from __future__ import annotations

import os
import sys
import tempfile
import time
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
.step-row { align-items: center !important; gap: 10px !important; margin-bottom: 10px; }
.step-row .step-card { flex: 1; }
.took-input input { border-radius: 10px !important; }
.readout { background: #eef2ff; color: #4338ca; border-radius: 12px; padding: 12px 18px;
  font-size: 0.95rem; text-align: center; margin-top: 6px; }
.summary { background: #f5f5f4; color: #57534e; border-radius: 12px; padding: 10px 16px;
  font-size: 0.94rem; text-align: center; margin-top: 8px; font-weight: 600; }
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


def summary_html(rows: list[dict[str, Any]]) -> str:
    """Return total plan timing for the current UI rows."""
    if not rows:
        return ""

    total_for_you = sum(
        int(row["actual_minutes"])
        if row["logged"]
        else int(row["calibrated_minutes"])
        for row in rows
    )
    total_raw = sum(int(row["raw_minutes"]) for row in rows)
    n_done = sum(1 for row in rows if row["logged"])
    text = f"For you: ~{total_for_you} min total · AI estimate: {total_raw} min"
    if n_done:
        text += f" · {n_done}/{len(rows)} done"
    return f'<div class="summary">{text}</div>'


def plan_markdown(task: str, rows: list[dict]) -> str:
    """Return the current plan as a portable markdown checklist."""
    if not rows:
        return ""

    title = task.strip() or "My plan"
    lines = [f"## {title}", ""]
    total_for_you = 0
    for row in rows:
        text = str(row["text"])
        if row["logged"]:
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


