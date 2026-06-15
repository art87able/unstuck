# Nebius Similar-Task Recall (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a task is pasted, embed it on Nebius serverless, recall the most-similar past task, and use it to seed task-specific time estimates and shape the new breakdown with the past good breakdown as a one-shot exemplar — shown as a labelled suggestion that auto-excludes after two dismissals.

**Architecture:** A new `embed(text) -> list[float] | None` seam (`embeddings.py`) mirrors the existing `generate` seam; a pure `recall.py` selects the best match; `prompts`/`model_adapter`/`service` gain an `exemplar` passthrough; the `app.py` `break_down` handler orchestrates `embed → recall → exemplar → seed → banner`; recall history persists as a new `gr.BrowserState` `history` key. Recall is strictly additive — any failure degrades silently to today's flow.

**Tech Stack:** Python 3.11+, `huggingface_hub` (already a dep), stdlib `urllib`/`json`/`math`, Gradio, pytest + `gradio_client`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-15-nebius-recall-design.md`

**Conventions to follow:** every module starts with `from __future__ import annotations`; full type hints; one-line docstrings on public functions; tests mock all network (zero real calls); commit after each task. Run the suite with `python -m pytest -q`.

---

## File map

| File | Status | Responsibility |
|---|---|---|
| `src/unstuck/embeddings.py` | **create** | `embed(text) -> list[float] | None` seam; Nebius `/v1/embeddings` via stdlib POST; returns `None` whenever recall can't run |
| `src/unstuck/recall.py` | **create** | Pure: `select(vec, history)` + `_cosine` + `seed_estimates(rows, entry)` |
| `src/unstuck/prompts.py` | modify | `breakdown_prompt(..., exemplar=None)` slot + `format_exemplar(text, steps)` |
| `src/unstuck/model_adapter.py` | modify | `breakdown(..., exemplar=None)` passthrough |
| `src/unstuck/service.py` | modify | `Unstuck.breakdown(..., exemplar=None)` passthrough |
| `app.py` | modify | history BrowserState helpers; `break_down`/`log_step` wiring; recall banner + "Start fresh" |
| `tests/test_embeddings.py` | **create** | embed seam tests |
| `tests/test_recall.py` | **create** | recall + seeding tests |
| `tests/test_prompts.py` | modify | exemplar slot + format_exemplar tests |
| `tests/test_service.py` | modify | exemplar passthrough test |
| `tests/test_app_smoke.py` | modify | history helpers + integration tests |
| `docs/deliverables/nebius-submission.md` | modify | correct stale counts (final task) |

**History entry shape** (one dict per past task in `data["history"]`):

```python
{
    "text": str,                # the pasted task text
    "embedding": list[float],   # its Nebius embedding
    "breakdown": [              # steps, for exemplar reuse
        {"text": str, "category": str, "est_minutes": int},
    ],
    "durations": [              # per logged step, for estimate seeding
        {"category": str, "actual_minutes": int},
    ],
    "dismissals": int,          # 0 by default; >= 2 excludes from recall
}
```

---

## Task 1: Embedding seam (`embeddings.py`)

**Files:**
- Create: `src/unstuck/embeddings.py`
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_embeddings.py
from __future__ import annotations

import importlib
import sys
import types

import pytest


def reload_embeddings(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    sys.modules.pop("unstuck.embeddings", None)
    import unstuck.embeddings

    return importlib.reload(unstuck.embeddings)


def test_embed_posts_openai_shape_and_parses_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")
    embeddings = reload_embeddings(monkeypatch)

    calls: dict[str, object] = {}

    def fake_post(url: str, headers: dict, payload: dict) -> dict:
        calls["url"] = url
        calls["headers"] = headers
        calls["payload"] = payload
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr(embeddings, "_http_post_json", fake_post)

    vec = embeddings.embed("clean the kitchen")

    assert vec == [0.1, 0.2, 0.3]
    assert calls["url"] == "https://api.tokenfactory.nebius.com/v1/embeddings"
    assert calls["headers"]["Authorization"] == "Bearer dummy"
    assert calls["payload"] == {
        "model": embeddings.NEBIUS_EMBED_MODEL,
        "input": "clean the kitchen",
    }


def test_embed_returns_none_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "nebius")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    embeddings = reload_embeddings(monkeypatch)

    assert embeddings.embed("hi") is None


def test_embed_returns_none_when_backend_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "none")
    embeddings = reload_embeddings(monkeypatch)

    assert embeddings.embed("hi") is None


def test_embed_degrades_to_none_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")
    embeddings = reload_embeddings(monkeypatch)

    def boom(url: str, headers: dict, payload: dict) -> dict:
        raise RuntimeError("network down")

    monkeypatch.setattr(embeddings, "_http_post_json", boom)

    assert embeddings.embed("hi") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_embeddings.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'unstuck.embeddings'`

