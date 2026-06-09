from __future__ import annotations

from unstuck.schema import CATEGORIES


_CATEGORY_LIST = ", ".join(CATEGORIES)

_SYSTEM_BLOCK = f"""You break ONE overwhelming task into 4-8 tiny ordered ADHD-friendly steps.
Each step must be a single concrete action.
Each step must include a positive-integer minute estimate.
The estimate must NEVER exceed 25 minutes. 25 is a hard max; split anything bigger into multiple steps.
Each step must use exactly one category from: {_CATEGORY_LIST}.
Return ONLY a JSON object with this exact schema and no prose or markdown fence:
{{"steps":[{{"text":"...","category":"...","est_minutes":1}}]}}"""


def breakdown_prompt(task: str) -> str:
    """Build the first-pass prompt for breaking one task into validated step JSON."""
    example = (
        'Example: Task "wash dishes" -> '
        '{"steps":[{"text":"Clear the sink","category":"admin","est_minutes":3}]}'
    )
    return f'{_SYSTEM_BLOCK}\n\n{example}\n\nTask: "{task}"'


def repair_prompt(task: str, bad_output: str, error: str) -> str:
    """Build the retry prompt after model output fails schema validation."""
    return (
        f"{_SYSTEM_BLOCK}\n\n"
        f'Task: "{task}"\n'
        f"Validation error: {error}\n"
        f"Previous reply:\n{bad_output}\n\n"
        'Return ONLY the JSON object in the exact schema: {"steps":[{"text","category","est_minutes"}]}.'
    )
