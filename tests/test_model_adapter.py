from __future__ import annotations

import pytest

from unstuck.model_adapter import ModelAdapter
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
