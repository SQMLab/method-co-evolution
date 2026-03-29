from __future__ import annotations

import html
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, urlencode

from .repository import (
    CommitEntry,
    HistoryRepository,
    MethodHistory,
    SampleRow,
    build_row_token,
    dump_json_bytes,
    load_post_data,
)


STYLE = """
<style>
:root {
  --bg: #f7f4ed;
  --panel: #fffdfa;
  --line: #d8cfbd;
  --ink: #1f2933;
  --muted: #6b7280;
  --accent: #0f766e;
  --accent-soft: #d7f3ef;
  --warn: #a16207;
  --warn-soft: #fef3c7;
  --danger: #b91c1c;
  --danger-soft: #fee2e2;
  --shadow: 0 18px 42px rgba(31, 41, 51, 0.08);
  --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  --sans: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 26%),
    linear-gradient(180deg, #fbf8f2 0%, #f7f4ed 50%, #f1ece1 100%);
  color: var(--ink);
  font-family: var(--sans);
}
a { color: var(--accent); }
main { max-width: 1280px; margin: 0 auto; padding: 32px 24px 72px; }
h1, h2, h3 { margin: 0; font-weight: 700; }
p { margin: 0; line-height: 1.55; }
code, pre, .mono { font-family: var(--mono); }
.hero {
  display: grid;
  gap: 18px;
  padding: 28px;
  border: 1px solid rgba(216, 207, 189, 0.9);
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(252,247,237,0.88));
  box-shadow: var(--shadow);
}
.hero p { color: var(--muted); max-width: 74ch; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  margin-top: 24px;
}
.card, .summary-card, .panel {
  background: rgba(255, 253, 250, 0.92);
  border: 1px solid rgba(216, 207, 189, 0.95);
  border-radius: 24px;
  padding: 22px;
  box-shadow: var(--shadow);
}
.panel { padding: 18px 20px; }
.eyebrow {
  color: var(--accent);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.78rem;
  font-weight: 700;
}
.muted { color: var(--muted); }
form {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
label {
  display: grid;
  gap: 6px;
  font-size: 0.95rem;
}
input, select, textarea, button {
  border-radius: 14px;
  border: 1px solid #cfc4af;
  padding: 12px 14px;
  font: inherit;
  color: var(--ink);
  background: rgba(255,255,255,0.96);
}
textarea { min-height: 110px; resize: vertical; }
button {
  background: linear-gradient(135deg, #0f766e, #155e75);
  color: white;
  border: none;
  cursor: pointer;
  font-weight: 700;
}
button.secondary {
  background: linear-gradient(135deg, #ebe2d3, #e3d6c0);
  color: var(--ink);
}
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  margin: 22px 0 28px;
}
.summary-card strong {
  display: block;
  font-size: 1.8rem;
  margin-top: 8px;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 11px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.86rem;
  font-weight: 700;
}
.chip.warn {
  background: var(--warn-soft);
  color: var(--warn);
}
.chip.danger {
  background: var(--danger-soft);
  color: var(--danger);
}
.chip.type-introduction {
  background: #dbeafe;
  color: #1d4ed8;
}
.chip.type-body {
  background: #dcfce7;
  color: #166534;
}
.chip.type-rename,
.chip.type-move,
.chip.type-file-move {
  background: #ede9fe;
  color: #6d28d9;
}
.chip.type-documentation,
.chip.type-format {
  background: #fce7f3;
  color: #be185d;
}
.chip.type-annotation,
.chip.type-modifier,
.chip.type-return-type,
.chip.type-exception,
.chip.type-parameter,
.chip.type-parameter-meta {
  background: #fef3c7;
  color: #a16207;
}
.chip.type-multi,
.chip.type-unknown {
  background: #fee2e2;
  color: #b91c1c;
}
.methods {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.method-panel h2 {
  font-size: 1.1rem;
  margin-top: 10px;
}
.method-panel .mono {
  font-size: 0.92rem;
  line-height: 1.5;
  word-break: break-word;
}
.timeline {
  display: grid;
  gap: 16px;
}
.timeline-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 84px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.timeline-center {
  position: relative;
  min-height: 0;
  align-self: stretch;
  display: grid;
  justify-items: center;
  gap: 8px;
  padding-top: 14px;
  padding-bottom: 14px;
}
.timeline-center::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(15,118,110,0.22), rgba(21,94,117,0.85));
}
.marker-stack {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 8px;
  align-items: center;
}
.marker {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #fff;
  border: 4px solid var(--accent);
  box-shadow: 0 0 0 4px rgba(215, 243, 239, 0.95);
}
.marker.right {
  border-color: #155e75;
  box-shadow: 0 0 0 4px rgba(191, 219, 254, 0.95);
}
.gap-label {
  position: relative;
  z-index: 1;
  text-align: center;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--muted);
  background: rgba(247, 244, 237, 0.96);
  padding: 4px 8px;
  border-radius: 999px;
}
.event-card {
  border-radius: 20px;
  border: 1px solid rgba(216, 207, 189, 0.95);
  background: rgba(255,255,255,0.92);
  padding: 14px 16px;
}
.event-card.right {
  background: rgba(245, 250, 255, 0.94);
}
details { border-radius: 16px; }
summary {
  list-style: none;
  cursor: pointer;
}
summary::-webkit-details-marker { display: none; }
.event-header {
  display: grid;
  gap: 7px;
}
.event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.meta-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: #f2ece2;
  font-size: 0.8rem;
  font-weight: 700;
}
.detail-grid {
  display: grid;
  gap: 12px;
  padding-top: 14px;
}
pre {
  white-space: pre-wrap;
  overflow-x: auto;
  padding: 14px;
  border-radius: 16px;
  background: #1f2933;
  color: #f8fafc;
  font-size: 0.86rem;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 18px;
  font-size: 0.95rem;
}
th, td {
  padding: 12px 10px;
  border-bottom: 1px solid rgba(216, 207, 189, 0.75);
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.flash {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 700;
}
.error {
  background: var(--danger-soft);
  color: var(--danger);
}
@media (max-width: 920px) {
  .methods, .timeline-row { grid-template-columns: 1fr; }
  .timeline-center { min-height: 72px; order: -1; }
  .timeline-center::before { left: 50%; transform: translateX(-50%); }
}
</style>
"""


