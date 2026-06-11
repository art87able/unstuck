"""Live smoke test against the deployed Space — one plan per granularity.

Run after every Space sync:

    .venv/bin/python scripts/smoke_live.py [space_id]

Needs an authenticated `hf` CLI (the token buys ZeroGPU quota; anonymous quota
is often zero). Exits non-zero if any granularity fails to produce a plan.

Gotcha baked in below: over the API the plan rows come back in the BrowserState
output (res[3]["plan"]["rows"]) — the visible rows_state slot (res[0]) is empty.
"""

from __future__ import annotations

import sys
import time

import huggingface_hub
from gradio_client import Client

SPACE = sys.argv[1] if len(sys.argv) > 1 else "build-small-hackathon/unstuck"
TASK = "Clean up my inbox and reply to the important emails"
EMPTY_DATA = {"records": [], "plan": None}

# Looser than schema bounds on purpose: this checks the live pipeline produces
# a sane plan, not that every model whim is in spec.
EXPECTED = {
    "chunky": {"steps": (2, 8), "max_minutes": 25},
    "regular": {"steps": (3, 12), "max_minutes": 25},
    "tiny": {"steps": (3, 12), "max_minutes": 10},
}


def main() -> int:
    token = huggingface_hub.get_token()
    if not token:
        print("FAIL: no HF token (run `hf auth login`)")
        return 1
    client = Client(SPACE, token=token, verbose=False)

    failures = 0
    for granularity, bounds in EXPECTED.items():
        t0 = time.time()
        try:
            res = client.predict(TASK, EMPTY_DATA, granularity, api_name="/break_down")
        except Exception as exc:  # noqa: BLE001 - report and keep testing the rest
            print(f"{granularity}: FAIL call error {type(exc).__name__}: {exc}")
            failures += 1
            continue
        elapsed = time.time() - t0

        plan = (res[3] or {}).get("plan") or {}
        rows = plan.get("rows") or []
        lo, hi = bounds["steps"]
        problems = []
        if not lo <= len(rows) <= hi:
            problems.append(f"{len(rows)} steps, wanted {lo}-{hi}")
        bad_minutes = [
            r["raw_minutes"]
            for r in rows
            if not 0 < int(r.get("raw_minutes", 0)) <= bounds["max_minutes"]
        ]
        if bad_minutes:
            problems.append(f"raw_minutes out of bounds: {bad_minutes}")
        if any(not str(r.get("text", "")).strip() for r in rows):
            problems.append("empty step text")

        status = "FAIL " + "; ".join(problems) if problems else "OK"
        mins = [r.get("raw_minutes") for r in rows]
        print(f"{granularity}: {status} — {len(rows)} steps in {elapsed:.1f}s, minutes={mins}")
        failures += bool(problems)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
