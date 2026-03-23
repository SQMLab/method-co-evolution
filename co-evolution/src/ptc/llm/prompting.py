from __future__ import annotations

import json
from pathlib import Path
import re

from ptc.llm.models import (
    LinkPrediction,
    PromptContentText,
    PromptInput,
    PromptMessage,
)
from ptc.llm.persistence import normalize_input_kind

_RESPONSE_FORMAT_PATH = (
    Path(__file__).resolve().parents[4] / "config" / "method_link_prediction_response_format.json"
)
with _RESPONSE_FORMAT_PATH.open("r", encoding="utf-8") as _handle:
    METHOD_LINK_PREDICTION_RESPONSE_FORMAT = json.load(_handle)


class MethodLinkingPromptFactory:
    def build_prompt(self, case_df, input_kind: str, prompt_format: str = "json") -> PromptInput:
        normalized_input_kind = normalize_input_kind(input_kind)
        source_prefix, candidate_prefix, group_column = _layout(normalized_input_kind)
        row = case_df.iloc[0]
        fqs = _display_method_text(row, source_prefix)
        url = row[f"{source_prefix}_url"]

        candidate_lookup: dict[str, dict] = {}
        candidate_lines = []
        seen_candidate_urls: set[str] = set()
        for row in case_df.itertuples(index=False):
            candidate_fqs = _display_method_text(row, candidate_prefix)
            candidate_sig = _row_value(row, f"{candidate_prefix}_sig")
            candidate_url = _row_value(row, f"{candidate_prefix}_url")

            if any([candidate_fqs, candidate_sig, candidate_url]):
                if not candidate_url or candidate_url not in seen_candidate_urls:
                    candidate_id = f"c{len(candidate_lookup) + 1}"

                    candidate_lookup[candidate_id] = {
                        "fqs": candidate_fqs,
                        "sig": candidate_sig or candidate_fqs,
                        "url": candidate_url,
                    }
                    candidate_lines.append(_candidate_line(candidate_id, candidate_fqs, prompt_format))
                    if candidate_url:
                        seen_candidate_urls.add(candidate_url)

        messages = self._build_messages(
            input_kind=normalized_input_kind,
            fqs=fqs,
            candidate_lines=candidate_lines,
            prompt_format=prompt_format,
        )
        prompt_text = render_messages_as_text(messages)

        return PromptInput(
            id=url,
            fqs=fqs,
            url=url,
            prompt_text=prompt_text,
            messages=messages,
            candidate_lookup=candidate_lookup,
            metadata={
                "input_kind": normalized_input_kind,
                "candidate_count": len(candidate_lookup),
                "prompt_format": prompt_format,
            },
            response_format=METHOD_LINK_PREDICTION_RESPONSE_FORMAT if prompt_format == "json" else None,
        )

    @staticmethod
    def _build_messages(
        input_kind: str,
        fqs: str,
        candidate_lines: list[str],
        prompt_format: str,
    ) -> list[PromptMessage]:
        candidate_block = "\n".join(candidate_lines) if candidate_lines else "- None"

        if input_kind == "t2p":
            system_text = _t2p_system_text(prompt_format)
            user_text = (
                f"Fully qualified signature (FQS) of test method: {fqs}\n"
                "Candidate production methods called by the test method:\n"
                f"{candidate_block}\n"
                f"{_output_instruction(prompt_format)}"
            )
            return [
                PromptMessage(role="system", content=[PromptContentText(type="text", text=system_text)]),
                PromptMessage(role="user", content=[PromptContentText(type="text", text=user_text)]),
            ]

        if input_kind == "p2t":
            system_text = _p2t_system_text(prompt_format)
            user_text = (
                f"Fully qualified signature (FQS) of production method: {fqs}\n"
                "Candidate test methods that call this production method:\n"
                f"{candidate_block}\n"
                f"{_output_instruction(prompt_format)}"
            )
            return [
                PromptMessage(role="system", content=[PromptContentText(type="text", text=system_text)]),
                PromptMessage(role="user", content=[PromptContentText(type="text", text=user_text)]),
            ]

        raise ValueError(f"Unsupported input_kind: {input_kind}")

def render_messages_as_text(messages: list[PromptMessage]) -> str:
    rendered_messages: list[str] = []
    for message in messages:
        content_text = "\n".join(block.text for block in message.content if block.type == "text").strip()
        rendered_messages.append(f"{message.role.upper()}:\n{content_text}")
    return "\n\n".join(rendered_messages).strip()


