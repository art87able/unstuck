# Unstuck — Codex Prompt Pack

Per-task prompts for building Unstuck with the **OpenAI Codex CLI**. The Codex Track judges
*how well you used Codex*, so these prompts are part of the submission — keep them tight and scoped.

## How to run this

- **One task at a time.** Run Codex on exactly one prompt below, as a single one-shot run — not a
  long agentic session. This keeps token use low and produces a clean, auditable per-task commit
  trail (the actual showcase for the Codex Track).
- **Review between tasks.** After each run, read the diff and the test output before starting the
  next prompt. Confirm the named files (and only those) changed and the stated test command passes.
- **No scope creep.** Each prompt names the only files that task may touch and the only commit it
  may make. If Codex wants to do more, stop and re-scope.
- **Attribution:** Codex-attributed commits are permitted **in this repo only** (Codex Track rule).
  Let Codex author and attribute its own commits here; do not strip that attribution.
- **Order matters.** Run Task 0 → Task 9 in sequence; later tasks import earlier modules.
- Run from the `unstuck/` repo root. Source lives under `src/unstuck/`; tests under `tests/`.

---

## Task 0 — Project scaffold

```
Implement ONLY the project scaffold for Unstuck. Touch only these files: requirements.txt,
src/unstuck/__init__.py, tests/__init__.py, pytest.ini.

1. Create requirements.txt with exactly:
       gradio>=4.44
       pytest>=8.0
   (Do NOT add a model backend dep — that comes in a later task.)
2. Create the package + test init files:
       mkdir -p src/unstuck tests scripts docs/deliverables
       printf 'from __future__ import annotations\n' > src/unstuck/__init__.py
       : > tests/__init__.py
3. Create pytest.ini with:
       [pytest]
       pythonpath = . src
       testpaths = tests
4. Verify config loads — run: python -m pytest -q
   Expected: "no tests ran" (exit code 5). This is success, not failure.
5. Commit with message: "chore: project scaffold (pytest, package layout)"
   Stage only: requirements.txt src/unstuck/__init__.py tests/__init__.py pytest.ini

Do not write any application code. Make exactly one commit, authored and attributed by Codex.
```

---

## Task 1 — Step schema + validator

```
Implement ONLY the step schema. Touch only: src/unstuck/schema.py and tests/test_schema.py.
Follow TDD strictly: failing test first, then implementation.

1. Write tests/test_schema.py covering: a valid payload parses (est_minutes coerced to int),
   missing "steps" key raises StepValidationError, empty steps list raises, a bad category raises,
   a non-positive estimate raises, an estimate over 25 minutes (e.g. 40) raises, blank/whitespace
   text raises, and CATEGORIES equals {"admin","creative","errand","deep-work"}. Import from
   unstuck.schema: validate_steps_payload, StepValidationError, CATEGORIES.
2. Run: python -m pytest tests/test_schema.py -q
   Expected: FAIL with ModuleNotFoundError: No module named 'unstuck.schema'.
3. Implement src/unstuck/schema.py: CATEGORIES = ("admin","creative","errand","deep-work");
   a StepValidationError(ValueError); dataclasses Step(text,category,est_minutes) and
   Steps(task, steps); and validate_steps_payload(payload)->Steps that validates structure,
   rejects bool est_minutes, coerces est_minutes to an int via int(round(...)) and requires
   0 < est_minutes <= 25 (a step over 25 min is invalid — this routes to the model adapter's
   repair retry so the model splits it), strips text, and returns Steps(task="", steps=[...]).
   Raise StepValidationError on any structural problem.
4. Run: python -m pytest tests/test_schema.py -q
   Expected: PASS (8 passed).
5. Commit: "feat: typed step schema + payload validator"
   Stage only: src/unstuck/schema.py tests/test_schema.py

One commit, Codex-attributed. Do not touch any other file.
```

---

## Task 2 — Calibration (time-bias multiplier)