- [ ] **Step 3: Write the implementation**

```python
# src/unstuck/embeddings.py
from __future__ import annotations

import json
import os
import urllib.request

EMBED_BACKEND = os.environ.get("UNSTUCK_EMBED_BACKEND", "nebius")
NEBIUS_EMBED_BASE_URL = os.environ.get(
    "NEBIUS_EMBED_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
)
NEBIUS_EMBED_MODEL = os.environ.get("NEBIUS_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
_TIMEOUT = float(os.environ.get("UNSTUCK_EMBED_TIMEOUT", "10"))


def _http_post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    """POST JSON, return decoded JSON. The single network seam — mocked in tests."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _embed_nebius(text: str, key: str) -> list[float]:
    url = NEBIUS_EMBED_BASE_URL.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {"model": NEBIUS_EMBED_MODEL, "input": text}
    body = _http_post_json(url, headers, payload)
    return [float(value) for value in body["data"][0]["embedding"]]


def embed(text: str) -> list[float] | None:
    """Embed text for recall. Returns None whenever recall cannot run (disabled
    backend, missing key, or any error) so recall stays strictly additive."""
    if EMBED_BACKEND == "nebius":
        key = os.environ.get("NEBIUS_API_KEY")
        if not key:
            return None
        try:
            return _embed_nebius(text, key)
        except Exception:
            return None
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_embeddings.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/unstuck/embeddings.py tests/test_embeddings.py
git commit -m "feat(embeddings): add embed() seam over Nebius serverless"
```

---

## Task 2: Recall selection + cosine (`recall.py`)

**Files:**
- Create: `src/unstuck/recall.py`
- Test: `tests/test_recall.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recall.py
from __future__ import annotations

from unstuck.recall import Match, select


def _entry(text: str, embedding: list[float], dismissals: int = 0) -> dict:
    return {
        "text": text,
        "embedding": embedding,
        "breakdown": [],
        "durations": [],
        "dismissals": dismissals,
    }


def test_select_returns_match_above_threshold() -> None:
    history = [_entry("clean kitchen", [1.0, 0.0])]

    match = select([1.0, 0.0], history, threshold=0.8)

    assert isinstance(match, Match)
    assert match.index == 0
    assert match.similarity == 1.0


def test_select_returns_none_below_threshold() -> None:
    history = [_entry("orthogonal", [0.0, 1.0])]

    assert select([1.0, 0.0], history, threshold=0.8) is None


def test_select_picks_highest_cosine() -> None:
    history = [
        _entry("near", [0.9, 0.1]),
        _entry("exact", [1.0, 0.0]),
    ]

    match = select([1.0, 0.0], history, threshold=0.5)

    assert match is not None
    assert match.index == 1


def test_select_skips_entries_dismissed_twice() -> None:
    history = [_entry("exact but dismissed", [1.0, 0.0], dismissals=2)]

    assert select([1.0, 0.0], history, threshold=0.5) is None


def test_select_skips_entries_without_embedding() -> None:
    history = [{"text": "no vec", "embedding": [], "dismissals": 0}]

    assert select([1.0, 0.0], history, threshold=0.5) is None


def test_select_empty_history_returns_none() -> None:
    assert select([1.0, 0.0], [], threshold=0.5) is None


def test_select_none_query_returns_none() -> None:
    assert select(None, [_entry("x", [1.0, 0.0])], threshold=0.5) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recall.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'unstuck.recall'`

- [ ] **Step 3: Write the implementation**

```python
# src/unstuck/recall.py
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from statistics import median
from typing import Any

RECALL_THRESHOLD = float(os.environ.get("UNSTUCK_RECALL_THRESHOLD", "0.80"))
MAX_DISMISSALS = 2


@dataclass
class Match:
    index: int
    similarity: float
    entry: dict[str, Any]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def select(
    query_vec: list[float] | None,
    history: list[dict[str, Any]],
    threshold: float = RECALL_THRESHOLD,
) -> Match | None:
    """Return the highest-cosine history entry at/above threshold, skipping entries
    dismissed >= MAX_DISMISSALS times or lacking an embedding. Pure; no I/O."""
    if not query_vec:
        return None
    best: Match | None = None
    for index, entry in enumerate(history):
        if int(entry.get("dismissals", 0)) >= MAX_DISMISSALS:
            continue
        vec = entry.get("embedding")
        if not vec:
            continue
        similarity = _cosine(query_vec, list(vec))
        if similarity >= threshold and (best is None or similarity > best.similarity):
            best = Match(index=index, similarity=similarity, entry=entry)
    return best


def seed_estimates(
    rows: list[dict[str, Any]], entry: dict[str, Any]
) -> list[dict[str, Any]]:
    """Override calibrated_minutes for rows whose category has a real duration in the
    matched entry (median of that category's actuals); leave others untouched. Pure."""
    by_category: dict[str, list[int]] = {}
    for duration in entry.get("durations", []):
        by_category.setdefault(str(duration["category"]), []).append(
            int(duration["actual_minutes"])
        )

    seeded: list[dict[str, Any]] = []
    for row in rows:
        actuals = by_category.get(str(row.get("category")))
        if actuals:
            new_row = dict(row)
            new_row["calibrated_minutes"] = max(1, int(round(median(actuals))))
            seeded.append(new_row)
        else:
            seeded.append(row)
    return seeded
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recall.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/unstuck/recall.py tests/test_recall.py
git commit -m "feat(recall): pure cosine match selection over task history"
```

