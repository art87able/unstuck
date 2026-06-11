from __future__ import annotations

from unstuck.prompts import GRANULARITY_RULES
from unstuck.service import Unstuck
from unstuck.store import Store


GOOD = '{"steps":[{"text":"Open doc","category":"admin","est_minutes":10}]}'


def test_breakdown_returns_persisted_uncalibrated_view_without_history() -> None:
    app = Unstuck(generate=lambda prompt: GOOD, store=Store(":memory:"))

    view = app.breakdown("write review")

    assert view.task_id > 0
    assert view.rows[0].raw_minutes == 10
    assert view.rows[0].calibrated_minutes == 10


def test_breakdown_calibrates_with_learned_category_history() -> None:
    app = Unstuck(generate=lambda prompt: GOOD, store=Store(":memory:"))
    for _ in range(3):
        view = app.breakdown("write review")
        app.log_actual(view.rows[0].step_id, 30)

    view = app.breakdown("write review")

    assert view.rows[0].raw_minutes == 10
    assert view.rows[0].calibrated_minutes == 30


def test_breakdown_passes_granularity_to_model_prompt() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return GOOD

    app = Unstuck(generate=generate, store=Store(":memory:"))

    app.breakdown("write review", granularity="tiny")

    assert GRANULARITY_RULES["tiny"] in prompts[0]
