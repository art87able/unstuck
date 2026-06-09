from __future__ import annotations

import json
import re
from collections.abc import Callable

from unstuck.prompts import breakdown_prompt, repair_prompt
from unstuck.schema import StepValidationError, Steps, validate_steps_payload


def _extract_json(text: str) -> object:
    """Extract and decode the first JSON object from model output."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise StepValidationError("no JSON object found")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise StepValidationError("no JSON object found") from exc


class ModelAdapter:
    """Turn an injected text generator into validated task breakdowns."""

    def __init__(self, generate: Callable[[str], str], max_repairs: int = 1) -> None:
        self.generate = generate
        self.max_repairs = max_repairs

    def breakdown(self, task: str) -> Steps:
        raw = self.generate(breakdown_prompt(task))

        for attempt in range(self.max_repairs + 1):
            try:
                steps = validate_steps_payload(_extract_json(raw))
            except StepValidationError as exc:
                if attempt >= self.max_repairs:
                    raise
                raw = self.generate(repair_prompt(task, raw, str(exc)))
                continue

            steps.task = task
            return steps

        raise StepValidationError("model output did not validate")
