# Phase 1 — Similar-task recall (Nebius embeddings) with reuse-breakdown + light shake-off

**Gist:** When you paste a task, embed it on Nebius serverless, recall your most-similar *past* task, and use it to (a) seed task-specific time estimates from what that task *actually* took and (b) shape the new breakdown with the past good breakdown as a one-shot exemplar — always as a visible, easily-dismissed suggestion that auto-stops recurring after two dismissals.

- **Date:** 2026-06-15
- **Status:** Approved design, pre-implementation
- **Repo:** `art87able/unstuck`
- **Targets at once:** Build-small hackathon (still on) · Nebius Serverless AI Builders Challenge (Artur's motivation note; no external judging criteria captured) · Unstuck-as-product

---

## 1. Why — the "gets smarter, stays small" flywheel

Unstuck already has a model seam (`generate(prompt) -> str`, env-selected) with four backends incl. `nebius` (Token Factory, `Qwen3-30B-A3B`). "Add a Nebius backend" is **done**. This is a *new feature that leverages Nebius's catalog* rather than just consuming chat.

The chosen direction combines two of Artur's candidate ideas into one loop, where the first produces the fuel for the second:

```
   paste task ──► embed (Nebius) ──► recall similar past task
                                          │
                                          ▼
              seed task-specific estimates + reuse good breakdown      ◄── Phase 1 (this spec)
                                          │
                       (accumulates: task → good breakdown → real durations)
                                          │
                                          ▼
        LoRA-fine-tune a small model on that corpus, serve serverless   ◄── Phase 2 (own spec, later)
```

**Why it fits every target at once:**
- **Build-small:** every model is *small* — a small embedding model now, a small fine-tuned chat model in Phase 2.
- **Nebius showcase:** uses the catalog across **three** capabilities — chat (shipped), **embeddings** (this phase), fine-tune+serve (Phase 2).
- **ZeroGPU 40 min/day cap:** all new intelligence runs on **Nebius serverless**, so it never draws on the scarce ZeroGPU budget. This is the honest narrative for *why Nebius*, not merely *that Nebius* — and it keeps a live demo well under the 2-min GPU window.
- **Privacy stays structural:** only task *text* crosses to Nebius (the boundary the breakdown prompt already crosses); vectors + history stay in the browser; similarity is computed ephemerally, never persisted server-side.

## 2. Scope

**In scope (Phase 1):** the embedding seam, the recall selection logic, exemplar-shaped breakdowns, estimate seeding from real past durations, and the shake-off mechanism. Everything runs on canned strings/vectors in tests; one tiny live embedding call is the only billed check.

**Out of scope / deferred:**
- **Phase 2 (fine-tune + serve):** depends on a harvested corpus; gets its own spec→plan cycle. Not dropped, sequenced.
- **Persistent recall scoring / reinforcement / decay:** explicitly rejected in favour of the lightest shake-off (see §6). YAGNI.
- **Cross-device recall:** history is per-browser `localStorage`, same as today. No server-side store.

## 3. Architecture — new pieces mirror the existing seam discipline

The codebase keeps the model boundary as one env-selected seam with mocked, network-free tests. Recall needs a *second* Nebius capability (embeddings), so it gets its own parallel seam, plus a pure selection function.

| New module | Contract | Tested how |
|---|---|---|
| `src/unstuck/embeddings.py` | `embed(text: str) -> list[float]`. Branch-selected by `UNSTUCK_EMBED_BACKEND` (default `nebius`). Nebius branch hits Token Factory embeddings with `NEBIUS_EMBED_MODEL` (default **`Qwen/Qwen3-Embedding-0.6B`** — small, "built small"; exact catalog id confirmed at plan time). Lazy import, env key read at import, same shape as `backend.py`. | mock the client, assert base_url / key / model / call shape, return a canned vector; **zero network** |
| `src/unstuck/recall.py` | **Pure**: `select(new_vec, history) -> Match or None`. Returns the highest-cosine record above `RECALL_THRESHOLD`, **skipping any with `dismissals >= 2`**; `None` on empty history or no match. No I/O. | pure unit tests; zero network |

**Changes to existing files (small, additive — preserve current behaviour when there is no match):**

- `prompts.py` — `breakdown_prompt(task, granularity, exemplar=None)` gains an optional `exemplar` slot that injects the matched task's past breakdown as **one** extra few-shot example after the static `EXAMPLES`. `exemplar=None` → byte-for-byte today's prompt.
- `service.py` + `model_adapter.py` — `breakdown(...)` gains an optional `exemplar` **passthrough** param threaded down to `breakdown_prompt`. These layers do *not* orchestrate recall. (Refined from the original draft: orchestration moved to the handler — see next bullet — because that is where `gr.BrowserState` lives and where breakdown + recalibration already run.)
- **`app.py` `break_down` handler orchestrates the loop** (`embed` → `recall.select` → exemplar prompt + estimate seeding + banner; else today's path unchanged). The per-session SQLite `Store` is not recall's home: `Store.import_json` only round-trips calibration *records* (category/est/actual), not task text + breakdowns.
- **History persists as a new `gr.BrowserState` key** — `data["history"]`, a list of entries `{text, embedding, breakdown, durations, dismissals}`, mirroring the existing `records` / `plan` keys with pure helpers (`make_history_entry`, `with_history`, `_history_from_data`, `bump_dismissal`). The BrowserState default becomes `{"records": [], "plan": None, "history": []}`; older saved state without the key is treated as empty history.

## 4. Data flow (one paste)

1. **Embed** the task text via `embed()` (Nebius serverless).
2. **`recall.select(vec, history)`** → `Match m` or `None` (records with `dismissals >= 2` excluded).
3. **Matched (`m`):** breakdown via `breakdown_prompt(task, granularity, exemplar=m.breakdown)`; seed each new step's estimate from `m`'s **real** per-step durations where the step category aligns, else fall back to the existing category calibration multiplier. Render with the recall banner (§6).
   **No match:** today's normal flow, untouched — no banner.
4. **"Start fresh"** (§6) → regenerate with `exemplar=None` **and** `m.dismissals += 1` (persisted to BrowserState). At 2, `recall.select` will never return `m` again.
5. **On completion**, persist the new task as `{text, embedding, breakdown, durations, dismissals: 0}` into history.

## 5. Estimate seeding rule

The differentiator today is honest, category-wide calibration (`median(actual / estimated)` per category). Recall makes it *task-specific* without dishonesty:

- For each new step, if the matched task has a completed step of the **same category**, seed the estimate from that step's **actual** duration.
- Otherwise fall back to the existing category calibration multiplier (current behaviour).
- Seeded estimates remain subject to the 25-min cap and the existing schema gate. Skipped/dismissed steps never contribute durations (unchanged rule).

## 6. Shake-off — "start fresh" + auto-exclude after 2 dismissals (no persistent score)

The risk introduced by reusing a past breakdown: a stale or bad pattern becomes **sticky** — recalled forever just because the new task is textually similar — railroading the user. The mechanism that lets you shake it off is what makes reuse-breakdown safe, and it is deliberately the lightest possible:

- **Recall is a labelled suggestion, never silent.** The exemplar-shaped breakdown appears under a banner: *"Shaped by a similar task from {date} · [start fresh instead]"*.
- **One tap on "start fresh"** discards the recall, regenerates with no exemplar, and increments that record's `dismissals`.
- **Auto-exclude at 2 dismissals.** Once `dismissals >= 2`, `recall.select` permanently skips that record as an exemplar. (Its *real durations* may still feed category calibration — that signal is always honest.)
- **No persistent helpfulness score, no reinforcement, no decay.** Just a counter and a threshold.

## 7. Error handling — recall is strictly additive

Recall must never block or break the core flow. Every failure mode degrades silently to the **normal breakdown** (no banner):

- Embedding call fails (network / quota / timeout) → degrade.
- **Missing embed key** (`NEBIUS_API_KEY` unset with `UNSTUCK_EMBED_BACKEND=nebius`) → recall **disabled gracefully**, *not* a hard raise. (Contrast: the core `nebius` *chat* backend hard-raises because it is load-bearing; embeddings are optional.)
- Cold start (empty history) or sub-threshold similarity → no match → normal flow.
- Malformed history record (e.g. imported without `embedding`) → treated as non-matchable.

## 8. Defaults

| Knob | Default | Note |
|---|---|---|
| `RECALL_THRESHOLD` (cosine) | `0.80` | tunable; start conservative to avoid weak matches |
| Missing embed key | **degrade** (recall off) | not a raise |
| `UNSTUCK_EMBED_BACKEND` | `nebius` | a `none` branch returns no embedding → recall disabled (offline/tests) |
| `NEBIUS_EMBED_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | small; exact catalog id confirmed at plan time |
| `dismissals` exclude-at | `2` | |

## 9. Testing strategy ("tested without billing" identity)

- `tests/test_embeddings.py` — mock the embedding client: assert base_url / key / model / `/v1/embeddings` call shape; canned vector returned; missing-key → recall-disabled path (no raise). Zero network.
- `tests/test_recall.py` — pure: match above/below threshold; highest-cosine wins; ties; `dismissals >= 2` excluded; empty history → `None`. Zero network.
- `tests/test_service.py` (extend) — matched path builds the exemplar prompt and seeds estimates; unmatched path is byte-identical to today; "start fresh" increments `dismissals` and drops the exemplar; after 2 dismissals the record is never selected. Canned strings/vectors only.
- Full suite stays green and network-free; the only live check is one ~few-token embedding call, mirroring the chat backend's live check.

## 10. Open items to resolve at plan time (not design risks)

1. **Embedding call mechanism.** Confirm whether `huggingface_hub.InferenceClient` routes embeddings to Token Factory's `/v1/embeddings` (e.g. via `feature_extraction`) or whether a minimal direct call to `/v1/embeddings` is cleaner. **Prefer the no-new-dependencies story** (`huggingface_hub` is already a dep); verify it actually hits the OpenAI-compatible embeddings route, else use a small direct POST. Capture the resolved shape in the plan.
2. **Exact embedding model id** in the Token Factory catalog (Qwen3-Embedding family: 0.6B / 4B / 8B — pick the smallest available).
3. **Cosine in Python vs numpy** — keep it dependency-light (pure-Python dot/norm is fine for a handful of vectors held in a browser session).

## 11. Cleanup folded in (stale submission doc)

`docs/deliverables/nebius-submission.md` is stale and should be corrected when this lands: "three backends" → **four** (+`offgrid`), "99 tests" → current count, and its base-URL (`api.tokenfactory.nebius.com`) vs PROMPTS.md Task 13's outdated default (`api.studio.nebius.com`) reconciled to the shipped value.

## 12. Phase 2 forward pointer (not this spec)

Once Phase 1 has harvested a `{task → good breakdown → real durations}` corpus, Phase 2 LoRA-fine-tunes a small Qwen on Token Factory and serves the adapter serverlessly by pointing `NEBIUS_MODEL` at it. **Privacy boundary:** Phase 2 trains on *public/synthetic* breakdown data (or the published agent-trace dataset), **not** the user's private `localStorage` history. Its own spec will detail data prep, the train run, and the eval (base vs fine-tuned).
