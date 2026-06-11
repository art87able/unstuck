from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import html
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import gradio as gr

from unstuck.calibration import calibrate, multiplier
from unstuck.service import BreakdownView, Unstuck
from unstuck.store import Store


THEME = gr.themes.Base(
    primary_hue="indigo",
    neutral_hue="stone",
    font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
).set(
    body_background_fill="#faf9f7",
    block_background_fill="#ffffff",
    block_border_width="0px",
    block_shadow="0 1px 3px rgba(40, 35, 60, 0.07)",
    button_primary_background_fill="#4f46e5",
    button_primary_background_fill_hover="#4338ca",
    button_primary_text_color="#ffffff",
    block_radius="14px",
    button_large_radius="10px",
)

CSS = """
.gradio-container { max-width: 760px !important; margin: 0 auto !important; }
#hero { text-align: center; padding: 1.4rem 0 0.2rem; }
#hero h1 { font-size: 2rem; margin: 0; letter-spacing: -0.02em; color: #1c1917; }
#hero p { color: #78716c; margin: 0.4rem 0 0; font-size: 1.02rem; }
#steps-list { display: flex; flex-direction: column; gap: 10px; }
.step-card { display: flex; align-items: center; gap: 14px; background: #fff;
  border: 1px solid #eee9e2; border-radius: 12px; padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(40, 35, 60, 0.05); }
.step-next { border-color:#4f46e5; box-shadow:0 2px 8px rgba(79,70,229,0.18); }
.step-next .step-num { background:#4f46e5; color:#fff; }
.step-later { opacity:0.55; }
.step-skipped { opacity:0.45; }
.step-skipped .step-text { text-decoration:line-through; }
.step-num { flex: none; width: 30px; height: 30px; border-radius: 50%;
  background: #eef2ff; color: #4f46e5; font-weight: 600; display: flex;
  align-items: center; justify-content: center; font-size: 0.9rem; }
.step-text { flex: 1; color: #292524; font-size: 1rem; line-height: 1.4; }
.chip { flex: none; border-radius: 999px; padding: 3px 11px; font-size: 0.82rem;
  white-space: nowrap; }
.chip-raw { background: #f5f5f4; color: #78716c; }
.chip-you { background: #eef2ff; color: #4338ca; font-weight: 600; }
.chip-done { background: #ecfdf5; color: #047857; font-weight: 600; }
.chip-timer { background: #fef3c7; color: #b45309; font-weight: 600; }
.chip-skip { background:#f5f5f4; color:#a8a29e; }
.step-row { align-items: center !important; gap: 10px !important; margin-bottom: 10px; }
.step-row .step-card { flex: 1; }
.took-input input { border-radius: 10px !important; }
.readout { background: #eef2ff; color: #4338ca; border-radius: 12px; padding: 12px 18px;
  font-size: 0.95rem; text-align: center; margin-top: 6px; }
.completion { background:#ecfdf5; color:#047857; border-radius:12px;
  padding:14px 18px; font-size:1rem; text-align:center; margin-top:10px; font-weight:600; }
.summary { background: #f5f5f4; color: #57534e; border-radius: 12px; padding: 10px 16px;
  font-size: 0.94rem; text-align: center; margin-top: 8px; font-weight: 600; }
.patterns { display:flex; flex-direction:column; gap:8px; }
.pattern-row { display:flex; align-items:flex-end; gap:10px; background:#fff;
  border:1px solid #eee9e2; border-radius:10px; padding:8px 14px; font-size:0.88rem; }
.pattern-cat { font-weight:600; color:#292524; min-width:90px; }
.pattern-mult { color:#4338ca; flex:1; }
.bar { display:inline-block; width:7px; background:#c7d2fe; border-radius:3px 3px 0 0;
  margin-right:2px; }
.pattern-n { color:#a8a29e; font-size:0.8rem; }
.explainer { color: #a8a29e; font-size: 0.86rem; text-align: center; margin-top: 10px; }
footer { display: none !important; }
"""