```
Implement ONLY the calibration unit. Touch only: src/unstuck/calibration.py and
tests/test_calibration.py. TDD: failing test first.

1. Write tests/test_calibration.py importing multiplier, calibrate, MIN_SAMPLES from
   unstuck.calibration. Cover: no history -> 1.0; a category's multiplier is the MEDIAN of its
   actual/estimated ratios once it has >= MIN_SAMPLES samples; with fewer than MIN_SAMPLES in the
   target category it falls back to the global median across all records (assert MIN_SAMPLES == 3);
   records with zero/missing est or actual are ignored; calibrate(10, 3.0) == 30 and
   calibrate(10, 0.04) == 1 (rounds, floors at 1, never returns 0).
2. Run: python -m pytest tests/test_calibration.py -q
   Expected: FAIL with ModuleNotFoundError: No module named 'unstuck.calibration'.
3. Implement src/unstuck/calibration.py: MIN_SAMPLES = 3; a helper that yields valid actual/est
   ratios (optionally filtered by category, skipping zero/missing values); multiplier(category,
   records) using the category median when it has >= MIN_SAMPLES valid ratios else the global
   median else 1.0; and calibrate(raw_minutes, mult) = max(1, int(round(raw_minutes * mult))).
4. Run: python -m pytest tests/test_calibration.py -q
   Expected: PASS (5 passed).
5. Commit: "feat: per-category time-bias calibration"
   Stage only: src/unstuck/calibration.py tests/test_calibration.py

One commit, Codex-attributed. No other files.
```

---

## Task 3 — SQLite store

```
Implement ONLY the SQLite store. Touch only: src/unstuck/store.py and tests/test_store.py.
TDD: failing test first. Depends on unstuck.schema.Step (already implemented).

1. Write tests/test_store.py importing Store from unstuck.store and Step from unstuck.schema.
   Cover: a roundtrip — add_task(text, now=) returns an id, add_steps(task_id, [Step...]),
   first_step_id(task_id), record_actual(step_id, category, est, actual, now=), and get_records()
   returns [{"category","est_minutes","actual_minutes"}]; and that export_json() returns JSON with
   "tasks","steps","records" tables populated and steps[0]["category"] == "admin". Use
   Store(":memory:").
2. Run: python -m pytest tests/test_store.py -q
   Expected: FAIL with ModuleNotFoundError: No module named 'unstuck.store'.
3. Implement src/unstuck/store.py: a Store(path=":memory:") opening sqlite3 with row_factory =
   sqlite3.Row, creating task(id,text,created_at), step(id,task_id,text,category,est_minutes,ord),
   record(id,step_id,category,est_minutes,actual_minutes,completed_at). Methods: add_task,
   add_steps (ordered by insertion via an ord column), first_step_id, record_actual, get_records,
   export_json (json.dumps with the three tables, indent=2). now= params default to time.time().
4. Run: python -m pytest tests/test_store.py -q
   Expected: PASS (2 passed).
5. Commit: "feat: SQLite store with export"
   Stage only: src/unstuck/store.py tests/test_store.py

One commit, Codex-attributed. No other files.
```

---

## Task 4 — Prompts

