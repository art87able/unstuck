"""Phase 2: fine-tune on Nebius Token Factory and serve the result serverless.

Converts the distilled SFT set to OpenAI chat format, uploads it, and creates a
fine-tuning job. The output model is then servable via UNSTUCK_BACKEND=nebius with
NEBIUS_MODEL=<job output model> — completing the original Phase-2 vision (the
adapter served serverless, no local weights).

Run:    NEBIUS_API_KEY=... .venv/bin/python scripts/finetune/nebius_finetune.py
Poll:   add `poll <job_id>` as args.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.tokenfactory.nebius.com/v1"
SFT = pathlib.Path(__file__).resolve().parent / "unstuck_sft.jsonl"
# A small instruct base; if Nebius rejects it the error lists the allowed set.
BASE_MODEL = os.environ.get("NEBIUS_FT_BASE", "Qwen/Qwen2.5-1.5B-Instruct")


def _headers() -> dict:
    key = os.environ["NEBIUS_API_KEY"]
    return {"Authorization": f"Bearer {key}"}


def _to_chat(pairs: list[dict]) -> bytes:
    lines = []
    for p in pairs:
        lines.append(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": p["prompt"]},
                        {"role": "assistant", "content": p["completion"]},
                    ]
                }
            )
        )
    return ("\n".join(lines) + "\n").encode()


def launch() -> None:
    pairs = [json.loads(x) for x in SFT.read_text().splitlines() if x.strip()]
    chat_bytes = _to_chat(pairs)
    with httpx.Client(timeout=120) as c:
        up = c.post(
            f"{BASE}/files",
            headers=_headers(),
            files={"file": ("unstuck_chat.jsonl", chat_bytes, "application/jsonl")},
            data={"purpose": "fine-tune"},
        )
        print("upload:", up.status_code, up.text[:300])
        up.raise_for_status()
        file_id = up.json()["id"]

        job = c.post(
            f"{BASE}/fine_tuning/jobs",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"model": BASE_MODEL, "training_file": file_id},
        )
        print("job:", job.status_code, job.text[:500])
        job.raise_for_status()
        print("JOB_ID:", job.json()["id"])


def poll(job_id: str) -> None:
    with httpx.Client(timeout=60) as c:
        r = c.get(f"{BASE}/fine_tuning/jobs/{job_id}", headers=_headers())
        r.raise_for_status()
        d = r.json()
        print(
            "status:", d.get("status"),
            "| model:", d.get("fine_tuned_model"),
            "| trained_tokens:", d.get("trained_tokens"),
        )


if __name__ == "__main__":
    if not os.environ.get("NEBIUS_API_KEY"):
        sys.exit("NEBIUS_API_KEY required")
    if len(sys.argv) >= 3 and sys.argv[1] == "poll":
        poll(sys.argv[2])
    else:
        launch()
