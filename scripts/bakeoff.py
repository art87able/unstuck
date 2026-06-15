"""Backend bake-off: run several small models through Unstuck's exact breakdown
contract and measure how often each returns a schema-valid plan.

All models are served serverless on Nebius Token Factory (the path that actually
hosts the small MiniCPM/Nemotron builds), driven through the same ModelAdapter the
app uses — so this measures real on-contract behaviour, not raw chat quality.

Run:  NEBIUS_API_KEY=... .venv/bin/python scripts/bakeoff.py
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unstuck.model_adapter import ModelAdapter  # noqa: E402
from unstuck.schema import StepValidationError  # noqa: E402

NEBIUS_BASE = "https://api.tokenfactory.nebius.com/v1/"

SAMPLE_TASKS = [
    "Clean my apartment before a friend visits tonight",
    "Start the first draft of a hackathon demo script",
    "Catch up on overdue email without losing the whole morning",
    "Prepare to call the dentist and book an appointment",
    "Make progress on a bug report that feels too vague to start",
]

MODELS = {
    "Qwen3-30B-A3B (teacher)": "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "MiniCPM-V-4.5 (OpenBMB)": "openbmb/MiniCPM-V-4_5",
    "Nemotron-3-Nano-30B (NVIDIA)": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
}


def make_generate(model_id: str) -> Callable[[str], str]:
    from huggingface_hub import InferenceClient

    client = InferenceClient(base_url=NEBIUS_BASE, api_key=os.environ["NEBIUS_API_KEY"])

    def generate(prompt: str) -> str:
        response = client.chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0,
        )
        return str(response.choices[0].message.content)

    return generate


def main() -> None:
    if not os.environ.get("NEBIUS_API_KEY"):
        sys.exit("NEBIUS_API_KEY required")

    print(f"| Model | Valid / {len(SAMPLE_TASKS)} | Avg steps | Avg latency |")
    print("|---|---|---|---|")
    for label, model_id in MODELS.items():
        adapter = ModelAdapter(make_generate(model_id), max_repairs=1)
        valid, step_counts, latencies = 0, [], []
        for task in SAMPLE_TASKS:
            t0 = time.monotonic()
            try:
                steps = adapter.breakdown(task, "regular")
                valid += 1
                step_counts.append(len(steps.steps))
            except StepValidationError:
                pass
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {label}: {exc}", file=sys.stderr)
            latencies.append(time.monotonic() - t0)
        avg_steps = f"{sum(step_counts) / len(step_counts):.1f}" if step_counts else "—"
        avg_lat = f"{sum(latencies) / len(latencies):.1f}s"
        print(f"| {label} | {valid}/{len(SAMPLE_TASKS)} | {avg_steps} | {avg_lat} |")


if __name__ == "__main__":
    main()
