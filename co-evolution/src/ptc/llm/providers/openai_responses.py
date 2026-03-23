from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ptc.llm.models import GenerationConfig, PromptInput, ProviderGeneration
from ptc.llm.runner import ModelProvider


@dataclass(slots=True)
class OpenAIResponsesProviderConfig:
    model_name_or_path: str
    api_key: str | None = None
    base_url: str | None = None


class OpenAIResponsesProvider(ModelProvider):
    def __init__(self, config: OpenAIResponsesProviderConfig):
        self.config = config
        self._client = None

    def prompt_mode(self) -> str:
        return "json"

    def generate_batch(
        self,
        prompts: list[PromptInput],
        generation_config: GenerationConfig,
    ) -> list[ProviderGeneration]:
        client = self._get_client()
        generations: list[ProviderGeneration] = []
        for prompt in prompts:
            try:
                response = client.responses.create(
                    model=normalize_openai_model_name(
                        self.config.model_name_or_path,
                        self.config.base_url,
                    ),
                    input=_response_input(prompt),
                    max_output_tokens=generation_config.max_new_tokens,
                    temperature=generation_config.temperature,
                    top_p=generation_config.top_p,
                    text={"format": prompt.response_format} if prompt.response_format else None,
                )
            except Exception as exc:
                raise RuntimeError(translate_provider_error(exc, self.config.base_url)) from exc
            output_text = self._extract_output_text(response)
            generations.append(
                ProviderGeneration(
                    id=prompt.id,
                    output_text=output_text,
                    metadata={"model_name_or_path": self.config.model_name_or_path, "api_type": "openai-responses"},
                )
            )
        return generations

    def _get_client(self):
        if self._client is not None:
            return self._client

        from openai import OpenAI

        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for api-type openai-responses. "
                "Pass --api-key or set OPENAI_API_KEY."
            )

        client_kwargs = {"api_key": api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        self._client = OpenAI(**client_kwargs)
        return self._client

    @staticmethod
    def _extract_output_text(response) -> str:
        if getattr(response, "output_text", None):
            return str(response.output_text).strip()

        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
        elif isinstance(response, dict):
            dumped = response
        else:
            return str(response).strip()

        output_text = _extract_text_from_dump(dumped)
        if output_text:
            return output_text
        return json.dumps(dumped, ensure_ascii=True)


def _response_input(prompt: PromptInput) -> list[dict]:
    input_messages: list[dict] = []
    for message in prompt.messages:
        content_blocks = []
        for block in message.content:
            if block.type != "text":
                continue
            content_blocks.append({"type": "input_text", "text": block.text})
        input_messages.append({"role": message.role, "content": content_blocks})
    return input_messages


def _extract_text_from_dump(dumped: dict) -> str:
    for output_item in dumped.get("output", []):
        for content in output_item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"]).strip()
    return ""


def normalize_openai_model_name(model_name_or_path: str, base_url: str | None = None) -> str:
    normalized = model_name_or_path.strip().replace("\\", "/")
    if _is_official_openai_base_url(base_url) and normalized.startswith("openai/"):
        return normalized.split("/", 1)[1]
    return normalized


def _is_official_openai_base_url(base_url: str | None) -> bool:
    if not base_url:
        return True
    normalized = base_url.strip().rstrip("/")
    return normalized in {
        "https://api.openai.com/v1",
        "https://api.openai.com",
    }


def translate_provider_error(exc: Exception, base_url: str | None) -> str:
    message = str(exc)
    if _is_openrouter_base_url(base_url):
        lowered = message.lower()
        if "no endpoints available matching your guardrail restrictions and data policy" in lowered:
            return (
                "OpenRouter could not route this request because your current privacy/guardrail "
                "settings block all available endpoints for the selected model. "
                "Review https://openrouter.ai/settings/privacy and relax the relevant restrictions, "
                "then retry."
            )
    return message


def _is_openrouter_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    return "openrouter.ai" in base_url.lower()
