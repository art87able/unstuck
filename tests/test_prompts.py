from __future__ import annotations

import json
import re

import pytest

from unstuck.prompts import GRANULARITY_RULES, breakdown_prompt, repair_prompt
from unstuck.schema import CATEGORIES, validate_steps_payload


def _example_payload(prompt: str) -> object:
    example_line = next(line for line in prompt.splitlines() if line.startswith("Example:") and '"steps"' in line)
    match = re.search(r"(\{\"steps\":.*\})", example_line)
    assert match is not None
    return json.loads(match.group(1))


def test_breakdown_prompt_includes_task_categories_and_schema_marker() -> None:
    task = "File my tax return"

    prompt = breakdown_prompt(task)

    assert task in prompt
    assert '"steps"' in prompt
    for category in CATEGORIES:
        assert category in prompt


def test_breakdown_prompt_example_is_valid_multi_step_payload() -> None:
    prompt = breakdown_prompt("Clean my apartment before a friend visits tonight")

    parsed = validate_steps_payload(_example_payload(prompt))

    assert len(parsed.steps) >= 3
    assert len({step.category for step in parsed.steps}) > 1
    assert all(step.est_minutes <= 25 for step in parsed.steps)
    assert parsed.steps[0].est_minutes <= 5


def test_breakdown_prompt_mentions_tiny_first_step() -> None:
    prompt = breakdown_prompt("Write the project report")

    assert "first step" in prompt.lower()


def test_breakdown_prompt_defaults_to_regular_granularity() -> None:
    prompt = breakdown_prompt("Write the project report")

    assert GRANULARITY_RULES["regular"] in prompt


@pytest.mark.parametrize("granularity", ["chunky", "regular", "tiny"])
def test_breakdown_prompt_includes_granularity_rule(granularity: str) -> None:
    prompt = breakdown_prompt("Write the project report", granularity)

    assert GRANULARITY_RULES[granularity] in prompt


def test_breakdown_prompt_rejects_unknown_granularity() -> None:
    with pytest.raises(ValueError):
        breakdown_prompt("Write the project report", "huge")


def test_repair_prompt_includes_context_and_schema_marker() -> None:
    task = "Submit the grant application"
    bad_output = "not json"
    error = "payload must be an object"

    prompt = repair_prompt(task, bad_output, error)

    assert task in prompt
    assert bad_output in prompt
    assert error in prompt
    assert '"steps"' in prompt


def test_repair_prompt_includes_granularity_rule() -> None:
    prompt = repair_prompt(
        "Submit the grant application",
        "not json",
        "payload must be an object",
        "tiny",
    )

    assert GRANULARITY_RULES["tiny"] in prompt