```
Implement ONLY the prompt builders. Touch only: src/unstuck/prompts.py and tests/test_schema.py
(extend the existing file — do NOT rewrite the schema tests already there). TDD: failing test first.

1. Append two tests to tests/test_schema.py, importing breakdown_prompt and repair_prompt from
   unstuck.prompts: breakdown_prompt("write the quarterly review") contains that task text, the
   word "json" (case-insensitive), every category in CATEGORIES, and a mention of the 25-minute
   hard maximum (assert "25" is in the prompt); repair_prompt("task x", "GARBLED{", "no JSON
   object found") contains both the bad output and the error string.
2. Run: python -m pytest tests/test_schema.py -q
   Expected: FAIL with ModuleNotFoundError: No module named 'unstuck.prompts'.
3. Implement src/unstuck/prompts.py importing CATEGORIES from unstuck.schema. A system block that
   instructs the model to break ONE task into 4-8 tiny ordered ADHD-friendly steps, each a single
   action, each with a positive-integer minute estimate that NEVER exceeds 25 minutes (hard max —
   split anything bigger into multiple steps) and exactly one category from CATEGORIES,
   returning ONLY a JSON object {"steps":[{"text","category","est_minutes"}]} with no prose/fence.
   breakdown_prompt(task) = system block + a one-line few-shot example + the quoted task.
   repair_prompt(task, bad_output, error) restates the error, echoes the previous reply, and asks
   for ONLY the JSON object in the exact schema.
4. Run: python -m pytest tests/test_schema.py -q
   Expected: PASS (10 passed).
5. Commit: "feat: breakdown + repair prompts"
   Stage only: src/unstuck/prompts.py tests/test_schema.py

One commit, Codex-attributed. No other files.
```

---

## Task 5 — Model adapter (validation + repair retry)

```
Implement ONLY the model adapter. Touch only: src/unstuck/model_adapter.py and
tests/test_model_adapter.py. TDD: failing test first. Depends on unstuck.prompts and unstuck.schema.
The LLM is injected as a generate(prompt)->str callable — NEVER import or load a real model.

1. Write tests/test_model_adapter.py importing ModelAdapter from unstuck.model_adapter and
   StepValidationError from unstuck.schema. Use a helper that builds a generate() yielding canned
   responses in order. Cover: parses good JSON on the first try and sets steps.task to the input
   task; strips surrounding prose and a ```json code fence; repairs after one bad reply
   (ModelAdapter(make([GARBLED, GOOD]), max_repairs=1) succeeds); raises StepValidationError after
   exhausting repairs (make([GARBLED, GARBLED]), max_repairs=1).
2. Run: python -m pytest tests/test_model_adapter.py -q
   Expected: FAIL with ModuleNotFoundError: No module named 'unstuck.model_adapter'.
3. Implement src/unstuck/model_adapter.py: a _extract_json(text) that regex-matches the first
   {...} (re.DOTALL), raising StepValidationError("no JSON object found") if none and on JSON
   decode error; ModelAdapter(generate, max_repairs=1) with breakdown(task)->Steps that calls
   generate(breakdown_prompt(task)), validates via validate_steps_payload(_extract_json(raw)),
   sets steps.task = task on success, and on StepValidationError re-prompts with repair_prompt up
   to max_repairs times before re-raising.
4. Run: python -m pytest tests/test_model_adapter.py -q
   Expected: PASS (4 passed).
5. Commit: "feat: model adapter with JSON validation + repair retry"
   Stage only: src/unstuck/model_adapter.py tests/test_model_adapter.py

One commit, Codex-attributed. No other files.
```

---

## Task 6 — Service (breakdown → calibrate → store)

```
Implement ONLY the application service. Touch only: src/unstuck/service.py and
tests/test_service.py. TDD: failing test first. Ties together model_adapter, calibration, store.
LLM injected as generate(prompt)->str — never load a real model.

1. Write tests/test_service.py importing Unstuck from unstuck.service and Store from unstuck.store,
   with a constant GOOD = '{"steps":[{"text":"Open doc","category":"admin","est_minutes":10}]}'.
   Cover: Unstuck(generate=lambda p: GOOD, store=Store(":memory:")).breakdown("write review")
   returns a view with task_id > 0 and rows[0].raw_minutes == 10 and (no history) calibrated_minutes
   == 10; and after seeding 3 admin records each 3x over estimate (via breakdown + log_actual),
   a fresh breakdown shows raw_minutes == 10 and calibrated_minutes == 30.
2. Run: python -m pytest tests/test_service.py -q
   Expected: FAIL with ModuleNotFoundError: No module named 'unstuck.service'.
