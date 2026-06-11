from __future__ import annotations

import json
import re
from collections.abc import Callable

from unstuck.prompts import breakdown_prompt, repair_prompt
from unstuck.schema import StepValidationError, Steps, validate_steps_payload


def _extract_json(text: str) -> object:
    """Extract the first steps payload, falling back to the first JSON object."""
    decoder = json.JSONDecoder()
    first_payload: object | None = None

    for match in re.finditer(r"\{", text):
        try:
            payload, _end = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue

        if first_payload is None:
            first_payload = payload
        if isinstance(payload, dict) and "steps" in payload:
            return payload

    if first_payload is not None:
        return first_payload
    raise StepValidationError("no JSON object found")


class ModelAdapter:
    """Turn an injected text generator into validated task breakdowns."""

    def __init__(self, generate: Callable[[str], str], max_repairs: int = 1) -> None:
        self.generate = generate
        self.max_repairs = max_repairs

    def breakdown(self, task: str, granularity: str = "regular") -> Steps:
        raw = self.generate(breakdown_prompt(task, granularity))

        for attempt in range(self.max_repairs + 1):
            try:
                steps = validate_steps_payload(_extract_json(raw))
            except StepValidationError as exc:
                if attempt >= self.max_repairs:
                    raise
                raw = self.generate(repair_prompt(task, raw, str(exc), granularity))
                continue

            steps.task = task
            return steps

        raise StepValidationError("model output did not validate")
