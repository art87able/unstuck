from __future__ import annotations

import json

from unstuck.schema import CATEGORIES


_CATEGORY_LIST = ", ".join(CATEGORIES)

GRANULARITY_RULES = {
    "chunky": (
        "Produce 3-5 bigger steps. Estimates may be up to 25 minutes. "
        "Make the first step the easiest one."
    ),
    "regular": (
        "Produce 4-8 tiny steps. The first step must be a tiny starter action of "
        "5 minutes or less that gets the person physically moving or the file/page open."
    ),
    "tiny": (
        "Produce 5-10 very tiny steps. No estimate may exceed 10 minutes. "
        "The first step must take 2 minutes or less and get the person physically "
        "moving or the file/page open."
    ),
}

EXAMPLES = {
    "regular": (
        'Example: Task "Clean my apartment before a friend visits tonight" -> '
        '{"steps":[{"text":"Open a trash bag and collect visible rubbish","category":"admin","est_minutes":5},{"text":"Carry rubbish to the outside bin","category":"errand","est_minutes":5},{"text":"Clear dishes into the sink","category":"admin","est_minutes":8},{"text":"Wipe kitchen counters and bathroom sink","category":"admin","est_minutes":12}]}'
    ),
    "tiny": (
        'Example: Task "Clean my apartment before a friend visits tonight" -> '
        '{"steps":[{"text":"Stand up and grab an empty trash bag","category":"admin","est_minutes":2},{"text":"Collect visible rubbish from one room","category":"admin","est_minutes":6},{"text":"Carry the trash bag to the outside bin","category":"errand","est_minutes":5},{"text":"Move dirty dishes into the sink","category":"admin","est_minutes":5},{"text":"Wipe the kitchen counter","category":"admin","est_minutes":7},{"text":"Wipe the bathroom sink","category":"admin","est_minutes":6}]}'
    ),
    "chunky": (
        'Example: Task "Clean my apartment before a friend visits tonight" -> '
        '{"steps":[{"text":"Collect rubbish and carry it to the outside bin","category":"errand","est_minutes":15},{"text":"Clear dishes and wipe kitchen surfaces","category":"admin","est_minutes":20},{"text":"Reset bathroom and main room surfaces","category":"admin","est_minutes":25}]}'
    ),
}

# A second example from a different domain so the model sees creative and
# deep-work categories in use, not only admin/errand.
EXAMPLES_EXTRA = {
    "regular": (
        'Example: Task "Prepare the talk I keep putting off" -> '
        '{"steps":[{"text":"Open the slides file and reread the outline","category":"admin","est_minutes":3},{"text":"List the three main points on a scratch note","category":"deep-work","est_minutes":8},{"text":"Draft bullet points for the opening slide","category":"creative","est_minutes":10},{"text":"Write speaker notes for the first section","category":"creative","est_minutes":12}]}'
    ),
    "tiny": (
        'Example: Task "Prepare the talk I keep putting off" -> '
        '{"steps":[{"text":"Open the slides file","category":"admin","est_minutes":2},{"text":"Reread the existing outline","category":"admin","est_minutes":4},{"text":"List the three main points on a scratch note","category":"deep-work","est_minutes":6},{"text":"Write one bullet for the opening slide","category":"creative","est_minutes":5},{"text":"Draft two bullets for the first section","category":"creative","est_minutes":8}]}'
    ),
    "chunky": (
        'Example: Task "Prepare the talk I keep putting off" -> '
        '{"steps":[{"text":"Reread the outline and list the main points","category":"deep-work","est_minutes":15},{"text":"Draft bullets for every slide","category":"creative","est_minutes":25},{"text":"Write speaker notes and do one run-through","category":"creative","est_minutes":25}]}'
    ),
}

# Cap how much of a failed reply gets echoed back in the repair prompt; a
# rambling reply would otherwise crowd out the instructions.
MAX_BAD_OUTPUT_CHARS = 1500


def _system_block(granularity: str) -> str:
    try:
        rule = GRANULARITY_RULES[granularity]
    except KeyError as exc:
        raise ValueError(f"unknown granularity: {granularity}") from exc

    return f"""You break ONE overwhelming task into tiny ordered ADHD-friendly steps.
{rule}
Each step must be a single concrete action.
Each step must include a positive-integer minute estimate.
The estimate must NEVER exceed 25 minutes. 25 is a hard max; split anything bigger into multiple steps.
Each step must use exactly one category from: {_CATEGORY_LIST}.
Category definitions:
- admin: forms, email, scheduling, tidying.
- creative: writing, design, making something new.
- errand: leaving the house or fetching/buying.
- deep-work: sustained focused thinking or problem-solving.
Every step text must start with an imperative verb. Avoid vague steps like "work on it".
Return ONLY a JSON object with this exact schema and no prose or markdown fence:
{{"steps":[{{"text":"...","category":"...","est_minutes":1}}]}}"""


def breakdown_prompt(
    task: str, granularity: str = "regular", exemplar: str | None = None
) -> str:
    """Build the first-pass prompt for breaking one task into validated step JSON.

    When `exemplar` is given (a recalled `Example: Task "..." -> {...}` line) it is
    injected on its own line; when None the output is byte-for-byte the original."""
    exemplar_block = f"{exemplar}\n" if exemplar else ""
    return (
        f"{_system_block(granularity)}\n\n"
        f"{EXAMPLES[granularity]}\n"
        f"{EXAMPLES_EXTRA[granularity]}\n"
        f"{exemplar_block}\n"
        f'Task: "{task}"'
    )


def format_exemplar(task_text: str, steps: list[dict]) -> str:
    """Render a past breakdown as a single few-shot example line for the prompt."""
    payload = {
        "steps": [
            {
                "text": str(step["text"]),
                "category": str(step["category"]),
                "est_minutes": int(step["est_minutes"]),
            }
            for step in steps
        ]
    }
    return f'Example: Task "{task_text}" -> {json.dumps(payload, separators=(",", ":"))}'


def repair_prompt(
    task: str,
    bad_output: str,
    error: str,
    granularity: str = "regular",
) -> str:
    """Build the retry prompt after model output fails schema validation."""
    if len(bad_output) > MAX_BAD_OUTPUT_CHARS:
        bad_output = bad_output[:MAX_BAD_OUTPUT_CHARS] + " ...[truncated]"
    return (
        f"{_system_block(granularity)}\n\n"
        f"{EXAMPLES[granularity]}\n\n"
        f'Task: "{task}"\n'
        f"Validation error: {error}\n"
        f"Previous reply:\n{bad_output}\n\n"
        "Fix the validation error. Return ONLY the JSON object in the exact schema: "
        '{"steps":[{"text","category","est_minutes"}]}.'
    )