3. Implement src/unstuck/service.py: dataclasses StepRow(step_id,text,category,raw_minutes,
   calibrated_minutes) and BreakdownView(task_id, rows). Unstuck(generate, store, max_repairs=1)
   wraps a ModelAdapter. breakdown(task): adapter.breakdown -> store.add_task -> store.add_steps ->
   read records -> map persisted step ids (ordered by ord) to steps, per-row apply
   multiplier(category, records) and calibrate(...). log_actual(step_id, actual_minutes): look up
   the step's category + est_minutes and store.record_actual(...).
4. Run: python -m pytest tests/test_service.py -q
   Expected: PASS (2 passed).
5. Run the whole suite — python -m pytest -q — expect all passing, then commit.
   Commit: "feat: Unstuck service (breakdown -> calibrate -> store)"
   Stage only: src/unstuck/service.py tests/test_service.py

One commit, Codex-attributed. No other files.
```

---

## Task 7 — Hybrid inference backend (ZeroGPU default + HF Inference fallback) + bake-off harness

> Updated 2026-06-09 (see docs/superpowers/specs/2026-06-09-unstuck-inference-addendum.md): model
> LOCKED to Qwen/Qwen3-4B-Instruct-2507; backend is a hybrid; ZeroGPU is free via the
> build-small-hackathon Team org (the personal account is not PRO).

```
Implement ONLY the inference backend + bake-off harness. Touch only: scripts/bakeoff.py,
src/unstuck/backend.py, and requirements.txt. This task has NO unit test — backend.py and
bakeoff.py import real models / call the network and MUST never be imported by the test suite.

Context: the model is LOCKED to Qwen/Qwen3-4B-Instruct-2507 (native qwen3 arch, no
trust_remote_code). backend.py is a HYBRID exposing one generate(prompt)->str selected by the env
var UNSTUCK_BACKEND (default "zerogpu"): a ZeroGPU/transformers path (model on the Space GPU) and an
"hf_inference" fallback (huggingface_hub InferenceClient -> nscale/featherless).

1. Write scripts/bakeoff.py: a MANUAL harness (puts "src" on sys.path) with ~5 SAMPLE_TASKS and a
   MODELS list of <=4B candidates, Qwen/Qwen3-4B-Instruct-2507 first (MiniCPM / Nemotron-Nano as
   alternates). make_generate(model_id) returns generate(prompt)->str backed by
   huggingface_hub.InferenceClient(model_id).chat_completion (so the bake-off scores JSON-validity
   over the serverless API without local weights). score(model_id) runs ModelAdapter(gen,
   max_repairs=1).breakdown over the tasks and returns the valid-JSON success rate; __main__ prints
   each model's rate. Keep all real network calls under the __main__ guard.
2. Implement src/unstuck/backend.py with MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507" and
   BACKEND = os.environ.get("UNSTUCK_BACKEND", "zerogpu"):
   - If BACKEND == "zerogpu": import spaces; import torch and transformers; load the tokenizer and
     AutoModelForCausalLM on cuda at MODULE SCOPE (device_map="cuda", torch_dtype="auto"); define
     generate(prompt)->str decorated @spaces.GPU(duration=30) that builds a chat prompt via
     tokenizer.apply_chat_template(..., add_generation_prompt=True), runs
     model.generate(max_new_tokens=512, do_sample=False), decodes ONLY the newly generated tokens,
     and returns a plain str (NEVER a CUDA tensor).
   - Elif BACKEND == "hf_inference": from huggingface_hub import InferenceClient; create
     InferenceClient(MODEL_ID); define generate(prompt)->str calling
     .chat_completion(messages=[{"role":"user","content":prompt}], max_tokens=512, temperature=0)
     and returning choices[0].message.content.
   Put each branch's heavy imports INSIDE that branch so importing the module with the other backend
   selected stays cheap. Do NOT import spaces/torch at top level outside the zerogpu branch.
