# Unstuck — guide for the coding agent

> This file is to Codex what `CLAUDE.md` is to Claude Code: the always-loaded contract for how to
> work in this repo. Read it before every task. **User instructions and the per-task prompt in
> `PROMPTS.md` always take precedence over this file where they conflict.**

## What this is

**Unstuck** — an ADHD task assistant. One overwhelming task → a small (≤4B) LLM breaks it into
tiny, timed, categorised steps; a deterministic calibration layer then learns the user's personal
*time-blindness* and recalibrates estimates to them. Built for the HuggingFace **Build Small
Hackathon** (Backyard AI track), shipped as a Gradio **Hugging Face Space**. Deadline **2026-06-15**.

- **Model (locked):** `Qwen/Qwen3-4B-Instruct-2507` — ~4.02B, apache-2.0, native `qwen3` arch
  (no `trust_remote_code`). Stay **≤4B** (Tiny Titan award).
- **Architecture:** a thin Gradio UI over four independently-tested **pure-Python** units —
  `schema` (typed step model + validator), `model_adapter` (backend-agnostic breakdown with JSON
  validation + one repair retry), `calibration` (per-category time-bias multiplier), `store`
  (SQLite + JSON export) — tied together by `service`. The LLM is **injected** as a
  `generate(prompt) -> str` callable, so all logic is unit-tested with canned model output.

## How you work here (build discipline)

This repo is built **one task at a time** from `PROMPTS.md`. For each task:

1. **One task per run.** Do exactly the task given — nothing more, nothing adjacent.
2. **Only the named files.** Each task lists the only files it may touch. Touch nothing else.
3. **TDD, strictly.** Write the failing test first → run it → confirm it fails for the *stated*
   reason → implement until green. Don't write the implementation before the test.
4. **Verify before commit.** Run the exact test command in the task and confirm the expected pass
   count. Never commit on red.
5. **One commit per task,** with the exact message given, staging **only** the named files.
6. **No scope creep.** If finishing the task seems to need a file it didn't name, stop and surface
   it rather than expanding scope.

### Commit attribution

**You (Codex) author and attribute your own commits in this repo** — this is intentional (the
OpenAI Codex Track judges how the project was built with Codex). This is a deliberate, repo-scoped
exception to the owner's standing no-AI-attribution rule; do **not** strip Codex attribution here.

## Hard rules

- **Never import or load a real model in tests.** The LLM is always injected as
  `generate(prompt) -> str`; tests pass canned strings. Only `backend.py` and `scripts/bakeoff.py`
  touch real weights, and the test suite must never import them.
- **No network in unit tests.** Use `Store(":memory:")` for store/service tests.
- **`est_minutes` is an int end-to-end** (schema coerces via `int(round(...))`; calibration and
  store assume int) and must be **> 0 and ≤ 25**. A step longer than 25 minutes is invalid and
  feeds the model adapter's repair retry — split bigger work into smaller steps.
- **Roadmap is out of scope.** No reminders, sync, accounts, agent loop, or life-memory KB in the
  MVP. Build only what the current task specifies.

## Conventions (match the surrounding code)

- Python 3.11+; start modules with `from __future__ import annotations`; type-hint public
  functions; use `@dataclass` for record types.
- Terse, skimmable code. Docstrings state the *contract* (what/why), not the obvious.
- Standard library first: `sqlite3`, `statistics`, `json`, `re`. No ORM, no heavy deps. Runtime
  dependencies stay minimal — `gradio` plus the single chosen model backend.
- Tests: `pytest`, one test file per unit, behaviour-named test functions, arrange/act/assert.

## Layout

```
unstuck/
  app.py                       # Gradio entry point (HF Space loads this)
  src/unstuck/
    schema.py                  # Step, Steps, CATEGORIES, validate_steps_payload()
    prompts.py                 # breakdown_prompt(), repair_prompt()
    model_adapter.py           # ModelAdapter.breakdown(task) -> Steps (+ repair retry)
    calibration.py             # multiplier(), calibrate()
    store.py                   # Store (SQLite): tasks/steps/records + export_json()
    service.py                 # Unstuck: breakdown -> calibrate -> store
    backend.py                 # concrete generate() for the chosen model (lazy, never in tests)
  scripts/bakeoff.py           # manual day-1 model bake-off (never imported by tests)
  tests/                       # one test_*.py per unit + test_app_smoke.py
  requirements.txt
  README.md                    # HF Space card + run instructions
  docs/deliverables/           # demo-script.md, social-post.md
```
