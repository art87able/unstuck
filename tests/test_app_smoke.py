from __future__ import annotations

import json

import pytest

gr = pytest.importorskip("gradio")

import app
from unstuck.service import Unstuck
from unstuck.store import Store


def test_splice_rows_replaces_middle_row_with_new_rows() -> None:
    rows = [
        {"step_id": 1, "text": "before"},
        {"step_id": 2, "text": "replace me"},
        {"step_id": 3, "text": "after"},
    ]
    new_rows = [
        {"step_id": 20, "text": "first new"},
        {"step_id": 21, "text": "second new"},
    ]

    spliced = app.splice_rows(rows, 2, new_rows)

    assert spliced == [rows[0], new_rows[0], new_rows[1], rows[2]]
    assert len(spliced) == 4


def test_splice_rows_unknown_step_id_returns_rows_unchanged() -> None:
    rows = [
        {"step_id": 1, "text": "before"},
        {"step_id": 2, "text": "after"},
    ]

    spliced = app.splice_rows(rows, 99, [{"step_id": 20, "text": "new"}])

    assert spliced == rows


def test_build_ui_accepts_injected_service() -> None:
    svc = Unstuck(
        generate=lambda p: '{"steps":[{"text":"x","category":"admin","est_minutes":3}]}',
        store=Store(":memory:"),
    )

    ui = app.build_ui(svc)

    assert ui is not None
    assert isinstance(ui, gr.Blocks)


def test_summary_html_empty_rows() -> None:
    assert app.summary_html([]) == ""


def test_summary_html_unlogged_rows() -> None:
    html = app.summary_html(
        [
            {
                "logged": False,
                "actual_minutes": None,
                "calibrated_minutes": 10,
                "raw_minutes": 8,
            },
            {
                "logged": False,
                "actual_minutes": None,
                "calibrated_minutes": 20,
                "raw_minutes": 15,
            },
        ]
    )

    assert "30" in html
    assert "23" in html


def test_summary_html_mixed_logged_rows() -> None:
    html = app.summary_html(
        [
            {
                "logged": True,
                "actual_minutes": 12,
                "calibrated_minutes": 10,
                "raw_minutes": 15,
            },
            {
                "logged": False,
                "actual_minutes": None,
                "calibrated_minutes": 20,
                "raw_minutes": 15,
            },
        ]
    )

    assert "32" in html
    assert "30" in html
    assert "1/2 done" in html


def test_plan_markdown_mixed_rows_golden() -> None:
    rows = [
        {
            "text": "Open the tax folder",
            "logged": True,
            "actual_minutes": 3,
            "calibrated_minutes": 4,
        },
        {
            "text": "Find the latest payslip",
            "logged": False,
            "actual_minutes": None,
            "calibrated_minutes": 7,
        },
        {
            "text": "Email accountant",
            "logged": True,
            "actual_minutes": 5,
            "calibrated_minutes": 8,
        },
    ]

    markdown = app.plan_markdown("  Sort tax paperwork  ", rows)

    assert markdown == (
        "## Sort tax paperwork\n"
        "\n"
        "- [x] Open the tax folder (took 3 min)\n"
        "- [ ] Find the latest payslip (~7 min)\n"
        "- [x] Email accountant (took 5 min)\n"
        "\n"
        "Total for you: ~15 min"
    )


def test_plan_markdown_empty_rows() -> None:
    assert app.plan_markdown("Task", []) == ""


def test_build_ui_does_not_call_backend() -> None:
    def fail(_prompt: str) -> str:
        raise RuntimeError("backend unavailable")

    svc = Unstuck(generate=fail, store=Store(":memory:"))

    ui = app.build_ui(svc)

    assert isinstance(ui, gr.Blocks)


def test_parse_import_imports_file_and_returns_status(tmp_path) -> None:
    payload = {
        "tasks": [],
        "steps": [],
        "records": [
            {
                "step_id": 99,
                "category": "admin",
                "est_minutes": 5,
                "actual_minutes": 8,
                "completed_at": 456.0,
            }
        ],
    }
    path = tmp_path / "unstuck.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    status = app.parse_import(str(path), Store(":memory:"))

    assert status == "Imported 1 records (0 duplicates skipped)"


def test_finish_minutes_manual_wins_over_timer() -> None:
    assert app.finish_minutes(7.6, started_at=100.0, now=700.0) == 8


def test_finish_minutes_timer_rounds_and_floors_at_one() -> None:
    assert app.finish_minutes(None, started_at=100.0, now=250.0) == 2
    assert app.finish_minutes(None, started_at=100.0, now=130.0) == 1


def test_finish_minutes_neither_set_returns_none() -> None:
    assert app.finish_minutes(None, started_at=None, now=100.0) is None


def test_finish_minutes_non_positive_manual_falls_through() -> None:
    assert app.finish_minutes(0, started_at=100.0, now=250.0) == 2
    assert app.finish_minutes(-1, started_at=None, now=250.0) is None


def test_snapshot_writes_rows_json_to_store() -> None:
    store = Store(":memory:")
    rows = [{"step_id": 1, "text": "Open doc", "logged": False}]

    app.snapshot(store, "Write review", rows)

    saved = store.load_plan()
    assert saved is not None
    task, rows_json = saved
    assert task == "Write review"
    assert json.loads(rows_json) == rows


def test_restore_roundtrips_saved_rows_and_task() -> None:
    store = Store(":memory:")
    rows = [
        {
            "step_id": 1,
            "text": "Open doc",
            "category": "admin",
            "raw_minutes": 5,
            "calibrated_minutes": 7,
            "logged": True,
            "actual_minutes": 8,
            "started_at": None,
        },
        {
            "step_id": 2,
            "text": "Draft notes",
            "category": "creative",
            "raw_minutes": 10,
            "calibrated_minutes": 12,
            "logged": False,
            "actual_minutes": None,
            "started_at": 1234.5,
        },
    ]
    app.snapshot(store, "Write review", rows)

    restored_rows, readout, summary, task_update = app.restore_snapshot(
        store, lambda: "learned readout"
    )

    assert restored_rows == rows
    assert readout == "learned readout"
    assert "20" in summary
    assert task_update["value"] == "Write review"


def test_restore_corrupted_rows_json_yields_empty_state() -> None:
    store = Store(":memory:")
    store.save_plan("Write review", "{")

    rows, readout, summary, task_update = app.restore_snapshot(
        store, lambda: "learned readout"
    )

    assert rows == []
    assert readout == "learned readout"
    assert summary == ""
    assert "value" not in task_update
