from __future__ import annotations

import pytest

from unstuck.schema import CATEGORIES, StepValidationError, validate_steps_payload


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