---

## Task 3: Exemplar prompt slot + formatter (`prompts.py`)

**Files:**
- Modify: `src/unstuck/prompts.py`
- Test: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_prompts.py`)

```python
import json

from unstuck.prompts import breakdown_prompt, format_exemplar


def test_breakdown_prompt_without_exemplar_is_unchanged() -> None:
    prompt = breakdown_prompt("write the report", granularity="regular")

    # The Task line still follows the second example block with a blank line.
    assert prompt.endswith('Task: "write the report"')
    assert "Example: Task" in prompt
    assert "\n\nTask:" in prompt


def test_breakdown_prompt_injects_exemplar_on_its_own_line() -> None:
    exemplar = 'Example: Task "old task" -> {"steps":[]}'

    prompt = breakdown_prompt("new task", granularity="regular", exemplar=exemplar)

    assert exemplar in prompt
    assert f"{exemplar}\n\nTask:" in prompt


def test_format_exemplar_renders_example_line() -> None:
    steps = [
        {"text": "Open the file", "category": "admin", "est_minutes": 3},
        {"text": "Draft the intro", "category": "creative", "est_minutes": 10},
    ]

    line = format_exemplar("write the report", steps)

    assert line.startswith('Example: Task "write the report" -> ')
    payload = json.loads(line.split(" -> ", 1)[1])
    assert payload == {
        "steps": [
            {"text": "Open the file", "category": "admin", "est_minutes": 3},
            {"text": "Draft the intro", "category": "creative", "est_minutes": 10},
        ]
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prompts.py -q`
Expected: FAIL with `ImportError: cannot import name 'format_exemplar'`

- [ ] **Step 3: Edit `breakdown_prompt` and add `format_exemplar`**

Add `import json` to the top of `src/unstuck/prompts.py` (after `from __future__ import annotations`).

Replace the existing `breakdown_prompt` function (currently lines 83-90) with:

```python
def breakdown_prompt(
    task: str, granularity: str = "regular", exemplar: str | None = None
) -> str:
    """Build the first-pass prompt for breaking one task into validated step JSON.

    When `exemplar` is given (a recalled `Example: Task "..." -> {...}` line) it is
    injected on its own line; when None the output is byte-for-byte the original."""
    exemplar_block = f"{exemplar}\n" if exemplar else ""
    return (
        f"{_system_block(granularity)}\n\n"
        f"{EXAMPLES[granularity]}\n"
        f"{EXAMPLES_EXTRA[granularity]}\n"
        f"{exemplar_block}\n"
        f'Task: "{task}"'
    )


def format_exemplar(task_text: str, steps: list[dict]) -> str:
    """Render a past breakdown as a single few-shot example line for the prompt."""
    payload = {
        "steps": [
            {
                "text": str(step["text"]),
                "category": str(step["category"]),
                "est_minutes": int(step["est_minutes"]),
            }
            for step in steps
        ]
    }
    return f'Example: Task "{task_text}" -> {json.dumps(payload, separators=(",", ":"))}'
```

> Note: original `breakdown_prompt` ended `...EXTRA[granularity]}\n\n` then `Task:`. The new form with `exemplar=None` produces `...EXTRA[granularity]}\n` + `""` + `\n` + `Task:` = the identical `\n\n` gap. Verified by `test_breakdown_prompt_without_exemplar_is_unchanged`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_prompts.py -q`
Expected: PASS (all prompt tests, incl. the 3 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/unstuck/prompts.py tests/test_prompts.py
git commit -m "feat(prompts): optional exemplar slot + format_exemplar"
```

---

## Task 4: Exemplar passthrough (`model_adapter.py`, `service.py`)

**Files:**
- Modify: `src/unstuck/model_adapter.py:39-52`
- Modify: `src/unstuck/service.py:38-39`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_service.py`)