def _t2p_system_text(prompt_format: str) -> str:
    return (
        "You are an expert in identifying which production methods are being tested by a given test method in a Java codebase. "
        "The input consists of a test method and a list of candidate production methods that are called within the test method. "
        "your task is to determine which of these candidate production methods are actually under test. "
        f"{_return_requirement(prompt_format)}"
    )


def _p2t_system_text(prompt_format: str) -> str:
    return (
        "You are an expert in finding the test methods that call a production method in a Java codebase. "
        "Choose the candidate test methods that actually test the production method. "
        f"{_return_requirement(prompt_format)}"
    )


def _output_instruction(prompt_format: str) -> str:
    if prompt_format == "json":
        return (
            "Use the candidate IDs from the list below. "
            "Do not repeat the prompt. Do not use markdown or code fences."
        )
    return (
        "Return exactly this format:\n"
        "METHOD: <exact candidate method from the list above or NONE>\n"
        "CONFIDENCE: <confidence between 0 and 1>\n"
        "RATIONALE: <short explanation>\n"
        "\n"
        "Repeat these three lines for each selected method."
    )


def _return_requirement(prompt_format: str) -> str:
    if prompt_format == "json":
        return "Return valid JSON only that follows the provided schema. Only return candidate IDs such as c1 or c2."
    return "Return only the requested labeled fields. Use the exact candidate method text from the list."