3. Replace requirements.txt with the ZeroGPU runtime set (gradio is pinned via the README
   sdk_version, NOT here; never list spaces — the platform pins it):
       pytest>=8.0
       torch==2.8.0
       transformers
       accelerate
       huggingface_hub
4. Sanity: run python -m pytest -q — the existing suite (23 tests) must still pass (bakeoff/backend
   are not collected). Do NOT run scripts/bakeoff.py or import backend.py here (they need real
   models / network).
5. Commit: "feat: hybrid inference backend (ZeroGPU default + HF Inference fallback) + bake-off harness"
   Stage only: scripts/bakeoff.py src/unstuck/backend.py requirements.txt

One commit, Codex-attributed. No other files.
```

---

## Task 8 — Gradio app + smoke test

> Updated 2026-06-09: include the data-export button (Space storage is ephemeral — see the inference
> addendum / ZEROGPU_SPACE_NOTES §4); the smoke test importorskips gradio (gradio is supplied by the
> Space `sdk_version`, not listed in `requirements.txt`).

```
Implement ONLY the Gradio UI and its smoke test. Touch only: app.py and tests/test_app_smoke.py.
TDD: failing test first. The smoke test must not load a model or hit the network — it injects a
fake generate() and a :memory: Store, and must importorskip gradio (gradio is provided by the Space
sdk_version, not listed in requirements.txt).

1. Write tests/test_app_smoke.py: at module top do `gr = pytest.importorskip("gradio")` so the test
   skips cleanly when gradio is absent. Then import app, build an Unstuck with
   generate=lambda p: '{"steps":[{"text":"x","category":"admin","est_minutes":3}]}' and
   Store(":memory:"), call app.build_ui(svc), and assert the returned gr.Blocks is not None.
   (build_ui MUST accept an injected service so tests never load a model.)
2. Run: python -m pytest tests/test_app_smoke.py -q
   Expected: FAIL — No module named 'app' (or build_ui missing).
3. Implement app.py: put "src" on sys.path, import gradio. build_ui(service: Unstuck) -> gr.Blocks
   with: a task textbox; a "Break it down" button rendering a markdown table of step #, text, AI est
   (raw_minutes), and "For you" (calibrated_minutes) held in gr.State; an accordion to log a step's
   actual minutes (calls service.log_actual); and an "Export my data (JSON)" control that writes
   service.store.export_json() to a tempfile and serves it for download (gr.DownloadButton or a
   button + gr.File) — the escape hatch for ephemeral Space storage. A main() (mark # pragma: no
   cover) that makes the DB dir, imports backend.generate, builds the service, and launches. Guard
   with if __name__ == "__main__".
4. Run: python -m pytest tests/test_app_smoke.py -q
   Expected: PASS (1 passed).
5. Run the full suite — python -m pytest -q — expect all passing. (Commit handled by reviewer — DO
   NOT run git.) Intended message: "feat: Gradio UI (raw vs calibrated, data export) + smoke test",
   staging only app.py tests/test_app_smoke.py.
```

---

## Task 9 — Space card + deliverable drafts

> Updated 2026-06-09: README front-matter is the ZeroGPU Gradio Space config (sdk_version pinned to
> the tested gradio, python_version 3.12.12); privacy framing corrected; include the GitHub repo
> link (OpenAI Codex Track rule).

```
Implement ONLY the docs/deliverables. Touch only: README.md, docs/deliverables/demo-script.md,
docs/deliverables/social-post.md. No code, no tests.

