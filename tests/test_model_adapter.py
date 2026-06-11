from __future__ import annotations

import pytest

from unstuck.model_adapter import ModelAdapter
from unstuck.prompts import GRANULARITY_RULES
from unstuck.schema import StepValidationError


GOOD = '{"steps":[{"text":"Open the doc","category":"admin","est_minutes":5}]}'
GARBLED = "not json at all"


def make(responses: list[str]):
    replies = iter(responses)

    def generate(prompt: str) -> str:
        return next(replies)

    return generate


def test_parses_good_json_first_try_and_sets_task() -> None:
    adapter = ModelAdapter(make([GOOD]))

    steps = adapter.breakdown("write review")

    assert steps.task == "write review"
    assert steps.steps[0].text == "Open the doc"
    assert steps.steps[0].category == "admin"
    assert steps.steps[0].est_minutes == 5


def test_strips_surrounding_prose_and_json_code_fence() -> None:
    fenced = f"Here you go:\n```json\n{GOOD}\n```\nDone."
    adapter = ModelAdapter(make([fenced]))

    steps = adapter.breakdown("write review")

    assert steps.task == "write review"
    assert steps.steps[0].text == "Open the doc"


def test_repairs_after_one_bad_reply() -> None:
    adapter = ModelAdapter(make([GARBLED, GOOD]), max_repairs=1)

    steps = adapter.breakdown("write review")

    assert steps.task == "write review"
    assert steps.steps[0].est_minutes == 5


def test_raises_after_exhausting_repairs() -> None:
    adapter = ModelAdapter(make([GARBLED, GARBLED]), max_repairs=1)

    with pytest.raises(StepValidationError):
        adapter.breakdown("write review")


def test_breakdown_passes_granularity_to_first_prompt() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return GOOD

    adapter = ModelAdapter(generate)

    adapter.breakdown("write review", granularity="tiny")

    assert GRANULARITY_RULES["tiny"] in prompts[0]


def test_repair_prompt_keeps_granularity() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return [GARBLED, GOOD][len(prompts) - 1]

    adapter = ModelAdapter(generate, max_repairs=1)

    adapter.breakdown("write review", granularity="tiny")

    assert len(prompts) == 2
    assert GRANULARITY_RULES["tiny"] in prompts[0]
    assert GRANULARITY_RULES["tiny"] in prompts[1]


def test_extracts_json_despite_trailing_prose_with_braces() -> None:
    noisy = f"{GOOD}\nNote: adjust {{the estimates}} if needed."
    adapter = ModelAdapter(make([noisy]))

    steps = adapter.breakdown("write review")

    assert steps.steps[0].text == "Open the doc"


def test_extracts_json_when_output_starts_mid_prefill_style() -> None:
    prefixed = f"{GOOD} and that is all"
    adapter = ModelAdapter(make([prefixed]))

    steps = adapter.breakdown("write review")

    assert steps.steps[0].est_minutes == 5


def test_skips_invalid_brace_blob_before_real_json() -> None:
    noisy = "{oops not json} " + GOOD
    adapter = ModelAdapter(make([noisy]))

    steps = adapter.breakdown("write review")

    assert steps.steps[0].category == "admin"
