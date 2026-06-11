from __future__ import annotations

import pytest

from unstuck.prompts import breakdown_prompt, repair_prompt
from unstuck.schema import CATEGORIES, StepValidationError, _normalize_text, validate_steps_payload


def test_valid_payload_parses_and_coerces_est_minutes_to_int() -> None:
    result = validate_steps_payload(
        {
            "steps": [
                {
                    "text": "  Open the document  ",
                    "category": "admin",
                    "est_minutes": 4.6,
                }
            ]
        }
    )

    assert result.task == ""
    assert len(result.steps) == 1
    assert result.steps[0].text == "Open the document"
    assert result.steps[0].category == "admin"
    assert result.steps[0].est_minutes == 5
    assert isinstance(result.steps[0].est_minutes, int)


def test_step_text_normalizes_whitespace_and_drops_one_trailing_period() -> None:
    result = validate_steps_payload(
        {"steps": [{"text": "  Open  the file.  ", "category": "admin", "est_minutes": 3}]}
    )

    assert result.steps[0].text == "Open the file"


def test_step_text_keeps_ellipsis_when_normalizing() -> None:
    assert _normalize_text("  Wait...  ") == "Wait..."


def test_more_than_twelve_steps_raises_exact_repair_message() -> None:
    payload = {
        "steps": [
            {"text": f"Open file {index}", "category": "admin", "est_minutes": 1}
            for index in range(13)
        ]
    }

    with pytest.raises(StepValidationError) as exc_info:
        validate_steps_payload(payload)

    assert str(exc_info.value) == "too many steps - return at most 12"


def test_one_word_step_text_raises_exact_repair_message() -> None:
    with pytest.raises(StepValidationError) as exc_info:
        validate_steps_payload(
            {"steps": [{"text": "Email", "category": "admin", "est_minutes": 5}]}
        )

    assert str(exc_info.value) == "step text must be a concrete action of at least two words"


def test_step_text_over_ninety_characters_raises_exact_repair_message() -> None:
    with pytest.raises(StepValidationError) as exc_info:
        validate_steps_payload(
            {
                "steps": [
                    {
                        "text": "Write the first full careful draft of the project update "
                        "with every detailed note included before sending it to reviewers",
                        "category": "deep-work",
                        "est_minutes": 15,
                    }
                ]
            }
        )

    assert str(exc_info.value) == "step text too long - keep each step under 90 characters"


def test_vague_step_starter_raises_exact_repair_message() -> None:
    with pytest.raises(StepValidationError) as exc_info:
        validate_steps_payload(
            {"steps": [{"text": "Work on report", "category": "deep-work", "est_minutes": 10}]}
        )

    assert (
        str(exc_info.value)
        == 'step "Work on report" is vague - start with a concrete physical action'
    )


def test_duplicate_step_text_raises_exact_repair_message() -> None:
    with pytest.raises(StepValidationError) as exc_info:
        validate_steps_payload(
            {
                "steps": [
                    {"text": "Open the file", "category": "admin", "est_minutes": 2},
                    {"text": "open  the file.", "category": "admin", "est_minutes": 2},
                ]
            }
        )

    assert str(exc_info.value) == "steps must not repeat"


def test_missing_steps_key_raises() -> None:
    with pytest.raises(StepValidationError):
        validate_steps_payload({})


def test_empty_steps_list_raises() -> None:
    with pytest.raises(StepValidationError):
        validate_steps_payload({"steps": []})


def test_bad_category_raises() -> None:
    with pytest.raises(StepValidationError):
        validate_steps_payload(
            {"steps": [{"text": "Email Sam", "category": "social", "est_minutes": 5}]}
        )


def test_non_positive_estimate_raises() -> None:
    with pytest.raises(StepValidationError):
        validate_steps_payload(
            {"steps": [{"text": "Email Sam", "category": "admin", "est_minutes": 0}]}
        )


def test_estimate_over_25_minutes_raises() -> None:
    with pytest.raises(StepValidationError):
        validate_steps_payload(
            {"steps": [{"text": "Draft report", "category": "deep-work", "est_minutes": 40}]}
        )


def test_blank_text_raises() -> None:
    with pytest.raises(StepValidationError):
        validate_steps_payload(
            {"steps": [{"text": "   ", "category": "admin", "est_minutes": 5}]}
        )


def test_categories_match_contract() -> None:
    assert set(CATEGORIES) == {"admin", "creative", "errand", "deep-work"}


def test_breakdown_prompt_includes_task_json_categories_and_time_limit() -> None:
    prompt = breakdown_prompt("write the quarterly review")

    assert "write the quarterly review" in prompt
    assert "json" in prompt.lower()
    for category in CATEGORIES:
        assert category in prompt
    assert "25" in prompt


def test_repair_prompt_includes_bad_output_and_error() -> None:
    prompt = repair_prompt("task x", "GARBLED{", "no JSON object found")

    assert "GARBLED{" in prompt
    assert "no JSON object found" in prompt


@pytest.mark.parametrize(
    "text",
    [
        "Figure out the budget",
        "Look into flight options",
        "Get ready to write the report",
    ],
)
def test_new_vague_starters_rejected(text: str) -> None:
    with pytest.raises(StepValidationError, match="vague"):
        validate_steps_payload(
            {"steps": [{"text": text, "category": "admin", "est_minutes": 5}]}
        )
