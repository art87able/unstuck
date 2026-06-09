from __future__ import annotations

import json

from unstuck.schema import Step
from unstuck.store import Store


def test_store_roundtrips_task_steps_and_actual_records() -> None:
    store = Store(":memory:")
    task_id = store.add_task("write review", now=123.0)

    assert task_id > 0

    store.add_steps(
        task_id,
        [
            Step(text="Open doc", category="admin", est_minutes=5),
            Step(text="Draft notes", category="creative", est_minutes=15),
        ],
    )
    step_id = store.first_step_id(task_id)
    store.record_actual(step_id, "admin", 5, 8, now=456.0)

    assert store.get_records() == [
        {"category": "admin", "est_minutes": 5, "actual_minutes": 8}
    ]


def test_export_json_includes_all_tables() -> None:
    store = Store(":memory:")
    task_id = store.add_task("clear inbox", now=123.0)
    store.add_steps(
        task_id,
        [Step(text="Archive old messages", category="admin", est_minutes=10)],
    )
    step_id = store.first_step_id(task_id)
    store.record_actual(step_id, "admin", 10, 12, now=456.0)

    payload = json.loads(store.export_json())

    assert len(payload["tasks"]) == 1
    assert len(payload["steps"]) == 1
    assert len(payload["records"]) == 1
    assert payload["steps"][0]["category"] == "admin"
