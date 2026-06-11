from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


CATEGORIES = ("admin", "creative", "errand", "deep-work")
_VAGUE_STARTERS = (
    "work on",
    "continue ",
    "deal with",
    "handle ",
    "think about",
    "try to ",
    "start working",
    "do the work",
    "make progress",
    "figure out",
    "look into",
    "get ready to",
)


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
    if len(raw_steps) > 12:
        raise StepValidationError("too many steps - return at most 12")

    steps = [_validate_step(raw_step) for raw_step in raw_steps]
    seen_texts: set[str] = set()
    for step in steps:
        text_key = step.text.lower()
        if text_key in seen_texts:
            raise StepValidationError("steps must not repeat")
        seen_texts.add(text_key)

    return Steps(task="", steps=steps)


def _validate_step(raw_step: Any) -> Step:
    if not isinstance(raw_step, dict):
        raise StepValidationError("step must be an object")

    raw_text = raw_step.get("text")
    if not isinstance(raw_text, str):
        raise StepValidationError("step text must be a string")

    text = _normalize_text(raw_text)
    if not text:
        raise StepValidationError("step text must not be blank")
    if len(text.split()) < 2:
        raise StepValidationError("step text must be a concrete action of at least two words")
    if len(text) > 90:
        raise StepValidationError("step text too long - keep each step under 90 characters")
    if text.lower().startswith(_VAGUE_STARTERS):
        raise StepValidationError(
            f'step "{text}" is vague - start with a concrete physical action'
        )

    category = raw_step.get("category")
    if category not in CATEGORIES:
        raise StepValidationError("step category is invalid")

    est_minutes = _coerce_est_minutes(raw_step.get("est_minutes"))
    return Step(text=text, category=category, est_minutes=est_minutes)


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if normalized.endswith(".") and not normalized.endswith("..."):
        normalized = normalized[:-1]
    return normalized


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