class JsonPredictionParser:
    parser_name = "json_prediction_parser"

    def parse(self, prompt_input: PromptInput, output_text: str) -> LinkPrediction:
        payload = self._extract_or_fallback_payload(output_text)
        candidate_ids = self._resolve_candidate_ids(prompt_input, payload)
        candidate_confidences = self._normalize_selected_confidences(payload, candidate_ids)
        candidate_rationales = self._normalize_selected_rationales(payload, candidate_ids)
        selected_candidate_fqses: list[str] = []
        selected_candidate_sigs: list[str] = []
        selected_candidate_urls: list[str] = []

        for candidate_id in candidate_ids:
            candidate = prompt_input.candidate_lookup.get(candidate_id)
            if candidate is None:
                continue
            selected_candidate_fqses.append(candidate["fqs"])
            selected_candidate_sigs.append(candidate["sig"])
            selected_candidate_urls.append(candidate["url"])

        return LinkPrediction(
            id=prompt_input.id,
            fqs=prompt_input.fqs,
            url=prompt_input.url,
            label="match" if candidate_ids else "none",
            raw_output_text=output_text,
            confidence=self._coerce_confidence(payload.get("confidence")),
            selected_candidate_ids=candidate_ids,
            selected_candidate_confidences=candidate_confidences,
            selected_candidate_fqses=selected_candidate_fqses,
            selected_candidate_sigs=selected_candidate_sigs,
            selected_candidate_urls=selected_candidate_urls,
            rationale=str(payload.get("rationale", "")).strip(),
            selected_candidate_rationales=candidate_rationales,
            metadata={"raw_json": payload},
        )

    @classmethod
    def _extract_or_fallback_payload(cls, output_text: str) -> dict:
        try:
            return cls._extract_json(output_text)
        except ValueError:
            conventional_payload = cls._extract_conventional_payload(output_text)
            if conventional_payload is not None:
                return conventional_payload
            stripped_output = output_text.strip()
            return {
                "candidate_ids": [],
                "confidence": None,
                "rationale": (
                    "Model did not return a JSON object."
                    if stripped_output
                    else "Model returned an empty response."
                ),
            }

    @staticmethod
    def _extract_conventional_payload(output_text: str) -> dict | None:
        stripped_output = output_text.strip()
        if not stripped_output:
            return None

        method_blocks = JsonPredictionParser._extract_method_blocks(stripped_output)
        if method_blocks:
            return JsonPredictionParser._payload_from_method_blocks(method_blocks)

        ids_match = re.search(r"(?im)^\s*candidate_ids\s*:\s*(.+?)\s*$", stripped_output)
        confidence_match = re.search(r"(?im)^\s*confidence\s*:\s*(.+?)\s*$", stripped_output)
        rationale_match = re.search(r"(?im)^\s*rationale\s*:\s*(.+)$", stripped_output)

        if ids_match is None and confidence_match is None and rationale_match is None:
            return None

        candidate_ids: list[str] = []
        if ids_match is not None:
            raw_ids = ids_match.group(1).strip()
            if raw_ids.upper() not in {"", "NONE", "[]"}:
                candidate_ids = [
                    item.strip()
                    for item in re.split(r"[\s,|]+", raw_ids)
                    if item.strip()
                ]

        payload = {"candidate_ids": candidate_ids}
        if confidence_match is not None:
            payload["confidence"] = confidence_match.group(1).strip()
        if rationale_match is not None:
            payload["rationale"] = rationale_match.group(1).strip()
        return payload

    @staticmethod
    def _extract_json(output_text: str) -> dict:
        decoder = json.JSONDecoder()
        stripped_output = output_text.strip()
        standalone_payload = JsonPredictionParser._try_decode_standalone_json(decoder, stripped_output)
        normalized_payload = JsonPredictionParser._normalize_payload_shape(standalone_payload)
        if normalized_payload is not None and JsonPredictionParser._looks_like_prediction_payload(normalized_payload):
            return normalized_payload

        for start_index, character in enumerate(output_text):
            if character not in {"{", "["}:
                continue
            try:
                raw_payload, _ = decoder.raw_decode(output_text[start_index:])
            except json.JSONDecodeError:
                continue
            payload = JsonPredictionParser._normalize_payload_shape(raw_payload)
            if payload is not None and JsonPredictionParser._looks_like_prediction_payload(payload):
                return payload
        raise ValueError(f"Could not find JSON object in model output: {output_text}")

    @staticmethod
    def _try_decode_standalone_json(decoder: json.JSONDecoder, output_text: str):
        if not output_text:
            return None
        try:
            payload, end_index = decoder.raw_decode(output_text)
        except json.JSONDecodeError:
            return None
        if output_text[end_index:].strip():
            return None
        return payload

    @staticmethod
    def _looks_like_prediction_payload(payload: dict) -> bool:
        if "candidate_ids" not in payload and "candidate_id" not in payload:
            return False

        rationale = str(payload.get("rationale", "")).strip().lower()
        if rationale == "short explanation":
            return False

        candidate_ids = payload.get("candidate_ids", payload.get("candidate_id", []))
        if (
            isinstance(candidate_ids, list)
            and candidate_ids == ["c1", "c2"]
            and rationale == "short explanation"
        ):
            return False

        return True

    @staticmethod
    def _normalize_payload_shape(raw_payload) -> dict | None:
        if isinstance(raw_payload, dict):
            return raw_payload
        if isinstance(raw_payload, list) and all(isinstance(item, str) for item in raw_payload):
            return {"candidate_ids": raw_payload}
        return None

    @staticmethod
    def _normalize_candidate_ids(payload: dict) -> list[str]:
        raw_value = payload.get("candidate_ids", payload.get("candidate_id", []))
        if raw_value in (None, "", "NONE"):
            return []
        if isinstance(raw_value, str):
            return [raw_value]
        if isinstance(raw_value, list):
            return [str(item) for item in raw_value if str(item).upper() != "NONE"]
        raise ValueError(f"Unsupported candidate_ids payload: {raw_value}")

    @classmethod
    def _normalize_selected_confidences(
        cls,
        payload: dict,
        candidate_ids: list[str],
    ) -> list[float | None]:
        raw_value = payload.get("candidate_confidences", None)
        if isinstance(raw_value, dict):
            return [cls._coerce_confidence(raw_value.get(candidate_id)) for candidate_id in candidate_ids]
        if isinstance(raw_value, list):
            return [cls._coerce_confidence(item) for item in raw_value]

        confidence = cls._coerce_confidence(payload.get("confidence"))
        if candidate_ids and confidence is not None:
            return [confidence]
        return []

    @staticmethod
    def _normalize_selected_rationales(payload: dict, candidate_ids: list[str]) -> list[str]:
        raw_value = payload.get("candidate_rationales", None)
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]

        rationale = str(payload.get("rationale", "")).strip()
        if candidate_ids and rationale:
            return [rationale]
        return []

    @staticmethod
    def _coerce_confidence(value) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _resolve_candidate_ids(cls, prompt_input: PromptInput, payload: dict) -> list[str]:
        if "candidate_methods" in payload:
            return cls._resolve_candidate_methods(prompt_input, payload["candidate_methods"])
        return cls._normalize_candidate_ids(payload)

    @classmethod
    def _resolve_candidate_methods(cls, prompt_input: PromptInput, candidate_methods: list[str]) -> list[str]:
        resolved_candidate_ids: list[str] = []
        seen_candidate_ids: set[str] = set()
        normalized_lookup = {
            candidate_id: {
                cls._normalize_method_text(candidate["fqs"]),
                cls._normalize_method_text(candidate["sig"]),
            }
            for candidate_id, candidate in prompt_input.candidate_lookup.items()
        }

        for method_text in candidate_methods:
            normalized_method = cls._normalize_method_text(method_text)
            if normalized_method:
                for candidate_id, candidate_texts in normalized_lookup.items():
                    if normalized_method in candidate_texts and candidate_id not in seen_candidate_ids:
                        resolved_candidate_ids.append(candidate_id)
                        seen_candidate_ids.add(candidate_id)
                        break
        return resolved_candidate_ids

    @staticmethod
    def _normalize_method_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value).strip()).lower()

    @staticmethod
    def _extract_method_blocks(output_text: str) -> list[dict]:
        blocks: list[dict] = []
        current_block: dict[str, str] = {}
        saw_method_field = False

        for raw_line in output_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            method_match = re.match(r"(?i)^method\s*:\s*(.*)$", line)
            if method_match is not None:
                if current_block:
                    blocks.append(current_block)
                current_block = {"method": method_match.group(1).strip()}
                saw_method_field = True
            else:
                confidence_match = re.match(r"(?i)^confidence\s*:\s*(.*)$", line)
                if confidence_match is not None:
                    current_block["confidence"] = confidence_match.group(1).strip()
                else:
                    rationale_match = re.match(r"(?i)^rationale\s*:\s*(.*)$", line)
                    if rationale_match is not None:
                        current_rationale = current_block.get("rationale", "")
                        rationale_text = rationale_match.group(1).strip()
                        if current_rationale:
                            current_block["rationale"] = f"{current_rationale}\n{rationale_text}"
                        else:
                            current_block["rationale"] = rationale_text
                    else:
                        current_rationale = current_block.get("rationale", "")
                        if current_rationale:
                            current_block["rationale"] = f"{current_rationale}\n{line}"

        if current_block:
            blocks.append(current_block)

        if saw_method_field:
            return blocks
        return []

    @classmethod
    def _payload_from_method_blocks(cls, method_blocks: list[dict]) -> dict:
        candidate_methods: list[str] = []
        rationales: list[str] = []
        confidences: list[float] = []

        for block in method_blocks:
            method_text = str(block.get("method", "")).strip()
            if method_text.upper() not in {"", "NONE", "[]"}:
                candidate_methods.append(method_text)

            rationale_text = str(block.get("rationale", "")).strip()
            if rationale_text:
                rationales.append(rationale_text)

            confidence_value = cls._coerce_confidence(block.get("confidence"))
            if confidence_value is not None:
                confidences.append(confidence_value)

        payload = {
            "candidate_methods": candidate_methods,
            "candidate_confidences": confidences,
            "candidate_rationales": rationales,
        }
        if confidences:
            payload["confidence"] = max(confidences)
        if rationales:
            payload["rationale"] = "\n\n".join(rationales)
        return payload


def _layout(input_kind: str) -> tuple[str, str, str]:
    if input_kind in {"fan-out", "t2p"}:
        return "from", "to", "from_url"
    if input_kind in {"fan-in", "p2t"}:
        return "to", "from", "to_url"
    raise ValueError(f"Unsupported input_kind: {input_kind}")


def _display_method_text(row, prefix: str) -> str:
    for field_name in (
        f"{prefix}_fqs_alt",
        f"{prefix}_fqs",
        f"{prefix}_sig",
        f"{prefix}_fqn",
        f"{prefix}_name",
    ):
        value = _row_value(row, field_name)
        if value:
            return str(value)
    return ""


def _row_value(row, field_name: str) -> str:
    if hasattr(row, "get"):
        return row.get(field_name, "")
    return getattr(row, field_name, "")


def _candidate_line(candidate_id: str, candidate_fqs: str, prompt_format: str) -> str:
    if prompt_format == "json":
        return f"{candidate_id}: {candidate_fqs}"
    return candidate_fqs
