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
        table = [
            "| # | Step | AI est | For you |",
            "|---:|---|---:|---:|",
        ]
        for index, row in enumerate(rows, start=1):
            text = str(row["text"]).replace("|", "\\|")
            table.append(
                f"| {index} | {text} | {row['raw_minutes']} min | "
                f"{row['calibrated_minutes']} min |"
            )
        return "\n".join(table), rows

    def break_down(task: str) -> tuple[str, list[dict[str, Any]], Any]:
        clean_task = task.strip()
        if not clean_task:
            return "Enter a task to break down.", [], gr.update(choices=[], value=None)

        markdown, rows = render_steps(service.breakdown(clean_task))
        choices = [
            (f"{index}. {row['text']}", row["step_id"])
            for index, row in enumerate(rows, start=1)
        ]
        return markdown, rows, gr.update(choices=choices, value=None)

    def log_actual(step_id: int | None, actual_minutes: float | None) -> str:
        if step_id is None:
            return "Choose a step first."
        if actual_minutes is None or actual_minutes <= 0:
            return "Enter actual minutes greater than 0."

        service.log_actual(int(step_id), int(round(actual_minutes)))
        return "Logged."

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
        gr.Markdown("# Unstuck")
        rows_state = gr.State([])

        task = gr.Textbox(
            label="Task",
            placeholder="Paste the overwhelming thing here",
            lines=3,
        )
        break_button = gr.Button("Break it down", variant="primary")
        steps_output = gr.Markdown()

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
    build_ui(service).launch()


if __name__ == "__main__":
    main()
