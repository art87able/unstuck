# Unstuck — roadmap (post-hackathon)

Ideas and checks for later stages. Not commitments.

## Development backlog (pre-deadline polish, until 2026-06-14)

- [ ] **Task 11 — plan summary + graceful backend errors.** Header chip with the total calibrated time vs the raw AI total ("For you: ~42 min · AI thought 28"), live-updating as steps are logged; catch backend failures (ZeroGPU quota, model errors) in the UI and show a friendly retry message instead of a stack trace.
- [ ] **Task 12 — "Still stuck?" per-step re-breakdown.** A button on any unlogged step that runs the breakdown on that single step's text and splices the resulting sub-steps in place — the core ADHD loop (any step can become the new overwhelming task) closed recursively.
- [x] **Task 15 — built-in step timer** *(done 2026-06-11, `29cebff`: Start stamps the clock,
  Done auto-computes elapsed minutes via `finish_minutes()`; manual entry still wins)*.
- [x] **Task 16 — copy plan as markdown checklist + Enter submits** *(done 2026-06-11,
  `fa1b3ab`: `plan_markdown()` golden-tested; gradio 6 uses `buttons=["copy"]`, not
  `show_copy_button`)*.
- [x] **Task 17 — plan survives page reload** *(done 2026-06-11, `10ce2d4`: single-row
  `plan_snapshot` upsert in SQLite, every row-returning handler persists, `ui.load` restores;
  live E2E verified with a stubbed backend)*.
- [ ] **Demo capture 2026-06-14** — ~90s video per `docs/deliverables/demo-script.md`, recorded in an HF-logged-in browser (anonymous ZeroGPU quota dies mid-demo), then post `docs/deliverables/social-post.md`. Submission deadline 2026-06-15.

## Nebius Serverless AI Builders Challenge (deadline 2026-06-30)

Second competition for the same product — sequenced after the build-small submission (06-15).
Source: nebius.com/serverless-ai-builders-challenge (May 26 – Jun 30, winners Jul 9; $100 credits
per valid submission, up to $2,000 top prizes; Special Award categories include **Agentic AI
Workflows** — the Codex-driven build story fits, as does Unstuck itself).

- [x] **Task 13 — `UNSTUCK_BACKEND=nebius`** *(code done 2026-06-11, `443792b`: InferenceClient
  with `NEBIUS_BASE_URL` (default `https://api.studio.nebius.com/v1/`, env-overridable) +
  `NEBIUS_MODEL` + required `NEBIUS_API_KEY`; 3 new mocked tests, suite 37 green)*. **Live
  verification still needed once Artur has a Nebius account + API key** — confirm the base URL
  and that the Qwen3-4B model id is served, then run one real `generate()`.
- [ ] **Submission writeup** — "one app, three serving backends" is exactly the documented,
  openly-shared reference example the challenge asks for; reuse the field notes + agent-trace
  dataset + the teaching guide.
- [ ] Verify entry mechanics on the challenge page (registration form, what counts as a valid
  submission) — *[claim needs source: page is a thin landing; mechanics likely behind a form]*.

## To investigate

- [ ] **Apple Foundation Models — free Private Cloud Compute inference (WWDC 2026).** Apple announced free access to Apple Foundation Models running on **Private Cloud Compute** (stateless Apple Silicon servers, no data retention) for developers with **<2M first-time App Store downloads** — no per-token/infrastructure cost. The Foundation Models framework also gained image input, server-side third-party model routing (Claude/Gemini via the same Swift API, swappable via an SPM dependency), multi-agent "Dynamic Profiles", and goes open source later this summer. *Why for Unstuck:* later-stage native iOS/macOS client could run hint generation at zero inference cost — on-device for simple queries, auto-escalating to PCC for complex ones — replacing or backing up the ZeroGPU/HF-inference backends; the third-party routing even keeps a path to stronger models without code changes. Verify: model capability vs `Qwen/Qwen3-4B-Instruct-2507`, guided-generation support, eligibility mechanics for the <2M-downloads free tier, OS requirements. Sources: [MacRumors](https://www.macrumors.com/2026/06/09/apple-outlines-major-ai-and-developer-tool-updates/), [WWDC26 session 241](https://developer.apple.com/videos/play/wwdc2026/241/), [TechTimes](https://www.techtimes.com/articles/318039/20260609/wwdc-2026-developer-tools-foundation-models-now-swaps-ai-providers-without-code-changes.htm). *(as of 2026-06-10)*