def finish_minutes(
    manual: float | None, started_at: float | None, now: float
) -> int | None:
    """Return manually entered minutes or compute elapsed timer minutes."""
    if manual is not None and manual > 0:
        return int(round(manual))
    if started_at is not None:
        return max(1, int(round((now - started_at) / 60.0)))
    return None


def next_step_id(rows: list[dict]) -> int | None:
    """Return the first unresolved step id in visible row order."""
    for row in rows:
        if not row["logged"] and not row.get("skipped"):
            return int(row["step_id"])
    return None


def make_record(
    category: str, est_minutes: int, actual_minutes: int, now: float
) -> dict[str, Any]:
    """Return one browser-stored calibration record."""
    return {
        "category": category,
        "est_minutes": est_minutes,
        "actual_minutes": actual_minutes,
        "completed_at": now,
    }


def _record_key(record: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        record["category"],
        record["est_minutes"],
        record["actual_minutes"],
        record["completed_at"],
    )


def _validate_record_row(row: Any, index: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"record {index} must be an object")

    category = row.get("category")
    est_minutes = row.get("est_minutes")
    actual_minutes = row.get("actual_minutes")
    completed_at = row.get("completed_at")

    if not isinstance(category, str):
        raise ValueError(f"record {index} category must be a string")
    if type(est_minutes) is not int or est_minutes <= 0:
        raise ValueError(f"record {index} est_minutes must be positive")
    if type(actual_minutes) is not int or actual_minutes <= 0:
        raise ValueError(f"record {index} actual_minutes must be positive")
    if type(completed_at) not in (int, float):
        raise ValueError(f"record {index} completed_at must be numeric")

    return make_record(category, est_minutes, actual_minutes, float(completed_at))


