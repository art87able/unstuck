from __future__ import annotations

import os
import sys
import tempfile
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
.step-row { align-items: center !important; gap: 10px !important; margin-bottom: 10px; }
.step-row .step-card { flex: 1; }
.took-input input { border-radius: 10px !important; }
.readout { background: #eef2ff; color: #4338ca; border-radius: 12px; padding: 12px 18px;
  font-size: 0.95rem; text-align: center; margin-top: 6px; }
.explainer { color: #a8a29e; font-size: 0.86rem; text-align: center; margin-top: 10px; }
footer { display: none !important; }
"""


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

    def break_down(task: str) -> tuple[list[dict[str, Any]], str]:
        clean_task = task.strip()
        if not clean_task:
            return [], '<div class="explainer">Enter a task to break down.</div>'
        return view_rows(service.breakdown(clean_task)), readout()

    def log_step(
        step_id: int,
    ) -> Any:
        def handler(
            minutes: float | None, rows: list[dict[str, Any]]
        ) -> tuple[list[dict[str, Any]], str]:
            if minutes is None or minutes <= 0:
                gr.Warning("Enter actual minutes greater than 0.")
                return rows, readout()
            actual = int(round(minutes))
            service.log_actual(step_id, actual)
            rows = [
                {**row, "logged": True, "actual_minutes": actual}
                if row["step_id"] == step_id
                else row
                for row in rows
            ]
            return recalibrated(rows), readout()

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
                        + "</div>",
                        padding=False,
                    )
                    if not row["logged"]:
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
                            outputs=[rows_state, readout_output],
                            api_visibility="private",
                        )
            gr.HTML(
                '<div class="explainer">"For you" recalibrates the AI estimate from the '
                "actual times you log — your personal time-blindness, learned per "
                "category. Log a step with <em>took (min) → Done</em> and watch the "
                "remaining estimates adjust.</div>"
            )

        export_button = gr.Button("Export my data (JSON)")
        export_file = gr.File(label="Download", interactive=False)

        break_button.click(
            break_down,
            inputs=task,
            outputs=[rows_state, readout_output],
        )
        export_button.click(export_data, outputs=export_file)

    return ui


def main() -> None:  # pragma: no cover
    data_dir = Path(os.environ.get("UNSTUCK_DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    from unstuck.backend import generate

    service = Unstuck(generate=generate, store=Store(str(data_dir / "unstuck.sqlite3")))
    build_ui(service).launch(theme=THEME, css=CSS)


if __name__ == "__main__":
    main()
