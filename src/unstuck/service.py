from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from unstuck.calibration import calibrate, multiplier
from unstuck.model_adapter import ModelAdapter
from unstuck.store import Store


@dataclass
class StepRow:
    step_id: int
    text: str
    category: str
    raw_minutes: int
    calibrated_minutes: int


@dataclass
class BreakdownView:
    task_id: int
    rows: list[StepRow]


class Unstuck:
    """Application service tying model breakdowns to persistence and calibration."""

    def __init__(
        self,
        generate: Callable[[str], str],
        store: Store,
        max_repairs: int = 1,
    ) -> None:
        self.adapter = ModelAdapter(generate, max_repairs=max_repairs)
        self.store = store

    def breakdown(self, task: str) -> BreakdownView:
        steps = self.adapter.breakdown(task)
        task_id = self.store.add_task(task)
        self.store.add_steps(task_id, steps.steps)

        records = self.store.get_records()
        step_ids = self._step_ids(task_id)
        rows = [
            StepRow(
                step_id=step_id,
                text=step.text,
                category=step.category,
                raw_minutes=step.est_minutes,
                calibrated_minutes=calibrate(
                    step.est_minutes,
                    multiplier(step.category, records),
                ),
            )
            for step_id, step in zip(step_ids, steps.steps, strict=True)
        ]
        return BreakdownView(task_id=task_id, rows=rows)

    def log_actual(self, step_id: int, actual_minutes: int) -> int:
        row = self.store.conn.execute(
            """
            select category, est_minutes
            from step
            where id = ?
            """,
            (step_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"step {step_id} does not exist")

        return self.store.record_actual(
            step_id,
            str(row["category"]),
            int(row["est_minutes"]),
            actual_minutes,
        )

    def _step_ids(self, task_id: int) -> list[int]:
        rows = self.store.conn.execute(
            """
            select id
            from step
            where task_id = ?
            order by ord
            """,
            (task_id,),
        ).fetchall()
        return [int(row["id"]) for row in rows]
