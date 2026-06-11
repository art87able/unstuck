# Unstuck — roadmap (post-hackathon)

Ideas and checks for later stages. Not commitments.

## Development backlog (pre-deadline polish, until 2026-06-14)

- [ ] **Task 11 — plan summary + graceful backend errors.** Header chip with the total calibrated time vs the raw AI total ("For you: ~42 min · AI thought 28"), live-updating as steps are logged; catch backend failures (ZeroGPU quota, model errors) in the UI and show a friendly retry message instead of a stack trace.
- [ ] **Task 12 — "Still stuck?" per-step re-breakdown.** A button on any unlogged step that runs the breakdown on that single step's text and splices the resulting sub-steps in place — the core ADHD loop (any step can become the new overwhelming task) closed recursively.
- [ ] **Demo capture 2026-06-14** — ~90s video per `docs/deliverables/demo-script.md`, recorded in an HF-logged-in browser (anonymous ZeroGPU quota dies mid-demo), then post `docs/deliverables/social-post.md`. Submission deadline 2026-06-15.

## To investigate

- [ ] **Apple Foundation Models — free Private Cloud Compute inference (WWDC 2026).** Apple announced free access to Apple Foundation Models running on **Private Cloud Compute** (stateless Apple Silicon servers, no data retention) for developers with **<2M first-time App Store downloads** — no per-token/infrastructure cost. The Foundation Models framework also gained image input, server-side third-party model routing (Claude/Gemini via the same Swift API, swappable via an SPM dependency), multi-agent "Dynamic Profiles", and goes open source later this summer. *Why for Unstuck:* later-stage native iOS/macOS client could run hint generation at zero inference cost — on-device for simple queries, auto-escalating to PCC for complex ones — replacing or backing up the ZeroGPU/HF-inference backends; the third-party routing even keeps a path to stronger models without code changes. Verify: model capability vs `Qwen/Qwen3-4B-Instruct-2507`, guided-generation support, eligibility mechanics for the <2M-downloads free tier, OS requirements. Sources: [MacRumors](https://www.macrumors.com/2026/06/09/apple-outlines-major-ai-and-developer-tool-updates/), [WWDC26 session 241](https://developer.apple.com/videos/play/wwdc2026/241/), [TechTimes](https://www.techtimes.com/articles/318039/20260609/wwdc-2026-developer-tools-foundation-models-now-swaps-ai-providers-without-code-changes.htm). *(as of 2026-06-10)*