def parse_import(file_path: str | os.PathLike[str], store: Store) -> str:
    """Import an Unstuck export file and return a short user-facing status."""
    payload = Path(file_path).read_text(encoding="utf-8")
    result = store.import_json(payload)
    return (
        f"Imported {result['imported']} records "
        f"({result['skipped']} duplicates skipped)"
    )


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
                "actual_minutes": None,
                "started_at": None,
            }
            for row in view.rows
        ]

    def recalibrated(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records = service.store.get_records()
        return [
            row
            if row["logged"]
            else {
                **row,
                "calibrated_minutes": calibrate(
                    row["raw_minutes"], multiplier(row["category"], records)
                ),
            }
            for row in rows
        ]

    def readout() -> str:
        records = service.store.get_records()
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

    def break_down(task: str) -> tuple[list[dict[str, Any]], str, str]:
        clean_task = task.strip()
        if not clean_task:
            return [], '<div class="explainer">Enter a task to break down.</div>', ""
        try:
            rows = view_rows(service.breakdown(clean_task))
        except Exception:
            gr.Warning("The model backend is busy. Try again in a minute.")
            return (
                [],
                '<div class="explainer">The model backend is busy or out of GPU quota. '
                "Try again in a minute. Logging in to Hugging Face raises the free "
                "ZeroGPU quota.</div>",
                "",
            )
        return rows, readout(), summary_html(rows)

    def log_step(
        step_id: int,
    ) -> Any:
        def handler(
            minutes: float | None, rows: list[dict[str, Any]]
        ) -> tuple[list[dict[str, Any]], str, str]:
            row = next((row for row in rows if row["step_id"] == step_id), None)
            if row is None:
                return rows, readout(), summary_html(rows)
            actual = finish_minutes(minutes, row.get("started_at"), time.time())
            if actual is None:
                gr.Warning("Press Start first or enter minutes.")
                return rows, readout(), summary_html(rows)
            service.log_actual(step_id, actual)
            rows = [
                {**row, "logged": True, "actual_minutes": actual, "started_at": None}
                if row["step_id"] == step_id
                else row
                for row in rows
            ]
            rows = recalibrated(rows)
            return rows, readout(), summary_html(rows)

        return handler

    def start_step(
        step_id: int,
    ) -> Any:
        def handler(
            rows: list[dict[str, Any]]
        ) -> tuple[list[dict[str, Any]], str, str]:
            rows = [
                {**row, "started_at": time.time()}
                if row["step_id"] == step_id
                else row
                for row in rows
            ]
            return rows, readout(), summary_html(rows)

        return handler

    def break_down_step(
        step_id: int,
    ) -> Any:
        def handler(
            rows: list[dict[str, Any]]
        ) -> tuple[list[dict[str, Any]], str, str]:
            if len(rows) >= 16:
                gr.Warning("That's plenty of steps — try starting the first tiny one")
                return rows, readout(), summary_html(rows)

            step_text = next(
                (str(row["text"]) for row in rows if row["step_id"] == step_id),
                None,
            )
            if step_text is None:
                return rows, readout(), summary_html(rows)

            try:
                new_rows = view_rows(service.breakdown(step_text))
            except Exception:
                gr.Warning(
                    "The model backend is busy or out of GPU quota. "
                    "Try again in a minute."
                )
                return rows, readout(), summary_html(rows)

            spliced = splice_rows(rows, step_id, new_rows)
            return spliced, readout(), summary_html(spliced)

        return handler

    def export_data() -> str:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="unstuck-",
            delete=False,
        )
        with handle:
            handle.write(service.store.export_json())
        return handle.name

    def import_data(
        file: Any, rows: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], str, str]:
        file_path = getattr(file, "name", file)
        try:
            status = parse_import(file_path, service.store)
        except (OSError, TypeError, ValueError):
            gr.Warning("That file doesn't look like an Unstuck export.")
            return rows, readout(), summary_html(rows)

        updated_rows = recalibrated(rows)
        status_html = f'<div class="summary">{status}</div>'
        return updated_rows, readout() + status_html, summary_html(updated_rows)

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

        task = gr.Textbox(
            label="Task",
            placeholder="Paste the overwhelming thing here",
            lines=3,
        )
        break_button = gr.Button("Break it down", variant="primary")
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

        @gr.render(inputs=rows_state)
        def render_rows(rows: list[dict[str, Any]]) -> None:
            import html as html_lib

            if not rows:
                return
            for index, row in enumerate(rows, start=1):
                text = html_lib.escape(str(row["text"]))
                with gr.Row(elem_classes="step-row"):
                    gr.HTML(
                        '<div class="step-card">'
                        f'<div class="step-num">{"✓" if row["logged"] else index}</div>'
                        f'<div class="step-text">{text}</div>'
                        f'<div class="chip chip-raw">AI: {row["raw_minutes"]} min</div>'
                        + (
                            f'<div class="chip chip-done">took {row["actual_minutes"]} min</div>'
                            if row["logged"]
                            else f'<div class="chip chip-you">For you: '
                            f'{row["calibrated_minutes"]} min</div>'
                        )
                        + (
                            '<div class="chip chip-timer">⏱ timing</div>'
                            if row.get("started_at") is not None and not row["logged"]
                            else ""
                        )
                        + "</div>",
                        padding=False,
                    )
                    if not row["logged"]:
                        start = gr.Button(
                            "Restart" if row.get("started_at") is not None else "Start",
                            size="sm",
                            scale=0,
                            min_width=80,
                            variant="secondary",
                        )
                        start.click(
                            start_step(int(row["step_id"])),
                            inputs=rows_state,
                            outputs=[rows_state, readout_output, summary_output],
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
                            inputs=[minutes, rows_state],
                            outputs=[rows_state, readout_output, summary_output],
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
                            inputs=rows_state,
                            outputs=[rows_state, readout_output, summary_output],
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
            inputs=task,
            outputs=[rows_state, readout_output, summary_output],
        )
        task.submit(
            break_down,
            inputs=task,
            outputs=[rows_state, readout_output, summary_output],
        )
        export_button.click(export_data, outputs=export_file)
        import_button.upload(
            import_data,
            inputs=[import_button, rows_state],
            outputs=[rows_state, readout_output, summary_output],
        )
        copy_button.click(
            copy_checklist,
            inputs=[task, rows_state],
            outputs=checklist_output,
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