def merge_records(existing: list[dict], payload: str) -> tuple[list[dict], int, int]:
    """Merge valid exported records without mutating existing browser state."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid json") from exc

    if not isinstance(data, dict):
        raise ValueError("payload must be an object")
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be a list")

    rows = [
        _validate_record_row(row, index)
        for index, row in enumerate(records, start=1)
    ]

    merged = list(existing)
    seen = {_record_key(record) for record in merged}
    imported = 0
    skipped = 0
    for row in rows:
        key = _record_key(row)
        if key in seen:
            skipped += 1
            continue
        merged.append(row)
        seen.add(key)
        imported += 1

    return merged, imported, skipped


def export_payload(records: list[dict]) -> str:
    """Return a Store.export_json-compatible payload for browser records."""
    return json.dumps({"tasks": [], "steps": [], "records": records})


def with_plan(data: dict, task: str, rows: list) -> dict:
    """Return browser state with the visible plan snapshot replaced."""
    records = _records_from_data(data)
    return {
        "records": list(records),
        "plan": {"task": task, "rows": list(rows)},
    }


def with_records(data: dict, records: list) -> dict:
    """Return browser state with calibration records replaced."""
    plan = data.get("plan") if isinstance(data, dict) else None
    return {"records": list(records), "plan": plan}


def snapshot(data: dict, task: str, rows: list[dict]) -> dict:
    """Return browser state with the visible plan rows saved."""
    return with_plan(data, task, rows)


def summary_html(rows: list[dict[str, Any]]) -> str:
    """Return total plan timing for the current UI rows."""
    if not rows:
        return ""

    active_rows = [row for row in rows if not row.get("skipped")]
    total_for_you = sum(
        int(row["actual_minutes"])
        if row["logged"]
        else int(row["calibrated_minutes"])
        for row in active_rows
    )
    total_raw = sum(int(row["raw_minutes"]) for row in active_rows)
    n_done = sum(1 for row in rows if row["logged"])
    n_skipped = sum(1 for row in rows if row.get("skipped"))
    text = f"For you: ~{total_for_you} min total · AI estimate: {total_raw} min"
    if n_done:
        text += f" · {n_done}/{len(rows)} done"
    if n_skipped:
        text += f" · {n_skipped} skipped"
    return f'<div class="summary">{text}</div>'


def completion_html(rows: list[dict]) -> str:
    """Return the done-state banner once a plan has resolved."""
    if not rows:
        return ""
    if not all(row["logged"] or row.get("skipped") for row in rows):
        return ""

    logged_rows = [row for row in rows if row["logged"]]
    if not logged_rows:
        return ""

    n_done = len(logged_rows)
    n_skipped = sum(1 for row in rows if row.get("skipped"))
    took = sum(int(row["actual_minutes"]) for row in logged_rows)
    est = sum(int(row["raw_minutes"]) for row in logged_rows)
    line1 = f"🎉 Done — {n_done} steps in {took} min."
    if n_skipped > 0:
        line1 += f" ({n_skipped} skipped)"

    ratio = took / est
    if ratio > 1.05:
        line2 = (
            f"The AI guessed {est} min — you took {ratio:.1f}× longer, "
            "and Unstuck now knows that."
        )
    elif ratio < 0.95:
        line2 = (
            f"The AI guessed {est} min — you beat it, "
            f"finishing in {ratio:.1f}× the time."
        )
    else:
        line2 = f"The AI guessed {est} min — almost exactly right."
    return f'<div class="completion">{line1}<br>{line2}</div>'


def patterns_html(records: list[dict]) -> str:
    """Return per-category calibration history as compact HTML."""
    if not records:
        return ""

    blocks = []
    for category in sorted({str(record["category"]) for record in records}):
        category_records = [
            (index, record)
            for index, record in enumerate(records)
            if str(record.get("category")) == category
        ]
        ordered = sorted(
            category_records,
            key=lambda item: (float(item[1].get("completed_at", item[0])), item[0]),
        )
        recent = [record for _index, record in ordered[-5:]]
        mult = multiplier(category, records)
        if mult > 1.05:
            verdict = "you underestimate these"
        elif mult < 0.95:
            verdict = "you overestimate these"
        else:
            verdict = "your gut is right"

        bars = []
        for record in recent:
            est = int(record["est_minutes"])
            actual = int(record["actual_minutes"])
            ratio = actual / est
            height = max(4, min(36, int(round(ratio * 14))))
            title = html.escape(f"est {est} → took {actual} min", quote=True)
            bars.append(
                f'<span class="bar" style="height:{height}px" '
                f'title="{title}"></span>'
            )

        cat = html.escape(category)
        blocks.append(
            '<div class="pattern-row">'
            f'<span class="pattern-cat">{cat}</span>'
            f'<span class="pattern-mult">~{mult:.1f}× — {verdict}</span>'
            + "".join(bars)
            + f'<span class="pattern-n">{len(category_records)} logged</span>'
            "</div>"
        )

    return '<div class="patterns">' + "".join(blocks) + "</div>"


def _records_from_data(data: dict | None) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    records = data.get("records")
    return records if isinstance(records, list) else []


def new_plan(
    data: dict, patterns: Callable[[list[dict[str, Any]]], str]
) -> tuple[list[dict[str, Any]], str, str, str, Any, dict]:
    """Clear the visible plan while keeping browser-stored records."""
    records = _records_from_data(data)
    updated = {"records": list(records), "plan": None}
    return [], "", "", patterns(records), gr.update(value=""), updated


def restore_snapshot(
    data: dict, readout: Callable[[list[dict[str, Any]]], str]
) -> tuple[list[dict[str, Any]], str, str, str, Any]:
    """Return browser plan state for Gradio load, or empty state on bad data."""
    records = _records_from_data(data)
    patterns = patterns_html(records)
    plan = data.get("plan") if isinstance(data, dict) else None
    if not isinstance(plan, dict):
        return [], readout(records), "", patterns, gr.update()

    saved_task = plan.get("task")
    rows = plan.get("rows")
    if not isinstance(saved_task, str) or not isinstance(rows, list):
        return [], readout(records), "", patterns, gr.update()

    summary = completion_html(rows) + summary_html(rows)
    return rows, readout(records), summary, patterns, gr.update(value=saved_task)


def plan_markdown(task: str, rows: list[dict]) -> str:
    """Return the current plan as a portable markdown checklist."""
    if not rows:
        return ""

    title = task.strip() or "My plan"
    lines = [f"## {title}", ""]
    total_for_you = 0
    for row in rows:
        text = str(row["text"])
        if row.get("skipped"):
            lines.append(f"- [-] {text} (skipped)")
        elif row["logged"]:
            actual = int(row["actual_minutes"])
            total_for_you += actual
            lines.append(f"- [x] {text} (took {actual} min)")
        else:
            calibrated = int(row["calibrated_minutes"])
            total_for_you += calibrated
            lines.append(f"- [ ] {text} (~{calibrated} min)")

    lines.extend(["", f"Total for you: ~{total_for_you} min"])
    return "\n".join(lines)


def splice_rows(
    rows: list[dict[str, Any]], step_id: int, new_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace one visible step row with its freshly broken-down sub-steps."""
    spliced: list[dict[str, Any]] = []
    found = False
    for row in rows:
        if row["step_id"] == step_id:
            spliced.extend(new_rows)
            found = True
        else:
            spliced.append(row)
    return spliced if found else rows