```python
def test_breakdown_threads_exemplar_into_first_prompt() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return GOOD

    app = Unstuck(generate=generate, store=Store(":memory:"))

    app.breakdown("write review", exemplar='Example: Task "old" -> {"steps":[]}')

    assert 'Example: Task "old" -> {"steps":[]}' in prompts[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service.py::test_breakdown_threads_exemplar_into_first_prompt -v`
Expected: FAIL with `TypeError: breakdown() got an unexpected keyword argument 'exemplar'`

- [ ] **Step 3: Add the passthrough**

In `src/unstuck/model_adapter.py`, replace the `breakdown` signature + first line (lines 39-40):

```python
    def breakdown(
        self, task: str, granularity: str = "regular", exemplar: str | None = None
    ) -> Steps:
        raw = self.generate(breakdown_prompt(task, granularity, exemplar))
```

(The repair path stays unchanged — repairs run without the exemplar.)

In `src/unstuck/service.py`, replace the `breakdown` signature + first line (lines 38-39):

```python
    def breakdown(
        self, task: str, granularity: str = "regular", exemplar: str | None = None
    ) -> BreakdownView:
        steps = self.adapter.breakdown(task, granularity, exemplar=exemplar)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_service.py -q`
Expected: PASS (existing 3 + the new one)

- [ ] **Step 5: Commit**

```bash
git add src/unstuck/model_adapter.py src/unstuck/service.py tests/test_service.py
git commit -m "feat(service): thread optional exemplar through breakdown"
```

---

## Task 5: History BrowserState helpers (`app.py`)

These are pure functions mirroring the existing `make_record` / `with_records` / `_records_from_data` family. They go near those helpers (around `app.py:145-330`).

**Files:**
- Modify: `app.py` (add helpers near the other pure state helpers)
- Test: `tests/test_app_smoke.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_app_smoke.py`)

```python
def test_make_history_entry_shape() -> None:
    entry = app.make_history_entry(
        "clean kitchen",
        [0.1, 0.2],
        [{"text": "Grab a bag", "category": "admin", "est_minutes": 2}],
    )

    assert entry == {
        "text": "clean kitchen",
        "embedding": [0.1, 0.2],
        "breakdown": [{"text": "Grab a bag", "category": "admin", "est_minutes": 2}],
        "durations": [],
        "dismissals": 0,
    }


def test_history_from_data_defaults_to_empty() -> None:
    assert app._history_from_data({"records": [], "plan": None}) == []
    assert app._history_from_data(None) == []


def test_with_history_returns_new_data_without_mutating() -> None:
    data = {"records": [], "plan": None, "history": []}
    history = [app.make_history_entry("t", [1.0], [])]

    updated = app.with_history(data, history)

    assert updated["history"] == history
    assert data["history"] == []


def test_bump_dismissal_increments_one_entry() -> None:
    history = [
        app.make_history_entry("a", [1.0], []),
        app.make_history_entry("b", [0.0], []),
    ]

    updated = app.bump_dismissal(history, 1)

    assert updated[1]["dismissals"] == 1
    assert updated[0]["dismissals"] == 0
    assert history[1]["dismissals"] == 0  # original untouched


def test_bump_dismissal_out_of_range_returns_copy_unchanged() -> None:
    history = [app.make_history_entry("a", [1.0], [])]

    assert app.bump_dismissal(history, 9) == history


def test_record_duration_in_history_appends_to_entry() -> None:
    history = [app.make_history_entry("a", [1.0], [])]

    updated = app.record_duration_in_history(history, 0, "admin", 12)

    assert updated[0]["durations"] == [{"category": "admin", "actual_minutes": 12}]
    assert history[0]["durations"] == []  # original untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app_smoke.py -q -k history`
Expected: FAIL with `AttributeError: module 'app' has no attribute 'make_history_entry'`

- [ ] **Step 3: Add the helpers to `app.py`**

Add near the other pure state helpers (e.g. just after `make_record`, ~`app.py:160`):

