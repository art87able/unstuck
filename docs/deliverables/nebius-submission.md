# Unstuck — one app, four serving backends

*Nebius Serverless AI Builders Challenge, June 2026 · [Source](https://github.com/art87able/unstuck) · [Live demo Space](https://huggingface.co/spaces/build-small-hackathon/unstuck) · [Agent-trace dataset](https://huggingface.co/datasets/build-small-hackathon/unstuck-agent-trace)*

> **Draft — final submit by Artur before 2026-06-30.** Fill in: the entry-form fields the
> challenge asks for, and a screenshot/GIF of the app running on the Nebius backend.

## What it is

**Unstuck** is an ADHD task assistant. Paste one overwhelming task; a small instruct model
breaks it into tiny, timed, categorised steps (chunky/regular/tiny granularity) — each capped
at 25 minutes, the first one always a small starter action (the task-initiation hook). Only the
next step is "live" (progressive reveal); a built-in timer measures each step (Start → Done) so
the user never self-tracks; any step can be recursively re-broken-down in place; skipped steps
are excluded from the data. The differentiator has **no AI in it**: a deterministic calibration
layer logs how long steps *actually* took and computes a per-category bias multiplier —
`median(actual / estimated)` — so the plan is honest about your time-blindness, with the
history visible in a "Your patterns" panel. Privacy is structural: plans and calibration
records live in the **browser's localStorage**, never server-side; export/import gives the full
data round-trip.

## The serverless part: one seam, four backends

The model enters the system as exactly one seam — `generate(prompt) -> str` — selected by an
environment variable. That seam is the whole reference-example story: **the same app, untouched,
runs against four completely different serving stacks**, including Nebius serverless inference.

| `UNSTUCK_BACKEND` | Serving stack | When |
|---|---|---|
| `zerogpu` | local weights on a shared GPU slice (HF Spaces) | default, privacy-first |
| `hf_inference` | HF serverless Inference Providers | CPU-only fallback |
| `nebius` | **Nebius Token Factory** — OpenAI-compatible serverless inference | this challenge |
| `offgrid` | local quantised GGUF via llama.cpp — fully on-device, no network | offline / privacy |

The Nebius branch is ~20 lines:

```python
client = InferenceClient(
    base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
    api_key=os.environ["NEBIUS_API_KEY"],
)

def generate(prompt: str) -> str:
    response = client.chat_completion(
        model=NEBIUS_MODEL,  # default: Qwen/Qwen3-30B-A3B-Instruct-2507
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0,
    )
    return str(response.choices[0].message.content)
```

Model choice: `Qwen/Qwen3-30B-A3B-Instruct-2507` — a Mixture-of-Experts model with only **3B
active parameters** per token, so the "built small" constraint survives the move to serverless:
big-catalog quality at small-model serving cost.

Run it:

```bash
UNSTUCK_BACKEND=nebius NEBIUS_API_KEY=… python app.py
```

## Beyond chat: similar-task recall on Nebius embeddings

This entry adds a **second** Nebius capability beyond chat. When you paste a task, Unstuck embeds
it via Token Factory's OpenAI-compatible `/v1/embeddings` (a small `Qwen3-Embedding` model) and
recalls your most-similar past task. The match shapes the new breakdown two ways: its past good
breakdown is injected as a one-shot exemplar, and your *real* recorded durations seed
task-specific time estimates instead of the category-wide average. Recall is always a labelled,
dismissable suggestion — hit **Start fresh** and, after two dismissals, that task is never
recalled again.

Two properties matter for this challenge:

- **Zero ZeroGPU cost.** Embeddings run on Nebius serverless, so recall never touches the scarce
  ZeroGPU quota — the demo stays well within the free GPU budget. The Nebius backend isn't just
  an alternative; it's what makes the smart features affordable under the GPU cap.
- **Privacy stays structural.** Only the task *text* crosses to Nebius (the boundary the
  breakdown prompt already crosses); embedding vectors and history live only in the browser's
  localStorage, and cosine similarity runs ephemerally per request.

## Why this is a useful reference example

1. **The seam pattern.** Most LLM apps hard-wire their provider. The env-selected
   `generate(prompt) -> str` boundary means the choice of serving stack is a deploy-time
   decision, not an architecture decision — and the entire logic suite (179 tests) runs on canned
   strings and vectors with zero network and zero GPU.
2. **Schema gate + one repair retry.** Small serverless models return *almost*-right JSON; the
   app validates every response (`0 < est_minutes ≤ 25`, category enum) and spends at most one
   corrective round-trip — a budget-respecting pattern for any pay-per-token backend.
3. **Tested without billing.** The Nebius branch ships with fully-mocked unit tests (fake
   `InferenceClient`, asserts base URL / key / params); the live check is a single ~10-token
   call. Credits are spent on users, not CI.
4. **Documented, openly shared.** Full build history (an agent driving an agent, TDD prompt
   packs, per-task commits) is public: the repo, the field notes, and an agent-trace dataset.

## Built small, in the open

The app was written by the OpenAI Codex CLI driven and reviewed by Claude Code — 24 scoped
TDD tasks, each a written spec with a failing-test-first contract, every commit independently
reviewed. The process itself is documented in
[`docs/field-notes.md`](../field-notes.md) and the
[agent-trace dataset](https://huggingface.co/datasets/build-small-hackathon/unstuck-agent-trace).
The similar-task recall feature in this entry was built the same way — Codex implemented each of
10 TDD tasks, with every task spec-reviewed, green-gated against the full suite, and committed by
Claude Code.

*Special-award fit: Agentic AI Workflows (the agent-driving-agent build) · AI & ML (the app).*
