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
.explainer { color: #a8a29e; font-size: 0.86rem; text-align: center; margin-top: 10px; }
footer { display: none !important; }
"""


def build_ui(service: Unstuck) -> gr.Blocks:
    """Build the Gradio UI around an injected Unstuck service."""

    def render_steps(view: BreakdownView) -> tuple[str, list[dict[str, Any]]]:
        rows = [
            {
                "step_id": row.step_id,
                "text": row.text,
                "raw_minutes": row.raw_minutes,
                "calibrated_minutes": row.calibrated_minutes,
            }
            for row in view.rows
        ]
        import html as html_lib

        cards = ['<div id="steps-list">']
        for index, row in enumerate(rows, start=1):
            text = html_lib.escape(str(row["text"]))
            cards.append(
                '<div class="step-card">'
                f'<div class="step-num">{index}</div>'
                f'<div class="step-text">{text}</div>'
                f'<div class="chip chip-raw">AI: {row["raw_minutes"]} min</div>'
                f'<div class="chip chip-you">For you: {row["calibrated_minutes"]} min</div>'
                "</div>"
            )
        cards.append(
            '<div class="explainer">"For you" recalibrates the AI estimate from the '
            "actual times you log — your personal time-blindness, learned per category.</div>"
        )
        cards.append("</div>")
        return "".join(cards), rows

    def break_down(task: str) -> tuple[str, list[dict[str, Any]], Any]:
        clean_task = task.strip()
        if not clean_task:
            return (
                '<div class="explainer">Enter a task to break down.</div>',
                [],
                gr.update(choices=[], value=None),
            )

        html, rows = render_steps(service.breakdown(clean_task))
        choices = [
            (f"{index}. {row['text']}", row["step_id"])
            for index, row in enumerate(rows, start=1)
        ]
        return html, rows, gr.update(choices=choices, value=None)

    def log_actual(step_id: int | None, actual_minutes: float | None) -> str:
        if step_id is None:
            return "Choose a step first."
        if actual_minutes is None or actual_minutes <= 0:
            return "Enter actual minutes greater than 0."

        service.log_actual(int(step_id), int(round(actual_minutes)))
        return (
            "Logged — future estimates in this category now lean on your real pace."
        )

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
        steps_output = gr.HTML()

        with gr.Accordion("Log actual time", open=False):
            step_choice = gr.Dropdown(label="Step", choices=[])
            actual_minutes = gr.Number(
                label="Actual minutes",
                minimum=1,
                precision=0,
            )
            log_button = gr.Button("Log actual")
            log_status = gr.Markdown()

        export_button = gr.Button("Export my data (JSON)")
        export_file = gr.File(label="Download", interactive=False)

        break_button.click(
            break_down,
            inputs=task,
            outputs=[steps_output, rows_state, step_choice],
        )
        log_button.click(
            log_actual,
            inputs=[step_choice, actual_minutes],
            outputs=log_status,
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