```python
def make_history_entry(
    text: str, embedding: list[float], breakdown: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a recall-history entry for one completed/created task."""
    return {
        "text": text,
        "embedding": list(embedding),
        "breakdown": [
            {
                "text": str(step["text"]),
                "category": str(step["category"]),
                "est_minutes": int(step["est_minutes"]),
            }
            for step in breakdown
        ],
        "durations": [],
        "dismissals": 0,
    }


def _history_from_data(data: dict | None) -> list[dict[str, Any]]:
    """Return the recall history from BrowserState, or empty if absent/malformed."""
    if not isinstance(data, dict):
        return []
    history = data.get("history")
    return history if isinstance(history, list) else []


def with_history(data: dict, history: list[dict[str, Any]]) -> dict:
    """Return a copy of BrowserState data with the recall history replaced."""
    return {**data, "history": history}


def bump_dismissal(
    history: list[dict[str, Any]], index: int
) -> list[dict[str, Any]]:
    """Return a copy of history with entry[index]'s dismissals incremented by one."""
    updated = [dict(entry) for entry in history]
    if 0 <= index < len(updated):
        updated[index]["dismissals"] = int(updated[index].get("dismissals", 0)) + 1
    return updated


def record_duration_in_history(
    history: list[dict[str, Any]], index: int, category: str, actual_minutes: int
) -> list[dict[str, Any]]:
    """Return a copy of history with one real duration appended to entry[index]."""
    updated = [dict(entry) for entry in history]
    if 0 <= index < len(updated):
        durations = list(updated[index].get("durations", []))
        durations.append({"category": category, "actual_minutes": int(actual_minutes)})
        updated[index]["durations"] = durations
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_smoke.py -q -k history`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "feat(app): pure recall-history BrowserState helpers"
```

---

## Task 6: Add `history` to the BrowserState default

**Files:**
- Modify: `app.py:1067-1069` (the `gr.BrowserState` default)

- [ ] **Step 1: Edit the default**

Replace:

```python
        user_data = gr.BrowserState(
            {"records": [], "plan": None}, storage_key="unstuck-v1"
        )
```

with:

```python
        user_data = gr.BrowserState(
            {"records": [], "plan": None, "history": []}, storage_key="unstuck-v1"
        )
```

> `storage_key` stays `"unstuck-v1"`: adding a key is backward-compatible because `_history_from_data` defaults missing/old state to `[]`.

- [ ] **Step 2: Run the full suite to confirm nothing regressed**

Run: `python -m pytest -q`
Expected: PASS (all existing + Tasks 1-5 tests green)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): carry recall history in BrowserState default"
```

---

## Task 7: Inject `embed` into `build_ui` and orchestrate recall in `break_down`