@dataclass
class TimelineRow:
    left: CommitEntry | None
    right: CommitEntry | None
    sort_date: datetime | None
    sort_index: int
    gap_label: str


@dataclass
class PairSummary:
    exact_shared_commits: int
    left_only_commits: int
    right_only_commits: int
    nearest_gap_days: float | None
    pattern_label: str
    pattern_tone: str


def create_app(cache_directory: str | None = None, data_directory: str | None = None) -> "HistoryViewerApp":
    return HistoryViewerApp(HistoryRepository(cache_directory=cache_directory, data_directory=data_directory))


class HistoryViewerApp:
    def __init__(self, repository: HistoryRepository):
        self.repository = repository

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
        try:
            method = environ.get("REQUEST_METHOD", "GET").upper()
            path = environ.get("PATH_INFO", "/")

            if method == "GET" and path == "/":
                return self._respond_html(start_response, render_page("Method Co-Evolution Viewer", self._render_home()))
            if method == "GET" and path == "/revision":
                return self._handle_revision(environ, start_response)
            if method == "GET" and path == "/sample":
                return self._handle_sample(environ, start_response)
            if method == "GET" and path == "/api/history-json":
                return self._handle_history_json(environ, start_response)
            if method == "POST" and path == "/api/notes":
                return self._handle_update_note(environ, start_response)
            if method == "POST" and path == "/api/revision-links":
                return self._handle_write_revision_links(environ, start_response)

            return self._respond_html(start_response, render_page("Not Found", self._render_error("Route not found")), status="404 Not Found")
        except Exception as exc:  # pragma: no cover - safety net for interactive app
            content = self._render_error(f"{exc}", traceback.format_exc())
            return self._respond_html(start_response, render_page("Error", content), status="500 Internal Server Error")

    def _handle_revision(self, environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
        params = _query_params(environ)
        tool = params.get("tool") or _infer_tool_from_query(params)
        if not tool:
            raise ValueError("Pass tool=historyFinder or tool=codeShovel")

        from_history = self.repository.load_history(tool=tool, url=params.get("from_url", ""), file_path=params.get("from_file", ""))
        to_history = self.repository.load_history(tool=tool, url=params.get("to_url", ""), file_path=params.get("to_file", ""))

        sample_row = None
        sample_csv = params.get("sample_csv", "")
        if sample_csv and params.get("from_url") and params.get("to_url"):
            sample_row = self.repository.read_sample_row(sample_csv, from_url=params["from_url"], to_url=params["to_url"])

        content = self._render_revision(
            from_history=from_history,
            to_history=to_history,
            sample_row=sample_row,
            sample_csv=sample_csv,
        )
        return self._respond_html(start_response, render_page("Method History Revision", content))

    def _handle_sample(self, environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
        params = _query_params(environ)
        sample_dir = params.get("sample_dir", "")
        sample_csv = params.get("sample_csv", "")
        if sample_dir:
            csv_files = self.repository.list_sample_csv_files(sample_dir)
            content = self._render_sample_directory(sample_dir=sample_dir, csv_files=csv_files)
            return self._respond_html(start_response, render_page("Sample Directory", content))
        if not sample_csv:
            raise ValueError("Pass sample_dir=<sample directory> or sample_csv=<absolute path to a sampled CSV>")
        rows = self.repository.read_sample_rows(sample_csv)
        limit = int(params.get("limit", "50"))
        content = self._render_sample_table(sample_csv=sample_csv, rows=rows[:limit], total_rows=len(rows), base_url=_request_base_url(environ))
        return self._respond_html(start_response, render_page("Sample CSV", content))

    def _handle_update_note(self, environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
        payload = _read_payload(environ)
        updated = self.repository.update_sample_note(
            payload["sample_csv"],
            from_url=payload["from_url"],
            to_url=payload["to_url"],
            note=payload.get("note", ""),
        )
        response = {
            "ok": True,
            "row_index": updated.row_index,
            "row_token": build_row_token(updated.csv_path, updated.values.get("from_url", ""), updated.values.get("to_url", "")),
            "note": updated.note,
        }
        return self._respond_json(start_response, response)

    def _handle_write_revision_links(self, environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
        payload = _read_payload(environ)
        base_url = payload.get("base_url") or _request_base_url(environ)
        row_count = self.repository.write_revision_links(payload["sample_csv"], base_url=base_url)
        return self._respond_json(start_response, {"ok": True, "rows": row_count, "base_url": base_url})

    def _handle_history_json(self, environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
        params = _query_params(environ)
        side = params.get("side", "from")
        if side not in {"from", "to"}:
            raise ValueError("side must be from or to")
        tool = params.get("tool") or _infer_tool_from_query(params)
        if not tool:
            raise ValueError("Pass tool=historyFinder or tool=codeShovel")

        history = self.repository.load_history(
            tool=tool,
            url=params.get(f"{side}_url", ""),
            file_path=params.get(f"{side}_file", ""),
        )
        body = dump_json_bytes(history.raw)
        headers = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))]
        if params.get("download") == "1":
            headers.append(("Content-Disposition", f'attachment; filename="{safe_json_filename(history)}"'))
        start_response("200 OK", headers)
        return [body]

    def _render_home(self) -> str:
        cache_dir = html.escape(str(self.repository.cache_directory))
        sample_hint = html.escape(str(self.repository.data_directory / "t2p-change-sample" / "historyFinder" / "omc--nc--ncc"))
        return f"""
<main>
  <section class="hero">
    <div class="eyebrow">Method Evolution UI</div>
    <h1>Inspect how test and production methods move together</h1>
    <p>Use GitHub method URLs, cached history JSON files, or a sampled CSV. The viewer aligns both histories on one timeline so you can spot direct co-evolution, lagged follow-up changes, and long periods where the two sides drift apart.</p>
    <p class="muted">Default cache root: <span class="mono">{cache_dir}</span></p>
  </section>

  <section class="grid">
    <article class="card">
      <div class="eyebrow">Use Case 1</div>
      <h2>Compare by URL</h2>
      <p class="muted">Best when you already have a test method link and a production method link from GitHub.</p>
      <form method="get" action="/revision">
        <label>Tool
          <select name="tool">
            <option value="historyFinder">historyFinder</option>
            <option value="codeShovel">codeShovel</option>
          </select>
        </label>
        <label>From URL
          <input type="text" name="from_url" placeholder="https://github.com/.../blob/<commit>/...#L17" />
        </label>
        <label>To URL
          <input type="text" name="to_url" placeholder="https://github.com/.../blob/<commit>/...#L29" />
        </label>
        <button type="submit">Open comparison</button>
      </form>
    </article>

    <article class="card">
      <div class="eyebrow">Use Case 1</div>
      <h2>Compare by cached JSON</h2>
      <p class="muted">Best when you already know the exact method-history JSON files.</p>
      <form method="get" action="/revision">
        <label>Tool
          <select name="tool">
            <option value="historyFinder">historyFinder</option>
            <option value="codeShovel">codeShovel</option>
          </select>
        </label>
        <label>From file
          <input type="text" name="from_file" placeholder="/Users/.../.cache/history/...json" />
        </label>
        <label>To file
          <input type="text" name="to_file" placeholder="/Users/.../.cache/history/...json" />
        </label>
        <button type="submit">Open comparison</button>
      </form>
    </article>

    <article class="card">
      <div class="eyebrow">Use Case 2</div>
      <h2>Browse a sample directory</h2>
      <p class="muted">Open a sample directory first, choose one CSV, then inspect rows in the browser and write a <span class="mono">revision_url</span> column that DBeaver can click directly.</p>
      <form method="get" action="/sample">
        <label>Sample directory
          <input type="text" name="sample_dir" value="{sample_hint}" />
        </label>
        <button type="submit">Open directory</button>
      </form>
    </article>
  </section>
</main>
"""

    def _render_revision(
        self,
        *,
        from_history: MethodHistory,
        to_history: MethodHistory,
        sample_row: SampleRow | None,
        sample_csv: str,
    ) -> str:
        rows = build_timeline_rows(from_history.entries, to_history.entries)
        summary = build_pair_summary(from_history.entries, to_history.entries)
        query_params = {
            "tool": from_history.tool or to_history.tool,
            "sample_csv": sample_csv,
            "from_url": from_history.input_url,
            "to_url": to_history.input_url,
            "from_file": from_history.input_file,
            "to_file": to_history.input_file,
        }
        note_panel = ""
        if sample_row is not None:
            note_panel = self._render_note_panel(sample_row, sample_csv)

        return f"""
<main>
  <section class="hero">
    <div class="eyebrow">Revision Viewer</div>
    <h1>{html.escape(summary.pattern_label)}</h1>
    <p>This view keeps both method histories on one descending timeline. Same-commit changes share a row, while unmatched changes show the nearest opposite-side gap so you can quickly see whether the test and source methods co-evolved or drifted.</p>
    <div class="chip-row">
      <span class="chip {html.escape(summary.pattern_tone)}">{html.escape(summary.pattern_label)}</span>
      <span class="chip">Tool: {html.escape(from_history.tool)}</span>
      <span class="chip">Project: {html.escape(from_history.project or to_history.project)}</span>
    </div>
  </section>

  <section class="stats">
    <article class="summary-card">
      <div class="eyebrow">Shared Commits</div>
      <strong>{summary.exact_shared_commits}</strong>
      <p class="muted">Changes recorded on the same commit hash.</p>
    </article>
    <article class="summary-card">
      <div class="eyebrow">Test-Only Changes</div>
      <strong>{summary.left_only_commits}</strong>
      <p class="muted">Commits seen only on the left side.</p>
    </article>
    <article class="summary-card">
      <div class="eyebrow">Production-Only Changes</div>
      <strong>{summary.right_only_commits}</strong>
      <p class="muted">Commits seen only on the right side.</p>
    </article>
    <article class="summary-card">
      <div class="eyebrow">Nearest Gap</div>
      <strong>{format_days(summary.nearest_gap_days)}</strong>
      <p class="muted">Smallest time gap between any left and right change.</p>
    </article>
  </section>

  <section class="methods">
    {self._render_method_panel("Test / From", from_history, side="from", query_params=query_params)}
    {self._render_method_panel("Production / To", to_history, side="to", query_params=query_params)}
  </section>

  {note_panel}

  <section class="panel">
    <div class="eyebrow">Timeline</div>
    <h2 style="margin-top:10px;">Change history, newest first</h2>
    <div class="timeline" style="margin-top:18px;">
      {''.join(render_timeline_row(row) for row in rows)}
    </div>
  </section>
</main>
{NOTE_SCRIPT}
"""

    def _render_method_panel(self, title: str, history: MethodHistory, *, side: str, query_params: dict[str, str]) -> str:
        links = []
        if history.input_url:
            links.append(f'<a href="{html.escape(history.input_url)}" target="_blank" rel="noreferrer">Requested URL</a>')
        if history.input_file:
            links.append(f'<span class="mono">{html.escape(history.input_file)}</span>')
        json_view_url = build_history_json_url(side=side, query_params=query_params, download=False)
        json_download_url = build_history_json_url(side=side, query_params=query_params, download=True)
        return f"""
<article class="panel method-panel">
  <div class="eyebrow">{html.escape(title)}</div>
  <h2>{html.escape(history.function_name or history.function_id or "Unknown method")}</h2>
  <p class="mono" style="margin-top:10px;">{html.escape(history.source_file_path)}:{history.function_start_line}</p>
  <p class="muted" style="margin-top:10px;">{len(history.entries)} change commit(s)</p>
  <div class="chip-row">
    <span class="chip">Origin: {html.escape(history.origin or history.tool)}</span>
    <span class="chip">Start line: {history.function_start_line}</span>
  </div>
  <div class="button-row" style="margin-top:14px;">
    <a href="{html.escape(json_download_url)}" class="chip" target="_blank" rel="noreferrer">Download JSON</a>
    <button type="button" class="secondary copy-json-button" data-json-url="{html.escape(json_view_url)}">Copy JSON</button>
    <span class="flash json-copy-status" style="display:none;"></span>
  </div>
  <div style="margin-top:14px; display:grid; gap:8px;">{''.join(links)}</div>
</article>
"""

    def _render_note_panel(self, sample_row: SampleRow, sample_csv: str) -> str:
        token = build_row_token(sample_row.csv_path, sample_row.values.get("from_url", ""), sample_row.values.get("to_url", ""))
        return f"""
<section class="panel">
  <div class="eyebrow">Research Note</div>
  <h2 style="margin-top:10px;">Save manual review notes back to the sampled CSV</h2>
  <p class="muted" style="margin-top:8px;">This updates the <span class="mono">note</span> column in place for the current row.</p>
  <form id="note-form" data-row-token="{html.escape(token)}">
    <input type="hidden" name="sample_csv" value="{html.escape(sample_csv)}" />
    <input type="hidden" name="from_url" value="{html.escape(sample_row.values.get('from_url', ''))}" />
    <input type="hidden" name="to_url" value="{html.escape(sample_row.values.get('to_url', ''))}" />
    <label>Note
      <textarea name="note">{html.escape(sample_row.note)}</textarea>
    </label>
    <div class="button-row">
      <button type="submit">Save note</button>
      <span id="note-status" class="flash" style="display:none;"></span>
    </div>
  </form>
</section>
"""

    def _render_sample_table(self, *, sample_csv: str, rows: list[SampleRow], total_rows: int, base_url: str) -> str:
        table_rows = []
        for row in rows:
            values = row.values
            revision_url = values.get("revision_url") or self.repository.build_revision_url(
                base_url=base_url,
                csv_path=sample_csv,
                from_url=values.get("from_url", ""),
                to_url=values.get("to_url", ""),
                tool=values.get("tool", ""),
                project=values.get("project", ""),
            )
            table_rows.append(
                f"""
<tr>
  <td>{html.escape(values.get('project', ''))}</td>
  <td><strong>{html.escape(values.get('from_name', ''))}</strong></td>
  <td><strong>{html.escape(values.get('to_name', ''))}</strong></td>
  <td>{html.escape(values.get('tool', ''))}</td>
  <td><a href="{html.escape(revision_url)}" target="_blank" rel="noreferrer">Open revision</a></td>
  <td>{html.escape(values.get('note', '')) or '<span class="muted">No note</span>'}</td>
</tr>
"""
            )

        return f"""
<main>
  <section class="hero">
    <div class="eyebrow">Sample Browser</div>
    <h1>{html.escape(sample_csv)}</h1>
    <p>Showing {len(rows)} row(s) out of {total_rows}. Open a row directly from here, or persist a <span class="mono">revision_url</span> column for DBeaver.</p>
    <div class="button-row" style="margin-top:12px;">
      <button class="secondary" id="revision-link-button" data-sample-csv="{html.escape(sample_csv)}" data-base-url="{html.escape(base_url)}">Write revision_url column</button>
      <span id="revision-link-status" class="flash" style="display:none;"></span>
    </div>
  </section>

  <section class="panel" style="margin-top:24px;">
    <div class="eyebrow">Rows</div>
    <table>
      <thead>
        <tr>
          <th>Project</th>
          <th>From</th>
          <th>To</th>
          <th>Tool</th>
          <th>Revision</th>
          <th>Note</th>
        </tr>
      </thead>
      <tbody>
        {''.join(table_rows)}
      </tbody>
    </table>
  </section>
</main>
{REVISION_LINK_SCRIPT}
"""

    def _render_sample_directory(self, *, sample_dir: str, csv_files: list[Any]) -> str:
        file_links = []
        for csv_file in csv_files:
            file_links.append(
                f"""
<tr>
  <td><a href="/sample?sample_csv={quote(str(csv_file), safe='')}">{html.escape(csv_file.name)}</a></td>
  <td><span class="mono">{html.escape(str(csv_file))}</span></td>
</tr>
"""
            )

        if not file_links:
            file_links.append(
                """
<tr>
  <td colspan="2"><span class="muted">No CSV files found in this directory.</span></td>
</tr>
"""
            )

        return f"""
<main>
  <section class="hero">
    <div class="eyebrow">Sample Directory</div>
    <h1>{html.escape(sample_dir)}</h1>
    <p>Select a CSV file to see the sampled method pairs.</p>
  </section>

  <section class="panel" style="margin-top:24px;">
    <div class="eyebrow">CSV Files</div>
    <table>
      <thead>
        <tr>
          <th>File</th>
          <th>Path</th>
        </tr>
      </thead>
      <tbody>
        {''.join(file_links)}
      </tbody>
    </table>
  </section>
</main>
"""

    def _render_error(self, message: str, detail: str = "") -> str:
        detail_html = f"<pre>{html.escape(detail)}</pre>" if detail else ""
        return f"""
<main>
  <section class="hero">
    <div class="eyebrow">Viewer Error</div>
    <h1>Something blocked the viewer</h1>
    <div class="flash error">{html.escape(message)}</div>
    {detail_html}
  </section>
</main>
"""

    def _respond_html(self, start_response: Any, content: str, status: str = "200 OK") -> Iterable[bytes]:
        body = content.encode("utf-8")
        start_response(status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]

    def _respond_json(self, start_response: Any, payload: dict[str, Any], status: str = "200 OK") -> Iterable[bytes]:
        body = dump_json_bytes(payload)
        start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]


def render_page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  {STYLE}
</head>
<body>{content}</body>
</html>"""


def build_timeline_rows(left_entries: list[CommitEntry], right_entries: list[CommitEntry]) -> list[TimelineRow]:
    right_by_hash = {entry.commit_hash: entry for entry in right_entries}
    used_right_hashes: set[str] = set()
    rows: list[TimelineRow] = []

    for index, left_entry in enumerate(left_entries):
        paired_right = right_by_hash.get(left_entry.commit_hash)
        if paired_right is not None:
            used_right_hashes.add(paired_right.commit_hash)
        rows.append(
            TimelineRow(
                left=left_entry,
                right=paired_right,
                sort_date=max_datetime(left_entry.commit_date, paired_right.commit_date if paired_right else None),
                sort_index=index,
                gap_label=row_gap_label(left_entry, paired_right, right_entries),
            )
        )

    for index, right_entry in enumerate(right_entries, start=len(rows)):
        if right_entry.commit_hash in used_right_hashes:
            continue
        rows.append(
            TimelineRow(
                left=None,
                right=right_entry,
                sort_date=right_entry.commit_date,
                sort_index=index,
                gap_label=row_gap_label(None, right_entry, left_entries),
            )
        )

    rows.sort(key=lambda row: (row.sort_date or datetime.min, -row.sort_index), reverse=True)
    return rows


def build_pair_summary(left_entries: list[CommitEntry], right_entries: list[CommitEntry]) -> PairSummary:
    left_hashes = {entry.commit_hash for entry in left_entries}
    right_hashes = {entry.commit_hash for entry in right_entries}
    shared = len(left_hashes & right_hashes)
    left_only = len(left_hashes - right_hashes)
    right_only = len(right_hashes - left_hashes)

    nearest_gap: float | None = None
    right_dates = [entry.commit_date for entry in right_entries if entry.commit_date is not None]
    for left_entry in left_entries:
        if left_entry.commit_date is None:
            continue
        for right_date in right_dates:
            gap = abs((left_entry.commit_date - right_date).total_seconds()) / 86400.0
            nearest_gap = gap if nearest_gap is None else min(nearest_gap, gap)

    if shared > 0:
        label, tone = "Direct co-evolution", ""
    elif nearest_gap is not None and nearest_gap <= 7:
        label, tone = "Lagged co-evolution", "warn"
    else:
        label, tone = "Mostly separate evolution", "danger"

    return PairSummary(
        exact_shared_commits=shared,
        left_only_commits=left_only,
        right_only_commits=right_only,
        nearest_gap_days=nearest_gap,
        pattern_label=label,
        pattern_tone=tone,
    )


def render_timeline_row(row: TimelineRow) -> str:
    left_html = render_event_card(row.left, side="left")
    right_html = render_event_card(row.right, side="right")
    marker_html = []
    if row.left is not None:
        marker_html.append('<span class="marker"></span>')
    if row.right is not None:
        marker_html.append('<span class="marker right"></span>')

    return f"""
<article class="timeline-row">
  <div>{left_html}</div>
  <div class="timeline-center">
    <div class="marker-stack">{''.join(marker_html)}</div>
    <div class="gap-label">{html.escape(row.gap_label)}</div>
  </div>
  <div>{right_html}</div>
</article>
"""


def render_event_card(entry: CommitEntry | None, *, side: str) -> str:
    if entry is None:
        return "<div></div>"

    css_class = "event-card right" if side == "right" else "event-card"
    date_value = format_commit_datetime(entry.commit_date, entry.commit_date_raw)
    change_labels = entry.display_change_tags or entry.change_types
    change_chip_html = "".join(render_change_chip(change_label) for change_label in change_labels)
    change_types = ", ".join(entry.change_types)
    link_lines = []
    if entry.commit_url:
        link_lines.append(f'<a href="{html.escape(entry.commit_url)}" target="_blank" rel="noreferrer">Commit</a>')
    if entry.new_file_url:
        link_lines.append(f'<a href="{html.escape(entry.new_file_url)}" target="_blank" rel="noreferrer">Method URL</a>')
    if entry.old_file_url:
        link_lines.append(f'<a href="{html.escape(entry.old_file_url)}" target="_blank" rel="noreferrer">Previous Method URL</a>')
    if entry.diff_url:
        link_lines.append(f'<a href="{html.escape(entry.diff_url)}" target="_blank" rel="noreferrer">Diff URL</a>')

    return f"""
<details class="{css_class}">
  <summary>
    <div class="event-header">
      <div class="event-meta">
        <span class="meta-pill">{html.escape(entry.short_hash)}</span>
        <span class="meta-pill">{html.escape(date_value)}</span>
        <span class="meta-pill">{format_days(entry.days_between_commits)}</span>
      </div>
      <div class="chip-row">{change_chip_html}</div>
      <strong>{html.escape(entry.commit_message or "No commit message")}</strong>
      <span class="muted">{html.escape(entry.commit_author or "Unknown author")} · {html.escape(entry.path)}</span>
    </div>
  </summary>
  <div class="detail-grid">
    <div class="chip-row">
      <span class="chip">Types: {html.escape(change_types)}</span>
    </div>
    <div>{' · '.join(link_lines)}</div>
    <div>
      <div class="eyebrow">Actual Source</div>
      <pre>{html.escape(entry.actual_source or "No source captured")}</pre>
    </div>
    <div>
      <div class="eyebrow">Diff</div>
      <pre>{html.escape(entry.diff or "No diff captured")}</pre>
    </div>
  </div>
</details>
"""


def max_datetime(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None:
        return second
    if second is None:
        return first
    return max(first, second)


def nearest_gap_days(target: CommitEntry, others: list[CommitEntry]) -> float | None:
    if target.commit_date is None:
        return None
    gaps = [
        abs((target.commit_date - other.commit_date).total_seconds()) / 86400.0
        for other in others
        if other.commit_date is not None
    ]
    return min(gaps) if gaps else None


def row_gap_label(left: CommitEntry | None, right: CommitEntry | None, others: list[CommitEntry]) -> str:
    if left is not None and right is not None:
        return "same commit"
    target = left or right
    gap = nearest_gap_days(target, others) if target is not None else None
    if gap is None:
        return "no time gap"
    return f"nearest {format_days(gap)}"


def format_days(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "0.0 d"
    if value < 1:
        return f"{value * 24:.1f} h"
    return f"{value:.1f} d"


def format_commit_datetime(value: datetime | None, fallback: str) -> str:
    if value is None:
        return fallback or "Unknown date"
    return f"{value.year} {value.strftime('%B')} {value.day}, {value.strftime('%H:%M')}"


def render_change_chip(label: str) -> str:
    chip_class = f"chip {change_type_chip_class(label)}"
    return f'<span class="{html.escape(chip_class)}">{html.escape(label)}</span>'


def change_type_chip_class(label: str) -> str:
    normalized = (
        label.strip().lower()
        .replace(" ", "-")
        .replace("_", "-")
    )
    aliases = {
        "introduction": "type-introduction",
        "yintroduced": "type-introduction",
        "body": "type-body",
        "ybodychange": "type-body",
        "rename": "type-rename",
        "yrename": "type-rename",
        "move": "type-move",
        "ymovefromfile": "type-move",
        "file-move": "type-file-move",
        "file-move/rename": "type-file-move",
        "yfilerename": "type-file-move",
        "documentation": "type-documentation",
        "ydocumentationchange": "type-documentation",
        "format": "type-format",
        "yformatchange": "type-format",
        "annotation": "type-annotation",
        "yannotationchnage": "type-annotation",
        "modifier": "type-modifier",
        "ymodifierchange": "type-modifier",
        "return-type": "type-return-type",
        "yreturntypechange": "type-return-type",
        "exception": "type-exception",
        "exceptions": "type-exception",
        "yexceptionschange": "type-exception",
        "parameter": "type-parameter",
        "yparameterchange": "type-parameter",
        "parameter-meta": "type-parameter-meta",
        "yparametermetachange": "type-parameter-meta",
        "multi": "type-multi",
        "ymultichange": "type-multi",
        "unknown": "type-unknown",
    }
    return aliases.get(normalized, "type-unknown")


def _query_params(environ: dict[str, Any]) -> dict[str, str]:
    parsed = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _request_base_url(environ: dict[str, Any]) -> str:
    scheme = environ.get("wsgi.url_scheme", "http")
    host = environ.get("HTTP_HOST") or f"{environ.get('SERVER_NAME', '127.0.0.1')}:{environ.get('SERVER_PORT', '8765')}"
    return f"{scheme}://{host}"


def _read_payload(environ: dict[str, Any]) -> dict[str, str]:
    content_length = int(environ.get("CONTENT_LENGTH", "0") or "0")
    body = environ["wsgi.input"].read(content_length)
    return load_post_data(body, environ.get("CONTENT_TYPE", "application/x-www-form-urlencoded"))


def _infer_tool_from_query(params: dict[str, str]) -> str:
    for key in ("from_file", "to_file"):
        value = params.get(key, "")
        if "/historyFinder/" in value:
            return "historyFinder"
        if "/codeShovel/" in value:
            return "codeShovel"
    return ""


def build_history_json_url(*, side: str, query_params: dict[str, str], download: bool) -> str:
    params = {"side": side}
    for key in ("tool", "sample_csv", "from_url", "to_url", "from_file", "to_file"):
        value = query_params.get(key, "")
        if value:
            params[key] = value
    if download:
        params["download"] = "1"
    return f"/api/history-json?{urlencode(params)}"


def safe_json_filename(history: MethodHistory) -> str:
    function_name = history.function_name or history.function_id or "method-history"
    normalized = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in function_name)
    normalized = normalized.strip("-") or "method-history"
    project = history.project or "project"
    return f"{project}-{normalized}-{history.function_start_line}.json"


NOTE_SCRIPT = """
<script>
for (const button of document.querySelectorAll(".copy-json-button")) {
  button.addEventListener("click", async () => {
    const status = button.parentElement.querySelector(".json-copy-status");
    try {
      const response = await fetch(button.dataset.jsonUrl);
      const text = await response.text();
      await navigator.clipboard.writeText(text);
      status.style.display = "inline-flex";
      status.textContent = "JSON copied";
      status.classList.remove("error");
    } catch (error) {
      status.style.display = "inline-flex";
      status.textContent = "Copy failed";
      status.classList.add("error");
    }
  });
}
const noteForm = document.getElementById("note-form");
if (noteForm) {
  noteForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("note-status");
    const formData = new FormData(noteForm);
    const response = await fetch("/api/notes", { method: "POST", body: new URLSearchParams(formData) });
    const payload = await response.json();
    status.style.display = "inline-flex";
    status.textContent = payload.ok ? "Note saved to CSV" : "Save failed";
    status.classList.toggle("error", !payload.ok);
  });
}
</script>
"""


REVISION_LINK_SCRIPT = """
<script>
const revisionButton = document.getElementById("revision-link-button");
if (revisionButton) {
  revisionButton.addEventListener("click", async () => {
    const status = document.getElementById("revision-link-status");
    const payload = new URLSearchParams({
      sample_csv: revisionButton.dataset.sampleCsv,
      base_url: revisionButton.dataset.baseUrl,
    });
    const response = await fetch("/api/revision-links", { method: "POST", body: payload });
    const data = await response.json();
    status.style.display = "inline-flex";
    status.textContent = data.ok ? `revision_url written for ${data.rows} row(s)` : "Write failed";
    status.classList.toggle("error", !data.ok);
  });
}
</script>
"""
