# Unstuck — roadmap (post-hackathon)

Ideas and checks for later stages. Not commitments.

## Development backlog (pre-deadline polish, until 2026-06-14)

- [x] **Task 11 — plan summary + graceful backend errors** *(verified done 2026-06-13 audit:
  header chip "For you: ~X min total · AI estimate: Y min" renders from `plan_summary` (app.py:326)
  and re-renders from every handler; backend failures surface as `gr.Warning("The model backend
  is busy...")` (app.py:581) — no stack traces reach the UI; suite 141 green)*.
- [x] **Task 12 — "Still stuck?" per-step re-breakdown** *(verified done 2026-06-13 audit:
  button on the spotlighted step (app.py:1082) splices tiny-granularity sub-steps in place;
  was delivered as part of wave 8's "'Still stuck?' always tiny" thread)*.
- [x] **Task 15 — built-in step timer** *(done 2026-06-11, `29cebff`: Start stamps the clock,
  Done auto-computes elapsed minutes via `finish_minutes()`; manual entry still wins)*.
- [x] **Task 16 — copy plan as markdown checklist + Enter submits** *(done 2026-06-11,
  `fa1b3ab`: `plan_markdown()` golden-tested; gradio 6 uses `buttons=["copy"]`, not
  `show_copy_button`)*.
- [x] **Task 17 — plan survives page reload** *(done 2026-06-11, `10ce2d4`: single-row
  `plan_snapshot` upsert in SQLite, every row-returning handler persists, `ui.load` restores;
  live E2E verified with a stubbed backend)*.
- [x] **Task 18 — "Your patterns" stats panel** *(done 2026-06-11: per-category multiplier +
  verdict + last-5 mini bar strip in a collapsed accordion; refreshed from every handler)*.
- [x] **Task 19 — progressive reveal** *(done 2026-06-11: first unlogged step spotlighted with
  full controls, later steps dimmed and control-free — anti-overwhelm by construction)*.
- [x] **Tasks 20–22 — New plan, Skip step, completion banner** *(done 2026-06-11: clear board + snapshot; skip resolves without polluting calibration; honest-stats banner; suite 77 green)*.
- [x] **Task 23 — per-user data via gr.BrowserState** *(done 2026-06-11: plans + calibration
  records moved to browser localStorage — multi-user isolation + the privacy headline; server
  SQLite keeps only task/step bookkeeping; suite 88 green, live E2E verified)*.
- [x] **Task 24 + wave 8 — step-size control, mobile polish, calibration regression fix,
  docs refresh** *(done 2026-06-11: chunky/regular/tiny granularity threaded UI→service→prompt
  ("Still stuck?" always tiny); responsive CSS ≤640px; fixed fresh-breakdown calibration to
  read browser records (regression from Task 23, launch-test guarded); demo script / social
  post / nebius writeup updated; suite 99 green)*.
- [x] **Tasks 25–27 — quality gates, Undo, edit/add steps** *(done 2026-06-11: validator
  rejects vague/duplicate/rambling steps (each rejection drives the repair retry);
  granularity-matched few-shot examples; Undo reverses Done/Skip incl. the calibration
  record; edit any step + add your own; suite 121 green)*.
- [x] **Wave 10 — model-layer reliability** *(done 2026-06-11, `490b521`: JSON prefill on the
  ZeroGPU backend (assistant turn starts `{"steps":[` — no prose/fence possible);
  `raw_decode`-scan JSON extraction (greedy regex died on trailing prose with braces);
  second few-shot example per granularity so creative/deep-work categories appear;
  granularity-aware first-step rule (chunky's contradictory 5-min starter demand removed);
  repair prompt carries the example + truncates rambling output; 3 new vague-starter gates;
  suite 133 green. **Needs a live Space smoke test after upload** — the prefill path only
  runs on GPU)*.
- [x] **Competitor scan (2026-06-11).** 100+ entries in the org. Closest: NeuroBait (ADHD
  *chatbot* companion, gemma-12B LoRA, 4 likes) — different lane (conversation vs structured
  tool); exam-panic-rescue (multi-model badge-maximalist). Top of field: field-guide (15♥),
  her (12♥), lolaby (10♥). Action taken: README badge/track tags added (we had a bare tag
  set; every serious entry advertises badges via tags). Unstuck at 0 likes — visibility is
  Artur's lever (post + Discord + likes beget likes).
- [x] **Competitor scan #2 (2026-06-13).** Re-pulled the org by likes. New leaderboard:
  aether-garden (20♥, agent sim/persistent-world, track:wood), field-guide (19♥), small-talk
  (19♥, voice robot), her (18♥, companion), PITCHFIGHT_AI (15♥), lolaby (12♥). **Two findings:**
  (1) **Tag format was wrong** — every ranking entry uses *namespaced* tags (`track:backyard`,
  `achievement:offbrand|fieldnotes|sharing`); we had the plain-text variants (`off-brand`,
  `field-notes`, `sharing-is-caring`) and **no `track:` tag**, so we were invisible to the badge/
  track filters judges browse by. **Fixed**: added the canonical namespaced tags (all four
  genuinely earned) + `short_description` leading with the calibration hook. ⚠️ **Only takes
  effect after the Space README re-sync** (Artur's pending one-liner). (2) **Likes flow to
  delight** (games/companions), not utility — our whole lane (NeuroBait, exam-panic-rescue, sema,
  sokrates, ai-study-buddy) all sit at 2–4♥. So likes aren't our win condition; **badges + an
  honest judged demo are.** Our only un-owned differentiator vs the lane is the *time-blindness
  self-calibration* — now the headline in title/description.
- [ ] **Open badge opportunity — `achievement:offgrid`** (her, exam-panic, sema all claim it):
  needs a *real* local path (llama.cpp / GGUF of Qwen3-4B, no cloud). Don't fake the tag — it
  requires a genuine on-device `generate()` backend. Candidate Wave-13 task; honest to claim only
  once shipped. (`sponsor:openai` is arguable via the Codex build but is about submission models,
  not dev tooling — left unclaimed to avoid badge-stuffing.)
- [ ] **Demo capture 2026-06-14** — ~90s video per `docs/deliverables/demo-script.md`, recorded in an HF-logged-in browser (anonymous ZeroGPU quota dies mid-demo), then post `docs/deliverables/social-post.md`. Submission deadline 2026-06-15.

## Wave 12 — virality + post-deadline candidates (expanded 2026-06-13)

- [x] **Task 31 — "Copy share update"** *(done 2026-06-13: `share_text()` builds a
  paste-anywhere progress line — complete plans get the honest brag ("Got unstuck: …
  N steps in M min (the AI guessed G)"), in-progress plans get "d of N steps done,
  ~R min to go", both ending with the Space link; button beside "Copy as checklist",
  same copy-textbox pattern; 4 golden tests, suite 145 green)*. Rationale: likes are
  the visibility lever — give users a one-click way to talk about Unstuck.
- [x] **Task 32 — .ics export** *(done 2026-06-13: `plan_ics(task, rows, start)` emits a
  VCALENDAR with one VEVENT per unlogged/non-skipped step, calibrated-minute DURATIONs,
  back-to-back from `start`; floating local times (no TZID/Z) so blocks import in the
  reader's own zone; RFC 5545 text escaping + CRLF; button writes a temp .ics to a
  `gr.File`. 3 golden tests, suite 148 green)*. The plan lands where a time-blind brain
  actually looks — closes the loop from "overwhelming task" to "blocked on my calendar".
- [x] **Task 33 — restored-plan banner** *(done 2026-06-13: `restored_banner_html(rows)`
  prepends "&#8617; Restored your plan from earlier — N steps left" to the summary on
  `ui.load`; self-clears on the next action (handlers recompute summary without it);
  hidden when the plan is complete or empty; singular/plural correct. 3 tests, suite
  151 green)*.
- [ ] **Task 34 — streak microcopy.** After each Done, rotate 3-4 short encouragements
  keyed to calibration honesty ("14 min vs 6 guessed — noted, adjusting"), not generic
  praise. Keep it one line; ADHD-safe (no guilt language).
- [ ] **Task 35 — "stuck heatmap" insight.** In Your patterns: which *category × step
  position* most often gets skipped or re-broken — surfaces what kind of step the user
  actually stalls on. Needs ≥10 records before showing.
- [ ] **Task 36 — PWA wrapper** (post-hackathon): manifest + service worker on a thin
  static host pointing at the Space, so Unstuck installs to a phone home screen.
- [ ] **Task 37 — Apple Private Cloud Compute spike** (parked from earlier): check the
  WWDC 2026 small-dev free-inference tier as a later backend for `generate()`.

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