This wires the seam: `break_down` embeds the task, selects a match, builds the exemplar, seeds estimates, persists a history entry, and exposes a recall banner + matched index via state. Tested with `gradio_client` (the repo's app-integration pattern), injecting a fake `embed`.

**Files:**
- Modify: `app.py` — `build_ui` signature (`:615`), imports, the `break_down` handler (`:682-722`), add a `recall_state` + banner output, update the `break_button.click` wiring.
- Test: `tests/test_app_smoke.py`

- [ ] **Step 1: Write the failing integration test** (append to `tests/test_app_smoke.py`)

```python
def test_break_down_uses_recall_exemplar_and_seeds_estimates() -> None:
    """A pre-seeded history entry with a real 30-min admin duration should both
    inject its breakdown as an exemplar AND seed the admin estimate to 30."""
    prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {"steps": [{"text": "Open the inbox", "category": "admin", "est_minutes": 10}]}
        )

    service = Unstuck(generate=fake_generate, store=Store(":memory:"))
    # Fake embed: identical vector for every task -> guaranteed cosine 1.0 match.
    ui = app.build_ui(service, embed=lambda text: [1.0, 0.0])
    ui.launch(prevent_thread_lock=True, server_port=7952, quiet=True)
    try:
        from gradio_client import Client

        client = Client("http://127.0.0.1:7952", verbose=False)
        history = [
            {
                "text": "tidy my inbox",
                "embedding": [1.0, 0.0],
                "breakdown": [
                    {"text": "Open the inbox", "category": "admin", "est_minutes": 10}
                ],
                "durations": [{"category": "admin", "actual_minutes": 30}],
                "dismissals": 0,
            }
        ]
        res = client.predict(
            "clear my email backlog",
            {"records": [], "plan": None, "history": history},
            "regular",
            api_name="/break_down",
        )
        summary = next(r for r in res if isinstance(r, str) and "summary" in r)
        # Seeded "for you" estimate is the matched task's real 30 min, not 10.
        assert "~30 min total" in summary
        # The exemplar (a recalled Example line) reached the model prompt.
        assert any("Example: Task \"tidy my inbox\"" in p for p in prompts)
    finally:
        ui.close()
```

> Confirm `api_name` output ordering against the existing `test_break_down_calibrates_from_browser_records` test; reuse its `next(r for r in res ...)` extraction style. If the summary marker string differs, match the marker that test uses.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_app_smoke.py::test_break_down_uses_recall_exemplar_and_seeds_estimates -q`
Expected: FAIL — `build_ui()` has no `embed` parameter (`TypeError`).

- [ ] **Step 3: Add the import and `embed` parameter**

At the top of `app.py`, with the other `from unstuck...` imports (near `:21`), add:

```python
from unstuck import embeddings, recall
```

Change the `build_ui` signature (`app.py:615`) from:

```python
def build_ui(service: Unstuck) -> gr.Blocks:
```

to:

```python
def build_ui(
    service: Unstuck,
    embed: Callable[[str], list[float] | None] | None = None,
) -> gr.Blocks:
    embed_fn = embed if embed is not None else embeddings.embed
```

(`Callable` is already imported at `app.py:9`.)

- [ ] **Step 4: Rewrite the `break_down` handler body**

Replace the success branch of `break_down` (`app.py:697-722`) so that, on a non-empty task, it embeds → selects → (optionally) builds an exemplar and seeds → persists a history entry. Full replacement for the `try:` block onward:

```python
        vector = embed_fn(clean_task)
        match = recall.select(vector, _history_from_data(data))
        exemplar = (
            format_exemplar(match.entry["text"], match.entry["breakdown"])
            if match is not None
            else None
        )
        try:
            view = service.breakdown(clean_task, granularity, exemplar=exemplar)
            rows = recalibrated(view_rows(view), records)
        except Exception:
            gr.Warning("The model backend is busy. Try again in a minute.")
            updated = persist(data, clean_task, [])
            return (
                [],
                '<div class="explainer">The model backend is busy or out of GPU quota. '
                "Try again in a minute. Logging in to Hugging Face raises the free "
                "ZeroGPU quota.</div>",
                "",
                patterns(records),
                updated,
                None,
                "",
                None,
            )

        banner = ""
        recall_pointer = None
        if match is not None:
            rows = recall.seed_estimates(rows, match.entry)
            banner = recall_banner_html(match.entry["text"])
            recall_pointer = match.index

        history = _history_from_data(data)
        new_index = len(history)
        history = history + [
            make_history_entry(
                clean_task,
                vector or [],
                [
                    {
                        "text": row["text"],
                        "category": row["category"],
                        "est_minutes": row["raw_minutes"],
                    }
                    for row in rows
                ],
            )
        ]
        updated = with_history(persist(data, clean_task, rows), history)
        return (
            rows,
            readout(records),
            completion_html(rows) + summary_html(rows),
            patterns(records),
            updated,
            None,
            banner,
            {"history_index": new_index, "dismiss_index": recall_pointer,
             "task": clean_task, "granularity": granularity},
        )
```

> The two extra trailing tuple values (`banner`, the recall pointer dict) map to the two new outputs (`recall_banner_output`, `recall_state`) added in Step 5. `embed_fn` is called once (`vector`) and reused.

Update the empty-task and error early-returns (`app.py:689-696` and the new error branch) to also return two extra trailing values `"", None` so every `break_down` return is an 8-tuple.

- [ ] **Step 5: Add the `recall_banner` output, `recall_state`, and the banner helper**

Add a pure helper near `restored_banner_html` (`app.py`, the banner family ~`:540`):

```python
def recall_banner_html(matched_task: str) -> str:
    """Banner shown when a breakdown was shaped by a recalled similar task."""
    safe = html.escape(matched_task)
    return (
        '<div class="recall-banner">Shaped by a similar task you did before: '
        f'<em>{safe}</em></div>'
    )
```

(`html` is already imported at `app.py:8`.)

In the Blocks body, add a banner HTML output and a recall-state holder. Just after `readout_output = gr.HTML()` (`app.py:1095`):

```python
        recall_banner_output = gr.HTML()
        recall_state = gr.State(None)
```

`break_down` is wired to **two** events that must stay in sync: `break_button.click` (`app.py:1342`) **and** `task.submit` (`app.py:1367`, the Enter-to-submit path). Both currently use this identical 6-output list:

```python
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                user_data,
                editing_step_id,
            ],
```

Replace the `outputs=[...]` of **both** blocks with the 8-output form (append the two new components in this order):

```python
            outputs=[
                rows_state,
                readout_output,
                summary_output,
                patterns_output,
                user_data,
                editing_step_id,
                recall_banner_output,
                recall_state,
            ],
```

This matches the 8-tuple `break_down` now returns exactly. (Leave the `inputs=[task, user_data, granularity]` unchanged on both.)

- [ ] **Step 6: Update `main()` to pass the real embed**

`main()` already relies on the default (`embed=None` → `embeddings.embed`), so no change is required. Leave `build_ui(service)` as-is at `app.py:1443`.

- [ ] **Step 7: Run the test + full suite**

Run: `python -m pytest tests/test_app_smoke.py::test_break_down_uses_recall_exemplar_and_seeds_estimates -q`
Expected: PASS

Run: `python -m pytest -q`
Expected: PASS (full suite green; adjust any sibling break_down test whose output arity changed — they read named markers, not positions, so they should be unaffected).

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "feat(app): recall-shaped breakdowns with seeded estimates + banner"
```