1. Write README.md as a Hugging Face ZeroGPU Gradio Space card. YAML front-matter exactly:
       ---
       title: Unstuck
       emoji: 🧩
       colorFrom: indigo
       colorTo: purple
       sdk: gradio
       sdk_version: "6.17.3"
       python_version: "3.12.12"
       app_file: app.py
       pinned: false
       ---
   Do NOT add a `spaces` line or a hardware key (ZeroGPU is selected in Space Settings). Then:
   - A short description: Unstuck turns one overwhelming task into tiny timed steps, then learns your
     personal time-blindness and recalibrates the estimates to you. Built for the HF Build Small
     Hackathon (Backyard AI track). Runs a ≤4B model (Qwen/Qwen3-4B-Instruct-2507).
   - A privacy line: "Runs a ≤4B model you can host yourself; your task history stays in the app's
     own store and is never sent to a third-party LLM."
   - A "Run locally" block: `pip install -r requirements.txt gradio`, then for the lightweight path
     `UNSTUCK_BACKEND=hf_inference HF_TOKEN=... python app.py` (the default backend is `zerogpu`,
     which the Space uses). Note Space storage is ephemeral — hence the in-app **Export** button.
   - A "Source" line linking the GitHub repo: https://github.com/art87able/unstuck (Codex Track).