def build_ui(service: Unstuck) -> gr.Blocks:
    """Build the Gradio UI around an injected Unstuck service."""

    def view_rows(view: BreakdownView) -> list[dict[str, Any]]:
        return [
            {
                "step_id": row.step_id,
                "text": row.text,
                "category": row.category,
                "raw_minutes": row.raw_minutes,
                "calibrated_minutes": row.calibrated_minutes,
                "logged": False,
                "skipped": False,
                "actual_minutes": None,
                "started_at": None,
            }
            for row in view.rows
        ]

    def recalibrated(
        rows: list[dict[str, Any]], records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            row
            if row["logged"] or row.get("skipped")
            else {
                **row,
                "calibrated_minutes": calibrate(
                    row["raw_minutes"], multiplier(row["category"], records)
                ),
            }
            for row in rows
        ]

    def readout(records: list[dict[str, Any]]) -> str:
        if not records:
            return ""
        lines = []
        for category in sorted({r["category"] for r in records}):
            mult = multiplier(category, records)
            n = sum(1 for r in records if r["category"] == category)
            if mult > 1.05:
                verdict = f"run ~{mult:.1f}× long"
            elif mult < 0.95:
                verdict = f"run short (~{mult:.1f}×)"
            else:
                verdict = "are about right"
            lines.append(
                f"Your <em>{category}</em> estimates {verdict} "
                f"({n} logged) — adjusting for that."
            )
        return '<div class="readout">' + "<br>".join(lines) + "</div>"

    def patterns(records: list[dict[str, Any]]) -> str:
        return patterns_html(records)

    def persist(data: dict, task: str, rows: list[dict[str, Any]]) -> dict:
        return snapshot(data, task, rows)

    def restore(data: dict) -> tuple[list[dict[str, Any]], str, str, str, Any, dict]:
        rows, readout_html, summary, patterns_html_, task_update = restore_snapshot(
            data, readout
        )
        return rows, readout_html, summary, patterns_html_, task_update, data

    def break_down(
        task: str, data: dict, granularity: str
    ) -> tuple[list[dict[str, Any]], str, str, str, dict]:
        clean_task = task.strip()
        records = _records_from_data(data)
        if not clean_task:
            updated = persist(data, clean_task, [])
            return (
                [],
                '<div class="explainer">Enter a task to break down.</div>',
                "",
                patterns(records),
                updated,
            )
        try:
            rows = recalibrated(
                view_rows(service.breakdown(clean_task, granularity)), records
            )
        except Exception:
            gr.Warning("The model backend is busy. Try again in a minute.")
            updated = persist(data, clean_task, [])
            return (
                [],
                '<div class="explainer">The model backend is busy or out of GPU quota. '
                "Try again in a minute. Logging in to Hugging Face raises the free "
                "ZeroGPU quota.</div>",
                "",
                patterns(records),
                updated,
            )
        updated = persist(data, clean_task, rows)
        return (
            rows,
            readout(records),
            completion_html(rows) + summary_html(rows),
            patterns(records),
            updated,
        )

    def log_step(
        step_id: int,
    ) -> Any:
        def handler(
            minutes: float | None,
            task: str,
            rows: list[dict[str, Any]],
            data: dict,
        ) -> tuple[list[dict[str, Any]], str, str, str, dict]:
            records = _records_from_data(data)
            row = next((row for row in rows if row["step_id"] == step_id), None)
            if row is None:
                updated = persist(data, task, rows)
                return (
                    rows,
                    readout(records),
                    completion_html(rows) + summary_html(rows),
                    patterns(records),
                    updated,
                )
            actual = finish_minutes(minutes, row.get("started_at"), time.time())
            if actual is None:
                gr.Warning("Press Start first or enter minutes.")
                updated = persist(data, task, rows)
                return (
                    rows,
                    readout(records),
                    completion_html(rows) + summary_html(rows),
                    patterns(records),
                    updated,
                )
            records = records + [
                make_record(
                    str(row["category"]),
                    int(row["raw_minutes"]),
                    actual,
                    time.time(),
                )
            ]
            rows = [
                {**row, "logged": True, "actual_minutes": actual, "started_at": None}
                if row["step_id"] == step_id
                else row
                for row in rows
            ]
            rows = recalibrated(rows, records)
            updated = persist(with_records(data, records), task, rows)
            return (
                rows,
                readout(records),
                completion_html(rows) + summary_html(rows),
                patterns(records),
                updated,
            )

        return handler

    def start_step(
        step_id: int,
    ) -> Any:
        def handler(
            task: str, rows: list[dict[str, Any]], data: dict
        ) -> tuple[list[dict[str, Any]], str, str, str, dict]:
            records = _records_from_data(data)
            rows = [
                {**row, "started_at": time.time()}
                if row["step_id"] == step_id
                else row
                for row in rows
            ]
            updated = persist(data, task, rows)
            return (
                rows,
                readout(records),
                completion_html(rows) + summary_html(rows),
                patterns(records),
                updated,
            )

        return handler

    def skip_step(
        step_id: int,
    ) -> Any:
        def handler(
            task: str, rows: list[dict[str, Any]], data: dict
        ) -> tuple[list[dict[str, Any]], str, str, str, dict]:
            records = _records_from_data(data)
            rows = [
                {**row, "skipped": True, "started_at": None}
                if row["step_id"] == step_id
                else row
                for row in rows
            ]
            updated = persist(data, task, rows)
            return (
                rows,
                readout(records),
                completion_html(rows) + summary_html(rows),
                patterns(records),
                updated,
            )

        return handler

    def break_down_step(
        step_id: int,
    ) -> Any:
        def handler(
            task: str, rows: list[dict[str, Any]], data: dict
        ) -> tuple[list[dict[str, Any]], str, str, str, dict]:
            records = _records_from_data(data)
            if len(rows) >= 16:
                gr.Warning("That's plenty of steps — try starting the first tiny one")
                updated = persist(data, task, rows)
                return (
                    rows,
                    readout(records),
                    completion_html(rows) + summary_html(rows),
                    patterns(records),
                    updated,
                )

            step_text = next(
                (str(row["text"]) for row in rows if row["step_id"] == step_id),
                None,
            )
            if step_text is None:
                updated = persist(data, task, rows)
                return (
                    rows,
                    readout(records),
                    completion_html(rows) + summary_html(rows),
                    patterns(records),
                    updated,
                )

            try:
                new_rows = recalibrated(
                    view_rows(service.breakdown(step_text, "tiny")), records
                )
            except Exception:
                gr.Warning(
                    "The model backend is busy or out of GPU quota. "
                    "Try again in a minute."
                )
                updated = persist(data, task, rows)
                return (
                    rows,
                    readout(records),
                    completion_html(rows) + summary_html(rows),
                    patterns(records),
                    updated,
                )

            spliced = splice_rows(rows, step_id, new_rows)
            updated = persist(data, task, spliced)
            return (
                spliced,
                readout(records),
                completion_html(spliced) + summary_html(spliced),
                patterns(records),
                updated,
            )

        return handler

    def export_data(data: dict) -> tuple[str, dict]:
        records = _records_from_data(data)
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="unstuck-",
            delete=False,
        )
        with handle:
            handle.write(export_payload(records))
        return handle.name, data

    def import_data(
        file: Any, task: str, rows: list[dict[str, Any]], data: dict
    ) -> tuple[list[dict[str, Any]], str, str, str, dict]:
        file_path = getattr(file, "name", file)
        records = _records_from_data(data)
        try:
            payload = Path(file_path).read_text(encoding="utf-8")
            records, imported, skipped = merge_records(records, payload)
            status = f"Imported {imported} records ({skipped} duplicates skipped)"
        except (OSError, TypeError, ValueError):
            gr.Warning("That file doesn't look like an Unstuck export.")
            updated = persist(data, task, rows)
            return (
                rows,
                readout(records),
                completion_html(rows) + summary_html(rows),
                patterns(records),
                updated,
            )

        updated_rows = recalibrated(rows, records)
        status_html = f'<div class="summary">{status}</div>'
        updated = persist(with_records(data, records), task, updated_rows)
        return (
            updated_rows,
            readout(records) + status_html,
            completion_html(updated_rows) + summary_html(updated_rows),
            patterns(records),
            updated,
        )

    def copy_checklist(task: str, rows: list[dict[str, Any]]) -> Any:
        markdown = plan_markdown(task, rows)
        return gr.update(value=markdown, visible=bool(markdown))

    with gr.Blocks(title="Unstuck") as ui:
        gr.HTML(
            '<div id="hero"><h1>Unstuck</h1>'
            "<p>One overwhelming task &rarr; tiny timed steps, honest about how long "
            "<em>you</em> actually take.</p></div>"
        )
        rows_state = gr.State([])
        user_data = gr.BrowserState(
            {"records": [], "plan": None}, storage_key="unstuck-v1"
        )

        task = gr.Textbox(
            label="Task",
            placeholder="Paste the overwhelming thing here",
            lines=3,
        )
        granularity = gr.Radio(
            choices=["chunky", "regular", "tiny"],
            value="regular",
            label="Step size",
            info="How small should the pieces be?",
        )
        with gr.Row():
            break_button = gr.Button("Break it down", variant="primary")
            new_plan_button = gr.Button("New plan", variant="secondary")
        gr.Examples(
            examples=[
                ["Clean up my inbox and reply to the important emails"],
                ["Prepare a small birthday dinner for four"],
                ["Unpack and organise my desk after moving"],
            ],
            inputs=task,
            cache_examples=False,
        )
        readout_output = gr.HTML()
        summary_output = gr.HTML()
        with gr.Accordion("Your patterns", open=False):
            patterns_output = gr.HTML()

        @gr.render(inputs=rows_state)
        def render_rows(rows: list[dict[str, Any]]) -> None:
            import html as html_lib

            if not rows:
                return
            spotlight = next_step_id(rows)
            for index, row in enumerate(rows, start=1):
                text = html_lib.escape(str(row["text"]))
                is_spotlight = row["step_id"] == spotlight
                if row.get("skipped"):
                    card_class = "step-card step-skipped"
                    step_num = "–"
                    chips = '<div class="chip chip-skip">skipped</div>'
                elif row["logged"]:
                    card_class = "step-card"
                    step_num = "✓"
                    chips = (
                        f'<div class="chip chip-raw">AI: {row["raw_minutes"]} min</div>'
                        f'<div class="chip chip-done">took {row["actual_minutes"]} min</div>'
                    )
                elif is_spotlight:
                    card_class = "step-card step-next"
                    step_num = str(index)
                    chips = (
                        f'<div class="chip chip-raw">AI: {row["raw_minutes"]} min</div>'
                        f'<div class="chip chip-you">For you: '
                        f'{row["calibrated_minutes"]} min</div>'
                    )
                else:
                    card_class = "step-card step-later"
                    step_num = str(index)
                    chips = (
                        f'<div class="chip chip-raw">AI: {row["raw_minutes"]} min</div>'
                        f'<div class="chip chip-you">For you: '
                        f'{row["calibrated_minutes"]} min</div>'
                    )
                timer_chip = (
                    '<div class="chip chip-timer">⏱ timing</div>'
                    if row.get("started_at") is not None
                    and not row["logged"]
                    and not row.get("skipped")
                    else ""
                )
                with gr.Row(elem_classes="step-row"):
                    gr.HTML(
                        f'<div class="{card_class}">'
                        f'<div class="step-num">{step_num}</div>'
                        f'<div class="step-text">{text}</div>'
                        + chips
                        + timer_chip
                        + "</div>",
                        padding=False,
                    )
                    if is_spotlight:
                        start = gr.Button(
                            "Restart" if row.get("started_at") is not None else "Start",
                            size="sm",
                            scale=0,
                            min_width=80,
                            variant="secondary",
                        )
                        start.click(
                            start_step(int(row["step_id"])),
                            inputs=[task, rows_state, user_data],
                            outputs=[
                                rows_state,
                                readout_output,
                                summary_output,
                                patterns_output,
                                user_data,
                            ],
                            api_visibility="private",
                        )
                        minutes = gr.Number(
                            show_label=False,
                            container=False,
                            minimum=1,
                            precision=0,
                            placeholder="took (min)",
                            scale=0,
                            min_width=110,
                            elem_classes="took-input",
                        )
                        done = gr.Button(
                            "Done", size="sm", scale=0, min_width=70, variant="secondary"
                        )
                        done.click(
                            log_step(int(row["step_id"])),
                            inputs=[minutes, task, rows_state, user_data],
                            outputs=[
                                rows_state,
                                readout_output,
                                summary_output,
                                patterns_output,
                                user_data,
                            ],
                            api_visibility="private",
                        )
                        still_stuck = gr.Button(
                            "Still stuck?",
                            size="sm",
                            scale=0,
                            min_width=110,
                            variant="secondary",
                        )
                        still_stuck.click(
                            break_down_step(int(row["step_id"])),
                            inputs=[task, rows_state, user_data],
                            outputs=[
                                rows_state,
                                readout_output,
                                summary_output,
                                patterns_output,
                                user_data,
                            ],
                            api_visibility="private",
                        )
                        skip = gr.Button(
                            "Skip",
                            size="sm",
                            scale=0,
                            min_width=70,
                            variant="secondary",
                        )
                        skip.click(
                            skip_step(int(row["step_id"])),
                            inputs=[task, rows_state, user_data],
                            outputs=[
                                rows_state,
                                readout_output,
                                summary_output,
                                patterns_output,
                                user_data,
                            ],
                            api_visibility="private",
                        )
            gr.HTML(
                '<div class="explainer">"For you" recalibrates the AI estimate from the '
                "actual times you log — your personal time-blindness, learned per "
                "category. Log a step with <em>took (min) → Done</em> and watch the "
                "remaining estimates adjust.</div>"
            )

        with gr.Row():
            export_button = gr.Button("Export my data (JSON)")
            import_button = gr.UploadButton(
                "Import my data (JSON)",
                file_types=[".json"],
            )
            copy_button = gr.Button("Copy as checklist")
        export_file = gr.File(label="Download", interactive=False)
        checklist_output = gr.Textbox(
            label="Checklist", lines=8, visible=False, buttons=["copy"]
        )

        break_button.click(
            break_down,
            inputs=[task, user_data, granularity],
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                user_data,
            ],
        )
        new_plan_button.click(
            lambda data: new_plan(data, patterns),
            inputs=user_data,
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                task,
                user_data,
            ],
        )
        task.submit(
            break_down,
            inputs=[task, user_data, granularity],
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                user_data,
            ],
        )
        export_button.click(export_data, inputs=user_data, outputs=[export_file, user_data])
        import_button.upload(
            import_data,
            inputs=[import_button, task, rows_state, user_data],
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                user_data,
            ],
        )
        copy_button.click(
            copy_checklist,
            inputs=[task, rows_state],
            outputs=checklist_output,
        )
        ui.load(
            restore,
            inputs=user_data,
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                task,
                user_data,
            ],
        )

    return ui


def main() -> None:  # pragma: no cover
    data_dir = Path(os.environ.get("UNSTUCK_DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    from unstuck.backend import generate

    service = Unstuck(generate=generate, store=Store(str(data_dir / "unstuck.sqlite3")))
    build_ui(service).launch(theme=THEME, css=CSS)


if __name__ == "__main__":
    main()