---

## Task 8: Capture real durations into the active history entry on log

So future recalls can seed from real durations, `log_step` must append the logged actual to the active task's history entry (pointed to by `recall_state.history_index`).

**Files:**
- Modify: `app.py` — the `log_step` handler closure (`:732+`) and its `.click` wiring to thread `recall_state`.
- Test: `tests/test_app_smoke.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_app_smoke.py`)

This is a pure-logic test of the append helper composed the way the handler uses it (the handler wiring itself is covered by the integration suite):

```python
def test_record_duration_then_seed_roundtrip() -> None:
    from unstuck.recall import seed_estimates

    history = [app.make_history_entry("tidy inbox", [1.0], [])]
    history = app.record_duration_in_history(history, 0, "admin", 30)

    rows = [{"category": "admin", "calibrated_minutes": 10, "raw_minutes": 10}]
    seeded = seed_estimates(rows, history[0])

    assert seeded[0]["calibrated_minutes"] == 30
```

- [ ] **Step 2: Run it to verify it passes-or-fails**

Run: `python -m pytest tests/test_app_smoke.py::test_record_duration_then_seed_roundtrip -q`
Expected: PASS already (helpers exist from Tasks 2 + 5) — this test locks the contract the handler depends on.

- [ ] **Step 3: Wire duration capture into `log_step`**

In the `log_step(step_id)` handler closure, after the actual minutes are computed and the record is added (where `record_actual` / `make_record` is called), thread `recall_state` in as an input and, when it carries a `history_index`, update history:

```python
            pointer = recall_state if isinstance(recall_state, dict) else {}
            history_index = pointer.get("history_index")
            updated_data = persist(data, task, rows)
            if history_index is not None and category is not None:
                history = record_duration_in_history(
                    _history_from_data(updated_data),
                    int(history_index),
                    str(category),
                    int(actual_minutes),
                )
                updated_data = with_history(updated_data, history)
```

Add `recall_state` (the `gr.State`) to the `inputs=[...]` of the `done.click(log_step(...), inputs=[...])` wiring (`app.py:1208-1211`), and ensure `updated_data` is what the handler returns for `user_data`.

> `category` and `actual_minutes` are already in scope in `log_step` (it builds a record from them). If the local names differ, use the ones the existing handler computes for the calibration record.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "feat(app): capture real step durations into recall history"
```

---

## Task 9: "Start fresh" — dismiss the recall and re-break without an exemplar

When a recall banner is showing, a "Start fresh" button re-breaks the task with no exemplar and increments the matched entry's `dismissals` (2 dismissals → never recalled again).

**Files:**
- Modify: `app.py` — render a "Start fresh" button from `recall_state`, add a `start_fresh` handler.
- Test: `tests/test_app_smoke.py`

- [ ] **Step 1: Write the failing integration test** (append to `tests/test_app_smoke.py`)

```python
def test_start_fresh_bumps_dismissal_and_drops_exemplar() -> None:
    prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {"steps": [{"text": "Open the inbox", "category": "admin", "est_minutes": 10}]}
        )

    service = Unstuck(generate=fake_generate, store=Store(":memory:"))
    ui = app.build_ui(service, embed=lambda text: [1.0, 0.0])
    ui.launch(prevent_thread_lock=True, server_port=7953, quiet=True)
    try:
        from gradio_client import Client

        client = Client("http://127.0.0.1:7953", verbose=False)
        history = [
            {
                "text": "tidy my inbox",
                "embedding": [1.0, 0.0],
                "breakdown": [
                    {"text": "Open the inbox", "category": "admin", "est_minutes": 10}
                ],
                "durations": [],
                "dismissals": 1,
            }
        ]
        res = client.predict(
            "clear my email backlog",
            {"records": [], "plan": None, "history": history},
            "regular",
            {"history_index": 1, "dismiss_index": 0,
             "task": "clear my email backlog", "granularity": "regular"},
            api_name="/start_fresh",
        )
        # The matched entry hits 2 dismissals and the regenerated prompt has no exemplar.
        data = next(r for r in res if isinstance(r, dict) and "history" in r)
        assert data["history"][0]["dismissals"] == 2
        assert not any('Example: Task "tidy my inbox"' in p for p in prompts)
    finally:
        ui.close()
