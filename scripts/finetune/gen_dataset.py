"""Generate a fine-tuning dataset for Unstuck by distilling a strong Nebius model.

For each (task, granularity) we ask the strong serverless model for a breakdown,
validate it against the app's own schema, and keep only schema-valid pairs. The
result is a JSONL of {"prompt", "completion"} the tiny student model learns from.

Run:  NEBIUS_API_KEY=... .venv/bin/python scripts/finetune/gen_dataset.py
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import sys

os.environ.setdefault("UNSTUCK_BACKEND", "nebius")
os.environ.setdefault("NEBIUS_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from unstuck.backend import generate  # noqa: E402
from unstuck.model_adapter import ModelAdapter  # noqa: E402
from unstuck.prompts import breakdown_prompt  # noqa: E402

TASKS = [
    "Clean my apartment before a friend visits tonight",
    "Prepare the talk I keep putting off",
    "Do my taxes before the deadline",
    "Sort out the pile of unopened mail on my desk",
    "Plan a birthday party for my sister",
    "Write the overdue report for work",
    "Declutter my overflowing wardrobe",
    "Set up a budget for next month",
    "Fix the leaking tap in the bathroom",
    "Apply for three jobs this week",
    "Reply to the emails I have been avoiding",
    "Meal-prep lunches for the week",
    "Start my dissertation literature review",
    "Cancel the subscriptions I no longer use",
    "Organise the photos on my phone",
    "Build a simple personal website",
    "Repot the plants that have outgrown their pots",
    "Prepare for my driving theory test",
    "Deep-clean the kitchen",
    "Write thank-you notes after the wedding",
    "Get my bike ready for spring",
    "Plan a weekend trip to the coast",
    "Update my CV and LinkedIn",
    "Clear the backlog of dishes and laundry",
    "Learn the basics of a new programming language",
    "Sort the garage so I can park the car",
    "Renew my passport before it expires",
    "Draft the newsletter for the club",
    "Assemble the flat-pack desk",
    "Prepare a healthy grocery list and shop",
    "Back up all my important files",
    "Practice for the job interview on Friday",
    "Plant a small vegetable garden",
    "Write the blog post I promised",
    "Tidy and label the kitchen cupboards",
    "Set up automatic bill payments",
    "Read the contract before I sign it",
    "Plan my study schedule for finals",
    "Fix the broken shelf in the hallway",
    "Sort out which clothes to donate",
    "Register for the conference and book travel",
    "Clean out and organise my email inbox",
    "Prepare slides for Monday's review",
    "Make a packing list for the holiday",
]

GRANULARITIES = ("regular", "tiny", "chunky")


def make_pair(task: str, gran: str) -> dict | None:
    adapter = ModelAdapter(generate, max_repairs=1)
    try:
        steps = adapter.breakdown(task, gran)
    except Exception as exc:  # noqa: BLE001
        print(f"  skip [{gran}] {task[:40]}: {exc}", file=sys.stderr)
        return None
    completion = json.dumps(
        {
            "steps": [
                {"text": s.text, "category": s.category, "est_minutes": s.est_minutes}
                for s in steps.steps
            ]
        },
        separators=(",", ":"),
    )
    return {"prompt": breakdown_prompt(task, gran), "completion": completion}


def main() -> None:
    if not os.environ.get("NEBIUS_API_KEY"):
        sys.exit("NEBIUS_API_KEY is required")

    jobs = [(t, g) for t in TASKS for g in GRANULARITIES]
    out: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for pair in pool.map(lambda tg: make_pair(*tg), jobs):
            if pair:
                out.append(pair)

    dest = pathlib.Path(__file__).resolve().parent / "unstuck_sft.jsonl"
    dest.write_text("\n".join(json.dumps(p) for p in out) + "\n")
    print(f"wrote {len(out)}/{len(jobs)} valid pairs -> {dest}")


if __name__ == "__main__":
    main()
