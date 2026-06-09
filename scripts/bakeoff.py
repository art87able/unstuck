from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unstuck.model_adapter import ModelAdapter
from unstuck.schema import StepValidationError


SAMPLE_TASKS = [
    "Clean my apartment before a friend visits tonight",
    "Start the first draft of a hackathon demo script",
    "Catch up on overdue email without losing the whole morning",
    "Prepare to call the dentist and book an appointment",
    "Make progress on a bug report that feels too vague to start",
]

MODELS = [
    "Qwen/Qwen3-4B-Instruct-2507",
    "openbmb/MiniCPM3-4B",
    "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16",
]


def make_generate(model_id: str) -> Callable[[str], str]:
    """Create a serverless HF chat generator for manual model bake-offs."""
    from huggingface_hub import InferenceClient

    client = InferenceClient(model_id)

    def generate(prompt: str) -> str:
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0,
        )
        return str(response.choices[0].message.content)

    return generate


def score(model_id: str) -> float:
    """Return the fraction of sample tasks that produce validated step JSON."""
    adapter = ModelAdapter(make_generate(model_id), max_repairs=1)
    successes = 0

    for task in SAMPLE_TASKS:
        try:
            adapter.breakdown(task)
        except StepValidationError:
            continue
        successes += 1

    return successes / len(SAMPLE_TASKS)


if __name__ == "__main__":
    for model_id in MODELS:
        print(f"{model_id}: {score(model_id):.0%}")
