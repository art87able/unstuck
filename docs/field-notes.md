# Field Notes — building Unstuck small, with an agent driving an agent

*Build Small Hackathon, June 2026 · [Space](https://huggingface.co/spaces/build-small-hackathon/unstuck) · [Source](https://github.com/art87able/unstuck)*

## What I built

**Unstuck** is an ADHD task assistant. You paste one overwhelming task; a ≤4B model
(`Qwen/Qwen3-4B-Instruct-2507`) breaks it into tiny, timed, categorised steps — each capped at
25 minutes, small enough to start without planning your whole afternoon.

The differentiator is the part with **no AI in it**: a deterministic calibration layer. You log
how long steps *actually* took, and Unstuck computes a per-category bias multiplier —
`median(actual / estimated)` over your history — and shows a "for you" estimate next to the raw
AI estimate. It doesn't pretend you got faster. It makes the plan honest about your
time-blindness.

## How it was built: an agent driving an agent

The code was written by the **OpenAI Codex CLI**, driven and reviewed by **Claude Code**, one
task at a time:

- A per-task prompt pack ([`PROMPTS.md`](../PROMPTS.md)) splits the build into 10 scoped tasks.
  Each prompt names the only files that task may touch, demands a failing test first, and states
  the exact expected test count.
- Each task ran as a single one-shot `codex exec` in a `workspace-write` sandbox. The sandbox
  write-protects `.git` — which turned out to be a feature: Codex codes and tests, then the
  reviewing agent independently re-runs the suite, reads the diff, and commits with
  `--author="Codex"`. Every commit is a review gate.
- [`AGENTS.md`](../AGENTS.md) is Codex's always-loaded contract (what `CLAUDE.md` is to Claude
  Code): architecture, model lock, test rules.

The result: 10 tasks, 24 tests green throughout, and a commit trail where every change is
attributable and auditable.

## What I learned

### 1. Inject the LLM, test everything else with strings

The model enters the system as one seam: a `generate(prompt) -> str` callable, injected
everywhere. All logic — schema validation, JSON repair retry, calibration math, SQLite store —
is unit-tested with canned model output. No test downloads a model; `backend.py` is the only
module that touches real weights and is never imported by the suite. This is why a 4B model app
could be built test-first by a coding agent that never had a GPU.

### 2. Small models need a validator and one repair retry

Qwen3-4B mostly returns clean JSON, but "mostly" isn't an engineering plan. The adapter
validates the payload (step list non-empty, category in enum, `0 < est_minutes ≤ 25`) and on
failure sends exactly one repair prompt containing the validation error. One retry caught
essentially everything in testing; unbounded retry loops are where token budgets go to die.

Three refinements that compounded later: **prefill the assistant turn** with `{"steps":[` on the
local-weights backend, so the model physically cannot open with prose or a markdown fence — it
can only continue the JSON object. Extract with `json.JSONDecoder.raw_decode` scanning from each
`{` instead of a greedy `\{.*\}` regex: the regex silently fails the moment the model appends a
trailing sentence containing a brace, which is exactly the failure mode prose-y small models
produce. And few-shot examples need to *cover the label space*: with a single cleaning-task
example the model almost never used the `creative` or `deep-work` categories; a second example
from a different domain fixed the distribution.

### 3. ZeroGPU has a shape, and fighting it costs you a deploy each time

Three production bugs, all found via the Space run logs, none caught by the (CPU-only) test
suite:

- **`device_map="cuda"` breaks ZeroGPU.** Accelerate's dispatch path bypasses ZeroGPU's torch
  monkey-patch. Plain module-scope `.to("cuda")` is the supported pattern.
- **`apply_chat_template` returns a `BatchEncoding`** in current transformers — pass
  `return_dict=True` and unpack with `**inputs` into `generate()`, or you get an
  `AttributeError` deep inside the GPU worker with no client-visible traceback.
- **Gradio handlers run on worker threads.** A module-scope `sqlite3` connection created on the
  main thread throws `ProgrammingError` on first real request. `check_same_thread=False` plus a
  lock fixes it.

Meta-lesson: the ZeroGPU worker reports only the exception class to the client. Pull the
**run logs** (`/api/spaces/{id}/logs/run`) for the actual traceback before guessing.

### 4. Ephemeral Spaces change your persistence design

Spaces have no persistent disk, so a bare SQLite file dies with the container. For an MVP the
honest answer is in-memory SQLite plus an **Export** button — tell users their data is theirs to
keep, rather than silently losing it.

### 5. Small is a feature

Staying ≤4B wasn't just for the constraint. It means the core experience is self-hostable, the
privacy story is real (the default backend keeps task text on the Space's GPU), and the
calibration layer — plain Python and a median — carries the product weight the model can't.

### 6. Measure the pipeline, then believe it

A 12-task × 3-granularity eval through the real adapter pipeline (HF serverless,
`Qwen3-4B`, temperature 0, one repair allowed) — run with
[`scripts/eval_quality.py`](../scripts/eval_quality.py):

| granularity | valid | first-try | repairs | >cap minutes | avg steps | categories seen |
|---|---|---|---|---|---|---|
| chunky | 12/12 | 12/12 | 0 | 0 | 4.0 | admin, creative, deep-work, errand |
| regular | 12/12 | 12/12 | 0 | 0 | 5.1 | admin, creative, deep-work, errand |
| tiny | 11/12 | 11/12 | 0 | 0 | 6.4 | admin, creative, deep-work, errand |

Two things the table bought us beyond a number to quote. It **confirmed the few-shot
label-space fix** (all four categories now appear at every granularity — before wave 10,
`creative` and `deep-work` never showed). And the single failure was a *finding, not noise*:
the model corrupted JSON mid-string (switched quote style after an apostrophe in a folder
name), and the extraction scan happily decoded an **inner step object** as the whole payload —
so the repair prompt carried a misleading "payload must include non-empty steps" diagnosis.
Fix: prefer a decoded object that actually has a `"steps"` key. An eval that only reported a
score would have hidden that; keeping the failing raw output is what made it debuggable.

### 7. Degrade loudly, fall back quietly

The live smoke test showed anonymous ZeroGPU quota can be **zero** — a judge clicking the
Space gets a friendly error and never sees a plan. The fix wasn't a bigger GPU; it was the
seam again: `generate()` is one callable, so a `with_fallback(primary, fallback)` wrapper
gives every visitor a plan — ZeroGPU when they have quota, HF serverless (via the Space's
`HF_TOKEN` secret) when they don't. Decoding temperature became `UNSTUCK_TEMPERATURE` at the
same time: greedy stays the measured default; sampling is one env var away, gated on re-running
the eval, not on vibes.

Re-ran at `UNSTUCK_TEMPERATURE=0.3`: identical headline (35/36 valid, all first-try, zero
cap violations), marginally better deep-work coverage. Verdict: greedy stays the code
default; 0.3 is eval-cleared for the live Space so repeated demo runs don't produce
byte-identical plans.