2. Write docs/deliverables/demo-script.md: a ~90-second timed demo script (hook about ADHD task
   initiation + time-blindness; break-it-down; log a couple of actuals over the estimate; re-run a
   similar task showing the raw AI estimate vs the higher "for you" estimate; the ≤4B "you can run
   it yourself" line; close on the repo/Space link). Mark it "USER RECORDS".
3. Write docs/deliverables/social-post.md: a short #BuildSmallHackathon post — paste a task, get tiny
   timed steps, it learns your personal time-blindness, runs on a ≤4B model, built for an ADHD brain,
   with a [Space link] placeholder. Mark it "USER POSTS".
4. (Commit handled by reviewer — DO NOT run git.) Intended message: "docs: Space card + demo script
   + social post drafts", staging only README.md docs/deliverables/.

(Creating the Space, recording the video, and posting are manual user steps — not part of this task.)
```

---

## Task 10 — Prompt tuning (better breakdowns from the 4B model)

> Added 2026-06-10: the v1 prompt's single-step example biases the small model toward terse,
> mono-category output. Tune the prompt; the schema and adapter stay untouched.

```
Improve ONLY the model prompts. Touch only: src/unstuck/prompts.py and tests/test_prompts.py (new).
Follow TDD: failing tests first, then the prompt changes. Do NOT modify schema.py, model_adapter.py,
or any other file.

1. Write tests/test_prompts.py covering breakdown_prompt and repair_prompt:
   - breakdown_prompt(task) contains the task text, every category name from unstuck.schema.CATEGORIES,
     and the literal substring '"steps"'.
   - The few-shot example inside breakdown_prompt is itself VALID: extract the example JSON object
     from the prompt (regex the line containing '"steps"' in the example block) and pass it through
     unstuck.schema.validate_steps_payload — it must parse with 3+ steps, more than one distinct
     category, every est_minutes <= 25, and the FIRST example step's est_minutes <= 5.
   - breakdown_prompt mentions a tiny starter first step (assert "first step" appears, case-insensitive).
   - repair_prompt(task, bad, err) contains the task, the bad output, the error text, and '"steps"'.
2. Run: python -m pytest tests/test_prompts.py -q  — expect FAIL on the new assertions.
3. Rewrite the prompt text in src/unstuck/prompts.py (keep the function signatures and the
   JSON-only output contract exactly as-is):
   - Keep: 4-8 ordered steps, one concrete action each, positive-integer minutes, 25-minute hard max,
     JSON-only with the exact {"steps":[{"text","category","est_minutes"}]} schema.
   - Add a one-line definition per category: admin (forms, email, scheduling, tidying),
     creative (writing, design, making something new), errand (leaving the house or fetching/buying),
     deep-work (sustained focused thinking or problem-solving).
   - Add: the FIRST step must be a tiny starter action of 5 minutes or less that gets the person
     physically moving or the file/page open (beats ADHD task-initiation paralysis).
   - Add: every step text starts with an imperative verb; no vague steps like "work on it".
   - Replace the one-step example with ONE worked example task ("Clean my apartment before a friend
     visits tonight") whose JSON answer has 4 steps, at least two distinct categories, a first step
     of <=5 minutes, and all estimates <=25. Keep the example on a single line so it stays easy to
     regex in tests.
   - repair_prompt: keep its structure, just inherit the improved system block.
4. Run: python -m pytest -q  — expect the FULL suite passing (existing 24 tests + the new ones).
5. (Commit handled by reviewer — DO NOT run git.) Intended message:
   "feat(prompts): category definitions, starter-step rule, richer few-shot example"
   staging only src/unstuck/prompts.py tests/test_prompts.py.
```

## Task 11 — Plan summary chip + graceful backend errors

> Added 2026-06-11: demo polish. Two UI-layer improvements; the service and store stay untouched.

```
Improve ONLY the Gradio layer. Touch only: app.py and tests/test_app_smoke.py.
Follow TDD where testable: extend the smoke test first, then implement. Do NOT modify anything
under src/unstuck/ or any other file. Do NOT run git.

1. Plan summary chip. In app.py, add a helper `summary_html(rows) -> str` at module level
   (so tests can import it without building the UI):
   - rows is the same list-of-dicts shape used in rows_state (keys: logged, actual_minutes,
     calibrated_minutes, raw_minutes).
   - Returns "" for empty rows.
   - Otherwise returns a div with class "summary" reading like:
     "For you: ~{total_for_you} min total · AI estimate: {total_raw} min"
     where total_for_you sums actual_minutes for logged rows plus calibrated_minutes for
     unlogged rows, and total_raw sums raw_minutes.
   - If at least one row is logged, append " · {n_done}/{n} done".
   Render it via a gr.HTML placed between the readout and the step list, updated by the same
   events that update rows_state (break_down and every Done click). Add a matching .summary
   CSS rule consistent with the existing calm-minimal style (similar to .readout but neutral
   stone background, centered).

2. Graceful backend errors. In break_down, wrap the service.breakdown call in try/except
   Exception: on failure, call gr.Warning with a short friendly message and return
   ([], <explainer div>, "") where the explainer says the model backend is busy or out of
   GPU quota and suggests trying again in a minute (mention that logging in to Hugging Face
   raises the free ZeroGPU quota). Never let a traceback reach the UI. Keep the existing
   empty-input branch behaviour (adjusted for the new third output).

3. Tests in tests/test_app_smoke.py (keep the existing test):
   - summary_html([]) == ""
   - summary_html with two unlogged rows (calibrated 10+20, raw 8+15) contains "30" and "23".
   - summary_html with one logged row (actual 12) + one unlogged (calibrated 20, raw 15+15)
     contains "32" and "30" and "1/2 done".
   - build_ui still returns a gr.Blocks when given a service whose generate raises
     RuntimeError (constructing the UI must not call the backend).

4. Run: python -m pytest -q — full suite green (existing tests + new ones).
5. (Commit handled by reviewer.) Intended message:
   "feat(ui): plan summary chip + graceful backend-error handling"
   staging only app.py tests/test_app_smoke.py.
```

## Task 12 — "Still stuck?" per-step re-breakdown

> Added 2026-06-11: the core ADHD loop closed recursively — any step can itself be the new
> overwhelming task. UI-layer feature reusing the existing service; src/unstuck/ stays untouched.

```
Touch only: app.py and tests/test_app_smoke.py. TDD where testable. Do NOT modify anything
under src/unstuck/. Do NOT run git. Note: app.py already has a plan-summary chip
(summary_html) and a 3-output break_down (rows, explainer/readout, summary) from Task 11 —
keep all of that working.

1. Module-level helper `splice_rows(rows, step_id, new_rows) -> list` in app.py:
   - Returns a new list where the single row whose "step_id" == step_id is replaced, in
     place, by the rows in new_rows (same dict shape). All other rows keep their order.
   - If step_id is not present, return rows unchanged.

2. UI: on every UNLOGGED step row (next to the "took (min) → Done" controls), add a small
   secondary button "Still stuck?". Clicking it:
   - Calls service.breakdown(<that step's text>) — this creates a new task in the store and
     returns calibrated rows; map them through the same view-rows dict shape already used.
   - Splices the sub-steps in place of the clicked step via splice_rows, updates rows_state,
     the readout, and the summary chip (same outputs as the Done click).
   - On backend failure (any Exception): gr.Warning with a short friendly message (busy /
     out of GPU quota, try again in a minute) and return the rows UNCHANGED.
   - Guard: if the current rows list already has 16 or more rows, warn
     ("That's plenty of steps — try starting the first tiny one") and do nothing.

3. Tests in tests/test_app_smoke.py (keep all existing tests):
   - splice_rows replaces the middle row of three with two new rows → length 4, order
     preserved (ids before/after intact).
   - splice_rows with an unknown step_id returns the input list equal to itself.
   - build_ui still returns gr.Blocks (existing tests keep passing).

4. Run: python -m pytest -q — full suite green.
5. (Commit handled by reviewer.) Intended message:
   "feat(ui): per-step re-breakdown via Still stuck? button"
   staging only app.py tests/test_app_smoke.py.
```

## Task 13 — Nebius serverless backend (third branch of the hybrid seam)

> Added 2026-06-11: entry path for the Nebius Serverless AI Builders Challenge (deadline
> 2026-06-30). Same `generate(prompt) -> str` contract; no new dependencies — Nebius AI Studio
> is OpenAI-compatible and huggingface_hub's InferenceClient accepts a base_url.

```
Touch ONLY: src/unstuck/backend.py and tests/test_backend.py (new). TDD: failing tests first.
Do NOT modify any other file. Do NOT run git.

1. Tests in tests/test_backend.py. backend.py selects its branch from env at import time, so
   each test must set env vars with monkeypatch BEFORE importing/reloading the module
   (importlib.reload). Do NOT let any test import torch, spaces, or hit the network:
   - With UNSTUCK_BACKEND=nebius and NEBIUS_API_KEY=dummy: monkeypatch
     huggingface_hub.InferenceClient with a fake class that records its constructor kwargs and
     whose chat_completion returns a canned object shaped like the real response
     (choices[0].message.content == "ok"). Assert: backend.generate("hi") == "ok"; the fake
     received base_url == backend.NEBIUS_BASE_URL and api_key == "dummy"; chat_completion was
     called with temperature=0 and max_tokens=512 and the prompt in the messages.
   - With UNSTUCK_BACKEND=nebius and NEBIUS_API_KEY unset: importing/reloading backend raises
     a clear error mentioning NEBIUS_API_KEY.
   - With UNSTUCK_BACKEND=bogus: reload raises ValueError mentioning "bogus".
2. Run: python -m pytest tests/test_backend.py -q — expect FAIL.
3. Implement in src/unstuck/backend.py:
   - Module constants: NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL",
     "https://api.studio.nebius.com/v1/") and NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL",
     MODEL_ID).
   - New elif BACKEND == "nebius" branch (keep zerogpu and hf_inference exactly as-is):
     read NEBIUS_API_KEY from env, raise RuntimeError("NEBIUS_API_KEY is required for the
     nebius backend") if missing; client = InferenceClient(base_url=NEBIUS_BASE_URL,
     api_key=key); generate(prompt) mirrors the hf_inference branch (model=NEBIUS_MODEL passed
     to chat_completion, max_tokens=512, temperature=0, returns str of the message content).
   - Import huggingface_hub inside the branch (heavy imports stay lazy, same as the others).
4. Run: python -m pytest -q — FULL suite green (34 existing + the new ones).
5. (Commit handled by reviewer.) Intended message:
   "feat(backend): nebius serverless branch (UNSTUCK_BACKEND=nebius)"
   staging only src/unstuck/backend.py tests/test_backend.py.
```