```

> Verify the exact `api_name`/output positions against how the existing integration tests read results, and align the `predict` argument list with `start_fresh`'s declared `inputs`.

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_app_smoke.py::test_start_fresh_bumps_dismissal_and_drops_exemplar -q`
Expected: FAIL — no `/start_fresh` endpoint.

- [ ] **Step 3: Add the `start_fresh` handler inside `build_ui`**

Place near `break_down`:

```python
    def start_fresh(
        task: str, data: dict, granularity: str, pointer: dict | None
    ) -> tuple[list[dict[str, Any]], str, str, str, dict, None, str, None]:
        clean_task = task.strip()
        records = _records_from_data(data)
        history = _history_from_data(data)
        dismiss_index = (pointer or {}).get("dismiss_index")
        if dismiss_index is not None:
            history = bump_dismissal(history, int(dismiss_index))
        data = with_history(data, history)
        try:
            view = service.breakdown(clean_task, granularity, exemplar=None)
            rows = recalibrated(view_rows(view), records)
        except Exception:
            gr.Warning("The model backend is busy. Try again in a minute.")
            return ([], readout(records), "", patterns(records),
                    persist(data, clean_task, []), None, "", None)
        updated = persist(data, clean_task, rows)
        return (
            rows,
            readout(records),
            completion_html(rows) + summary_html(rows),
            patterns(records),
            updated,
            None,
            "",
            None,
        )
```

- [ ] **Step 4: Render the "Start fresh" button from `recall_state`**

Add a render block alongside `render_rows` (`app.py:1100`) that shows the button only when a recall happened:

```python
        @gr.render(inputs=[recall_state])
        def render_recall_actions(pointer: dict | None) -> None:
            if not pointer or pointer.get("dismiss_index") is None:
                return
            fresh = gr.Button("Start fresh", size="sm", variant="secondary")
            fresh.click(
                start_fresh,
                inputs=[task, user_data, granularity, recall_state],
                outputs=[
                    rows_state,
                    readout_output,
                    summary_output,
                    patterns_output,
                    user_data,
                    editing_step_id,
                    recall_banner_output,
                    recall_state,
                ],
                api_name="start_fresh",
            )
```

- [ ] **Step 5: Run the test + full suite**

Run: `python -m pytest tests/test_app_smoke.py::test_start_fresh_bumps_dismissal_and_drops_exemplar -q`
Expected: PASS

Run: `python -m pytest -q`
Expected: PASS (full suite)

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "feat(app): Start fresh button dismisses and re-breaks without exemplar"
```

---

## Task 10: Add the recall-banner CSS + correct the stale submission doc

**Files:**
- Modify: `app.py` — add a `.recall-banner` rule to the `CSS` string.
- Modify: `docs/deliverables/nebius-submission.md`

- [ ] **Step 1: Add CSS for the banner**

In the `CSS` block (top of `app.py`, near the other rules ~`:86`), add:

```css
.recall-banner { font-size: 13px; color: #4f46e5; background: rgba(79,70,229,0.08);
  border-radius: 10px; padding: 8px 12px; margin: 8px 0; }
```

- [ ] **Step 2: Correct the stale counts in the submission draft**

In `docs/deliverables/nebius-submission.md`: change "three serving backends"/"three backends" to **four** (add the `offgrid` row to the backend table), update the "99 tests" figure to the current count from `python -m pytest -q` (the final line reports the total), and add a one-line note that similar-task recall runs on Nebius embeddings with zero ZeroGPU cost. Reconcile the base URL to the shipped `https://api.tokenfactory.nebius.com/v1/`.

- [ ] **Step 3: Run the full suite to get the final test count**

Run: `python -m pytest -q`
Expected: PASS — note the total to drop into the doc.

- [ ] **Step 4: Manual smoke (optional, requires a key)**

Run: `UNSTUCK_BACKEND=nebius UNSTUCK_EMBED_BACKEND=nebius NEBIUS_API_KEY=… python app.py`
Paste a task, complete it, paste a similar one — confirm the recall banner appears and the "for you" estimate reflects the prior real duration. This is the single billed check.

- [ ] **Step 5: Commit**

```bash
git add app.py docs/deliverables/nebius-submission.md
git commit -m "docs+style: recall banner CSS; refresh submission counts"
```

---

## Done criteria

- `python -m pytest -q` is green, fully network-free (embed + chat both mocked).
- Pasting a task with a similar one in history shows the recall banner, injects the past breakdown as an exemplar, and seeds the "for you" estimate from the real prior duration.
- "Start fresh" drops the exemplar and, after a second dismissal, that entry is never recalled again.
- All recall work runs on Nebius serverless; the embedding path spends zero ZeroGPU quota; vectors live only in `localStorage`.
