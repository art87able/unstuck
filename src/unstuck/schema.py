from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CATEGORIES = ("admin", "creative", "errand", "deep-work")


class StepValidationError(ValueError):
    """Raised when model step JSON does not match the app contract."""


@dataclass
class Step:
    text: str
    category: str
    est_minutes: int


@dataclass
class Steps:
    task: str
    steps: list[Step]


def validate_steps_payload(payload: object) -> Steps:
    """Validate model output and return typed, normalized steps."""
    if not isinstance(payload, dict):
        raise StepValidationError("payload must be an object")

    raw_steps = payload.get("steps")
    if "steps" not in payload or not isinstance(raw_steps, list) or not raw_steps:
        raise StepValidationError("payload must include non-empty steps")

    steps = [_validate_step(raw_step) for raw_step in raw_steps]
    return Steps(task="", steps=steps)


def _validate_step(raw_step: Any) -> Step:
    if not isinstance(raw_step, dict):
        raise StepValidationError("step must be an object")

    raw_text = raw_step.get("text")
    if not isinstance(raw_text, str):
        raise StepValidationError("step text must be a string")

    text = raw_text.strip()
    if not text:
        raise StepValidationError("step text must not be blank")

    category = raw_step.get("category")
    if category not in CATEGORIES:
        raise StepValidationError("step category is invalid")

    est_minutes = _coerce_est_minutes(raw_step.get("est_minutes"))
    return Step(text=text, category=category, est_minutes=est_minutes)


def _coerce_est_minutes(value: Any) -> int:
    if isinstance(value, bool):
        raise StepValidationError("est_minutes must not be boolean")

    try:
        minutes = int(round(value))
    except (TypeError, ValueError) as exc:
        raise StepValidationError("est_minutes must be numeric") from exc

    if minutes <= 0 or minutes > 25:
        raise StepValidationError("est_minutes must be between 1 and 25")

    return minutes
