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


def test_import_json_restores_records_into_fresh_store() -> None:
    source = Store(":memory:")
    task_id = source.add_task("clear inbox", now=123.0)
    source.add_steps(
        task_id,
        [Step(text="Archive old messages", category="admin", est_minutes=10)],
    )
    step_id = source.first_step_id(task_id)
    source.record_actual(step_id, "admin", 10, 12, now=456.0)

    restored = Store(":memory:")
    result = restored.import_json(source.export_json())

    assert result == {"imported": 1, "skipped": 0}
    assert restored.get_records() == source.get_records()


def test_import_json_skips_duplicate_records() -> None:
    source = Store(":memory:")
    task_id = source.add_task("clear inbox", now=123.0)
    source.add_steps(
        task_id,
        [Step(text="Archive old messages", category="admin", est_minutes=10)],
    )
    step_id = source.first_step_id(task_id)
    source.record_actual(step_id, "admin", 10, 12, now=456.0)
    payload = source.export_json()

    restored = Store(":memory:")
    assert restored.import_json(payload) == {"imported": 1, "skipped": 0}

    assert restored.import_json(payload) == {"imported": 0, "skipped": 1}
    assert restored.get_records() == source.get_records()


def test_import_json_malformed_json_raises_value_error() -> None:
    store = Store(":memory:")

    try:
        store.import_json("{")
    except ValueError as exc:
        assert str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_import_json_bad_record_rows_raise_value_error() -> None:
    store = Store(":memory:")
    payload = json.dumps(
        {
            "tasks": [],
            "steps": [],
            "records": [
                {
                    "step_id": 1,
                    "category": "admin",
                    "est_minutes": 0,
                    "actual_minutes": 12,
                    "completed_at": 456.0,
                }
            ],
        }
    )

    try:
        store.import_json(payload)
    except ValueError as exc:
        assert str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_plan_snapshot_save_then_load_roundtrips_opaque_rows_json() -> None:
    store = Store(":memory:")
    rows_json = '[{"step_id": 1, "text": "Open doc"}]'

    store.save_plan("Write review", rows_json)

    assert store.load_plan() == ("Write review", rows_json)


def test_plan_snapshot_second_save_overwrites_single_row() -> None:
    store = Store(":memory:")
    store.save_plan("First task", '[{"step_id": 1}]')

    store.save_plan("Second task", '[{"step_id": 2}]')

    assert store.load_plan() == ("Second task", '[{"step_id": 2}]')


def test_plan_snapshot_fresh_store_returns_none() -> None:
    store = Store(":memory:")

    assert store.load_plan() is None


def test_plan_snapshot_clear_removes_saved_snapshot() -> None:
    store = Store(":memory:")
    store.save_plan("Write review", '[{"step_id": 1}]')

    store.clear_plan()

    assert store.load_plan() is None


def test_plan_snapshot_clear_on_fresh_store_does_not_raise() -> None:
    store = Store(":memory:")

    store.clear_plan()

    assert store.load_plan() is None
