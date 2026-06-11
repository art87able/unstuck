from __future__ import annotations

import json
import re

import pytest

from unstuck.prompts import EXAMPLES, GRANULARITY_RULES, breakdown_prompt, repair_prompt
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


def test_regular_breakdown_prompt_keeps_current_example_text() -> None:
    prompt = breakdown_prompt("Clean my apartment before a friend visits tonight", "regular")

    assert EXAMPLES["regular"] in prompt
    assert (
        EXAMPLES["regular"]
        == 'Example: Task "Clean my apartment before a friend visits tonight" -> '
        '{"steps":[{"text":"Open a trash bag and collect visible rubbish","category":"admin","est_minutes":5},{"text":"Carry rubbish to the outside bin","category":"errand","est_minutes":5},{"text":"Clear dishes into the sink","category":"admin","est_minutes":8},{"text":"Wipe kitchen counters and bathroom sink","category":"admin","est_minutes":12}]}'
    )


def test_tiny_breakdown_prompt_uses_tiny_example_with_two_minute_starter() -> None:
    prompt = breakdown_prompt("Clean my apartment before a friend visits tonight", "tiny")
    parsed = validate_steps_payload(_example_payload(prompt))

    assert "Stand up and grab an empty trash bag" in prompt
    assert parsed.steps[0].est_minutes == 2
    assert len(parsed.steps) == 6
    assert all(step.est_minutes <= 10 for step in parsed.steps)


def test_chunky_breakdown_prompt_uses_chunky_example_with_twenty_five_minutes() -> None:
    prompt = breakdown_prompt("Clean my apartment before a friend visits tonight", "chunky")
    parsed = validate_steps_payload(_example_payload(prompt))

    assert '"est_minutes":25' in prompt
    assert len(parsed.steps) == 3
    assert all(15 <= step.est_minutes <= 25 for step in parsed.steps)


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


@pytest.mark.parametrize("granularity", ["chunky", "regular", "tiny"])
def test_extra_example_is_valid_and_covers_creative_and_deep_work(granularity: str) -> None:
    from unstuck.prompts import EXAMPLES_EXTRA

    prompt = breakdown_prompt("Write the project report", granularity)
    assert EXAMPLES_EXTRA[granularity] in prompt

    match = re.search(r"(\{\"steps\":.*\})", EXAMPLES_EXTRA[granularity])
    assert match is not None
    parsed = validate_steps_payload(json.loads(match.group(1)))

    categories = {step.category for step in parsed.steps}
    assert "creative" in categories
    assert "deep-work" in categories
    assert all(step.est_minutes <= 25 for step in parsed.steps)


def test_tiny_extra_example_respects_tiny_rules() -> None:
    from unstuck.prompts import EXAMPLES_EXTRA

    match = re.search(r"(\{\"steps\":.*\})", EXAMPLES_EXTRA["tiny"])
    assert match is not None
    parsed = validate_steps_payload(json.loads(match.group(1)))

    assert 5 <= len(parsed.steps) <= 10
    assert parsed.steps[0].est_minutes <= 2
    assert all(step.est_minutes <= 10 for step in parsed.steps)


def test_repair_prompt_includes_example_and_truncates_long_bad_output() -> None:
    from unstuck.prompts import EXAMPLES, MAX_BAD_OUTPUT_CHARS

    long_bad = "x" * (MAX_BAD_OUTPUT_CHARS + 500)
    prompt = repair_prompt("Submit the grant application", long_bad, "no JSON object found", "tiny")

    assert EXAMPLES["tiny"] in prompt
    assert "...[truncated]" in prompt
    assert long_bad not in prompt


def test_chunky_prompt_does_not_demand_five_minute_starter() -> None:
    prompt = breakdown_prompt("Write the project report", "chunky")

    assert "5 minutes or less" not in prompt
    assert "easiest" in prompt
