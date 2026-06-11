"""Measured model eval: validity / repair / category stats per granularity.

Runs the real ModelAdapter pipeline (prompt -> generate -> validate -> one
repair) against an API backend and reports the numbers the field notes quote:

    .venv/bin/python scripts/eval_quality.py hf_inference
    NEBIUS_API_KEY=... .venv/bin/python scripts/eval_quality.py nebius

The zerogpu prefill path can't run off-GPU; scripts/smoke_live.py covers it
end-to-end against the deployed Space instead.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unstuck.model_adapter import ModelAdapter
from unstuck.schema import StepValidationError

TASKS = [
    "Clean my apartment before a friend visits tonight",
    "Start the first draft of a hackathon demo script",
    "Catch up on overdue email without losing the whole morning",
    "Prepare to call the dentist and book an appointment",
    "Make progress on a bug report that feels too vague to start",
    "Plan a small birthday dinner for four people",
    "Unpack and organise my desk after moving",
    "Write a cover letter for a job I actually want",
    "Sort out my tax documents before the deadline",
    "Practice guitar when I haven't touched it in a month",
    "Back up my laptop and phone properly",
    "Get back into running after three weeks off",
]
GRANULARITIES = ["chunky", "regular", "tiny"]
MAX_MINUTES = {"chunky": 25, "regular": 25, "tiny": 10}


def make_generate(backend: str) -> Callable[[str], str]:
    from huggingface_hub import InferenceClient

    temperature = float(os.environ.get("UNSTUCK_TEMPERATURE", "0"))
    if backend == "hf_inference":
        client = InferenceClient("Qwen/Qwen3-4B-Instruct-2507")
        model = None
    elif backend == "nebius":
        client = InferenceClient(
            base_url=os.environ.get(
                "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
            ),
            api_key=os.environ["NEBIUS_API_KEY"],
        )
        model = os.environ.get("NEBIUS_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")
    else:
        raise SystemExit(f"unsupported backend for offline eval: {backend}")

    def generate(prompt: str) -> str:
        kwargs = {"model": model} if model else {}
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=temperature,
            **kwargs,
        )
        return str(response.choices[0].message.content)

    return generate


def main() -> int:
    backend = sys.argv[1] if len(sys.argv) > 1 else "hf_inference"
    base_generate = make_generate(backend)
    results = {}

    for granularity in GRANULARITIES:
        calls = 0

        def counting_generate(prompt: str) -> str:
            nonlocal calls
            calls += 1
            return base_generate(prompt)

        adapter = ModelAdapter(counting_generate, max_repairs=1)
        stats = {
            "tasks": 0,
            "valid": 0,
            "first_try": 0,
            "repaired": 0,
            "failed": 0,
            "steps": [],
            "minutes_violations": 0,
            "categories": Counter(),
            "seconds": 0.0,
        }
        for task in TASKS:
            calls = 0
            stats["tasks"] += 1
            t0 = time.time()
            try:
                steps = adapter.breakdown(task, granularity)
            except StepValidationError as exc:
                stats["failed"] += 1
                print(f"  {granularity} FAIL {task[:40]!r}: {exc}")
                continue
            finally:
                stats["seconds"] += time.time() - t0
            stats["valid"] += 1
            if calls == 1:
                stats["first_try"] += 1
            else:
                stats["repaired"] += 1
            stats["steps"].append(len(steps.steps))
            for step in steps.steps:
                stats["categories"][step.category] += 1
                if step.est_minutes > MAX_MINUTES[granularity]:
                    stats["minutes_violations"] += 1
        results[granularity] = stats

    print(f"\n== {backend} · temperature={os.environ.get('UNSTUCK_TEMPERATURE', '0')} ==")
    print("granularity  valid  first-try  repaired  failed  steps(avg)  >cap  s/task  categories")
    for granularity, s in results.items():
        n = s["tasks"]
        avg_steps = sum(s["steps"]) / len(s["steps"]) if s["steps"] else 0
        cats = ", ".join(f"{c}:{k}" for c, k in s["categories"].most_common())
        print(
            f"{granularity:<11}  {s['valid']}/{n:<4} {s['first_try']}/{n:<7}"
            f"  {s['repaired']:<8}  {s['failed']:<6}  {avg_steps:<10.1f}"
            f"  {s['minutes_violations']:<4}  {s['seconds'] / n:<6.1f}  {cats}"
        )
    print(json.dumps({g: {k: (dict(v) if isinstance(v, Counter) else v) for k, v in s.items()} for g, s in results.items()}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
