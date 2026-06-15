from __future__ import annotations

import json

import pytest

gr = pytest.importorskip("gradio")

import app
from unstuck.prompts import GRANULARITY_RULES
from unstuck.service import Unstuck
from unstuck.store import Store


def test_next_step_id_picks_first_unlogged_row() -> None:
    rows = [
        {"step_id": 1, "logged": False},
        {"step_id": 2, "logged": False},
    ]

    assert app.next_step_id(rows) == 1


def test_next_step_id_all_logged_returns_none() -> None:
    rows = [
        {"step_id": 1, "logged": True},
        {"step_id": 2, "logged": True},
    ]

    assert app.next_step_id(rows) is None


def test_next_step_id_empty_rows_returns_none() -> None:
    assert app.next_step_id([]) is None


def test_next_step_id_skips_logged_first_row() -> None:
    rows = [
        {"step_id": 1, "logged": True},
        {"step_id": 2, "logged": False},
    ]

    assert app.next_step_id(rows) == 2


def test_next_step_id_skips_skipped_first_row() -> None:
    rows = [
        {"step_id": 1, "logged": False, "skipped": True},
        {"step_id": 2, "logged": False, "skipped": False},
    ]

    assert app.next_step_id(rows) == 2


def test_next_step_id_all_logged_or_skipped_returns_none() -> None:
    rows = [
        {"step_id": 1, "logged": True, "skipped": False},
        {"step_id": 2, "logged": False, "skipped": True},
    ]

    assert app.next_step_id(rows) is None


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


def test_edit_row_text_strips_and_updates_matching_row() -> None:
    rows = [
        {"step_id": 1, "text": "before"},
        {"step_id": 2, "text": "replace me", "logged": False},
    ]

    edited = app.edit_row_text(rows, 2, "  better wording  ")

    assert edited == [
        rows[0],
        {"step_id": 2, "text": "better wording", "logged": False},
    ]
    assert rows[1]["text"] == "replace me"


def test_edit_row_text_empty_text_returns_rows_unchanged() -> None:
    rows = [{"step_id": 1, "text": "keep me"}]

    assert app.edit_row_text(rows, 1, "   ") == rows


def test_edit_row_text_unknown_step_id_returns_rows_unchanged() -> None:
    rows = [{"step_id": 1, "text": "keep me"}]

    assert app.edit_row_text(rows, 99, "new text") == rows


def test_add_manual_row_appends_admin_step_with_next_id_and_calibration() -> None:
    rows = [
        {"step_id": 4, "text": "existing"},
        {"step_id": 9, "text": "other"},
    ]
    records = [
        app.make_record("admin", 5, 10, 1.0),
        app.make_record("admin", 5, 10, 2.0),
        app.make_record("admin", 5, 10, 3.0),
    ]

    updated = app.add_manual_row(rows, "  Email Sam  ", 7.6, records)

    assert updated[:-1] == rows
    assert updated[-1] == {
        "step_id": 10,
        "text": "Email Sam",
        "category": "admin",
        "raw_minutes": 8,
        "calibrated_minutes": 16,
        "logged": False,
        "skipped": False,
        "actual_minutes": None,
        "started_at": None,
    }
    assert len(rows) == 2


def test_add_manual_row_empty_rows_start_at_one_and_default_to_ten_minutes() -> None:
    updated = app.add_manual_row([], "Pay bill", None, [])

    assert updated == [
        {
            "step_id": 1,
            "text": "Pay bill",
            "category": "admin",
            "raw_minutes": 10,
            "calibrated_minutes": 10,
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "started_at": None,
        }
    ]


def test_add_manual_row_empty_text_returns_rows_unchanged() -> None:
    rows = [{"step_id": 1, "text": "keep me"}]

    assert app.add_manual_row(rows, "  ", 5, []) == rows


def test_undo_row_resets_resolved_row_and_removes_record_timestamp() -> None:
    other = {
        "step_id": 1,
        "logged": False,
        "skipped": False,
        "actual_minutes": None,
        "started_at": None,
    }
    rows = [
        other,
        {
            "step_id": 2,
            "logged": True,
            "skipped": False,
            "actual_minutes": 12,
            "started_at": None,
            "record_at": 456.0,
        },
    ]

    undone = app.undo_row(rows, 2)

    assert undone == [
        other,
        {
            "step_id": 2,
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "started_at": None,
        },
    ]
    assert rows[1]["logged"] is True
    assert rows[1]["record_at"] == 456.0


def test_undo_row_resets_skipped_row() -> None:
    rows = [
        {
            "step_id": 1,
            "logged": False,
            "skipped": True,
            "actual_minutes": None,
            "started_at": 123.0,
        },
    ]

    assert app.undo_row(rows, 1) == [
        {
            "step_id": 1,
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "started_at": None,
        }
    ]


def test_undo_row_unknown_step_id_returns_rows_unchanged() -> None:
    rows = [{"step_id": 1, "logged": True, "record_at": 456.0}]

    undone = app.undo_row(rows, 99)

    assert undone == rows
    assert undone is not rows


def test_remove_record_removes_one_exact_timestamp_match() -> None:
    records = [
        app.make_record("admin", 5, 8, 100.0),
        app.make_record("admin", 5, 8, 200.0),
        app.make_record("creative", 5, 8, 200.0),
    ]

    updated = app.remove_record(records, "admin", 5, 8, 200.0)

    assert updated == [
        app.make_record("admin", 5, 8, 100.0),
        app.make_record("creative", 5, 8, 200.0),
    ]
    assert records[1] == app.make_record("admin", 5, 8, 200.0)


def test_remove_record_without_timestamp_removes_last_field_match() -> None:
    records = [
        app.make_record("admin", 5, 8, 100.0),
        app.make_record("admin", 5, 9, 150.0),
        app.make_record("admin", 5, 8, 200.0),
    ]

    assert app.remove_record(records, "admin", 5, 8, None) == [
        app.make_record("admin", 5, 8, 100.0),
        app.make_record("admin", 5, 9, 150.0),
    ]


def test_remove_record_no_match_returns_unchanged_copy() -> None:
    records = [app.make_record("admin", 5, 8, 100.0)]

    updated = app.remove_record(records, "admin", 5, 9, 100.0)

    assert updated == records
    assert updated is not records


def test_build_ui_accepts_injected_service() -> None:
    svc = Unstuck(
        generate=lambda p: '{"steps":[{"text":"x","category":"admin","est_minutes":3}]}',
        store=Store(":memory:"),
    )

    ui = app.build_ui(svc)

    assert ui is not None
    assert isinstance(ui, gr.Blocks)


def test_build_ui_manual_step_inputs_have_accessible_labels_and_valid_default() -> None:
    svc = Unstuck(
        generate=lambda p: '{"steps":[{"text":"x","category":"admin","est_minutes":3}]}',
        store=Store(":memory:"),
    )

    ui = app.build_ui(svc)
    components = list(ui.blocks.values())

    assert any(
        isinstance(component, gr.Textbox) and component.label == "Your own step"
        for component in components
    )
    assert any(
        isinstance(component, gr.Number)
        and component.label == "Minutes"
        and component.value == 5
        for component in components
    )


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


def test_summary_html_skipped_rows_contribute_nothing() -> None:
    html = app.summary_html(
        [
            {
                "logged": True,
                "skipped": False,
                "actual_minutes": 12,
                "calibrated_minutes": 10,
                "raw_minutes": 15,
            },
            {
                "logged": False,
                "skipped": True,
                "actual_minutes": None,
                "calibrated_minutes": 20,
                "raw_minutes": 25,
            },
            {
                "logged": False,
                "skipped": False,
                "actual_minutes": None,
                "calibrated_minutes": 7,
                "raw_minutes": 8,
            },
        ]
    )

    assert "For you: ~19 min total" in html
    assert "AI estimate: 23 min" in html
    assert "1/3 done" in html
    assert "1 skipped" in html


def test_completion_html_incomplete_plan_returns_empty() -> None:
    rows = [
        {
            "logged": True,
            "skipped": False,
            "actual_minutes": 8,
            "raw_minutes": 10,
        },
        {
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "raw_minutes": 5,
        },
    ]

    assert app.completion_html(rows) == ""


def test_completion_html_all_skipped_returns_empty() -> None:
    rows = [
        {
            "logged": False,
            "skipped": True,
            "actual_minutes": None,
            "raw_minutes": 10,
        },
        {
            "logged": False,
            "skipped": True,
            "actual_minutes": None,
            "raw_minutes": 5,
        },
    ]

    assert app.completion_html(rows) == ""


def test_completion_html_done_with_skips_golden() -> None:
    rows = [
        {
            "logged": True,
            "skipped": False,
            "actual_minutes": 12,
            "raw_minutes": 10,
        },
        {
            "logged": False,
            "skipped": True,
            "actual_minutes": None,
            "raw_minutes": 20,
        },
        {
            "logged": True,
            "skipped": False,
            "actual_minutes": 9,
            "raw_minutes": 5,
        },
    ]

    assert app.completion_html(rows) == (
        '<div class="completion">🎉 Done — 2 steps in 21 min. (1 skipped)<br>'
        "The AI guessed 15 min — you took 1.4× longer, and Unstuck now knows that."
        "</div>"
    )


def test_completion_html_longer_ratio_verdict() -> None:
    rows = [
        {
            "logged": True,
            "skipped": False,
            "actual_minutes": 11,
            "raw_minutes": 10,
        },
    ]

    assert (
        "The AI guessed 10 min — you took 1.1× longer, and Unstuck now knows that."
        in app.completion_html(rows)
    )


def test_completion_html_shorter_ratio_verdict() -> None:
    rows = [
        {
            "logged": True,
            "skipped": False,
            "actual_minutes": 9,
            "raw_minutes": 10,
        },
    ]

    assert (
        "The AI guessed 10 min — you beat it, finishing in 0.9× the time."
        in app.completion_html(rows)
    )


def test_completion_html_close_ratio_verdict() -> None:
    rows = [
        {
            "logged": True,
            "skipped": False,
            "actual_minutes": 10,
            "raw_minutes": 10,
        },
    ]

    assert (
        "The AI guessed 10 min — almost exactly right."
        in app.completion_html(rows)
    )


def test_patterns_html_empty_records() -> None:
    assert app.patterns_html([]) == ""


def test_patterns_html_sorts_categories_and_shows_counts() -> None:
    records = [
        {
            "category": "creative",
            "est_minutes": 10,
            "actual_minutes": 10,
            "completed_at": 2.0,
        },
        {
            "category": "admin",
            "est_minutes": 10,
            "actual_minutes": 20,
            "completed_at": 1.0,
        },
    ]

    html = app.patterns_html(records)

    assert html.startswith('<div class="patterns">')
    assert html.index('<span class="pattern-cat">admin</span>') < html.index(
        '<span class="pattern-cat">creative</span>'
    )
    assert '<span class="pattern-n">1 logged</span>' in html


def test_patterns_html_verdict_strings() -> None:
    records = []
    for offset, category, actual in [
        (0, "under", 20),
        (10, "over", 5),
        (20, "right", 10),
    ]:
        records.extend(
            {
                "category": category,
                "est_minutes": 10,
                "actual_minutes": actual,
                "completed_at": float(offset + index),
            }
            for index in range(3)
        )

    html = app.patterns_html(records)

    assert "~2.0× — you underestimate these" in html
    assert "~0.5× — you overestimate these" in html
    assert "~1.0× — your gut is right" in html


def test_patterns_html_bar_heights_are_clamped() -> None:
    records = [
        {
            "category": "admin",
            "est_minutes": 1,
            "actual_minutes": 10,
            "completed_at": 1.0,
        },
        {
            "category": "admin",
            "est_minutes": 100,
            "actual_minutes": 1,
            "completed_at": 2.0,
        },
    ]

    html = app.patterns_html(records)

    assert 'style="height:36px"' in html
    assert 'style="height:4px"' in html


def test_patterns_html_uses_last_five_records_chronologically() -> None:
    records = [
        {
            "category": "admin",
            "est_minutes": 10,
            "actual_minutes": actual,
            "completed_at": float(completed_at),
        }
        for completed_at, actual in [
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 4),
            (5, 5),
            (6, 6),
            (7, 7),
        ]
    ]

    html = app.patterns_html(records)

    assert html.count('class="bar"') == 5
    assert 'title="est 10 → took 1 min"' not in html
    assert 'title="est 10 → took 2 min"' not in html
    assert html.index('title="est 10 → took 3 min"') < html.index(
        'title="est 10 → took 7 min"'
    )


def test_make_history_entry_shape() -> None:
    entry = app.make_history_entry(
        "clean kitchen",
        [0.1, 0.2],
        [{"text": "Grab a bag", "category": "admin", "est_minutes": 2}],
    )

    assert entry == {
        "text": "clean kitchen",
        "embedding": [0.1, 0.2],
        "breakdown": [{"text": "Grab a bag", "category": "admin", "est_minutes": 2}],
        "durations": [],
        "dismissals": 0,
    }


def test_history_from_data_defaults_to_empty() -> None:
    assert app._history_from_data({"records": [], "plan": None}) == []
    assert app._history_from_data(None) == []


def test_with_history_returns_new_data_without_mutating() -> None:
    data = {"records": [], "plan": None, "history": []}
    history = [app.make_history_entry("t", [1.0], [])]

    updated = app.with_history(data, history)

    assert updated["history"] == history
    assert data["history"] == []


def test_bump_dismissal_increments_one_entry() -> None:
    history = [
        app.make_history_entry("a", [1.0], []),
        app.make_history_entry("b", [0.0], []),
    ]

    updated = app.bump_dismissal(history, 1)

    assert updated[1]["dismissals"] == 1
    assert updated[0]["dismissals"] == 0
    assert history[1]["dismissals"] == 0  # original untouched


def test_bump_dismissal_out_of_range_returns_copy_unchanged() -> None:
    history = [app.make_history_entry("a", [1.0], [])]

    assert app.bump_dismissal(history, 9) == history


def test_record_duration_in_history_appends_to_entry() -> None:
    history = [app.make_history_entry("a", [1.0], [])]

    updated = app.record_duration_in_history(history, 0, "admin", 12)

    assert updated[0]["durations"] == [{"category": "admin", "actual_minutes": 12}]
    assert history[0]["durations"] == []  # original untouched


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


def test_plan_markdown_skipped_row_golden_line() -> None:
    rows = [
        {
            "text": "Open the tax folder",
            "logged": False,
            "skipped": True,
            "actual_minutes": None,
            "calibrated_minutes": 4,
        },
        {
            "text": "Find the latest payslip",
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "calibrated_minutes": 7,
        },
    ]

    markdown = app.plan_markdown("Sort tax paperwork", rows)

    assert "- [-] Open the tax folder (skipped)" in markdown
    assert "Total for you: ~7 min" in markdown


def test_plan_markdown_empty_rows() -> None:
    assert app.plan_markdown("Task", []) == ""


def test_build_ui_does_not_call_backend() -> None:
    def fail(_prompt: str) -> str:
        raise RuntimeError("backend unavailable")

    svc = Unstuck(generate=fail, store=Store(":memory:"))

    ui = app.build_ui(svc)

    assert isinstance(ui, gr.Blocks)


def test_make_record_returns_browser_state_record() -> None:
    assert app.make_record("admin", 5, 8, 456.0) == {
        "category": "admin",
        "est_minutes": 5,
        "actual_minutes": 8,
        "completed_at": 456.0,
    }


def test_export_payload_roundtrips_through_merge_records() -> None:
    records = [
        app.make_record("admin", 5, 8, 456.0),
        app.make_record("creative", 10, 12, 789.0),
    ]

    merged, imported, skipped = app.merge_records([], app.export_payload(records))

    assert merged == records
    assert imported == 2
    assert skipped == 0


def test_merge_records_skips_existing_duplicates() -> None:
    records = [app.make_record("admin", 5, 8, 456.0)]

    merged, imported, skipped = app.merge_records(records, app.export_payload(records))

    assert merged == records
    assert imported == 0
    assert skipped == 1


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        json.dumps([]),
        json.dumps({"tasks": [], "steps": []}),
        json.dumps({"records": "nope"}),
        json.dumps({"records": [None]}),
        json.dumps({"records": [{"category": 12, "est_minutes": 5, "actual_minutes": 8, "completed_at": 1.0}]}),
        json.dumps({"records": [{"category": "admin", "est_minutes": 0, "actual_minutes": 8, "completed_at": 1.0}]}),
        json.dumps({"records": [{"category": "admin", "est_minutes": 5, "actual_minutes": True, "completed_at": 1.0}]}),
        json.dumps({"records": [{"category": "admin", "est_minutes": 5, "actual_minutes": 8}]}),
    ],
)
def test_merge_records_bad_payloads_raise_value_error(payload: str) -> None:
    existing = [app.make_record("admin", 5, 8, 456.0)]

    with pytest.raises(ValueError):
        app.merge_records(existing, payload)

    assert existing == [app.make_record("admin", 5, 8, 456.0)]


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


def test_with_plan_returns_new_data_with_plan_snapshot() -> None:
    data = {"records": [app.make_record("admin", 5, 8, 456.0)], "plan": None}
    rows = [{"step_id": 1, "text": "Open doc", "logged": False}]

    updated = app.with_plan(data, "Write review", rows)

    assert updated == {
        "records": data["records"],
        "plan": {"task": "Write review", "rows": rows},
    }
    assert data["plan"] is None


def test_with_records_returns_new_data_with_records() -> None:
    data = {"records": [], "plan": {"task": "Write review", "rows": []}}
    records = [app.make_record("admin", 5, 8, 456.0)]

    updated = app.with_records(data, records)

    assert updated == {"records": records, "plan": data["plan"]}
    assert data["records"] == []


def test_restore_roundtrips_browser_plan_and_records() -> None:
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
    data = {
        "records": [app.make_record("admin", 5, 8, 456.0)],
        "plan": {"task": "Write review", "rows": rows},
    }

    restored_rows, readout, summary, patterns, task_update = app.restore_snapshot(
        data, lambda records: "learned readout" if records else ""
    )

    assert restored_rows == rows
    assert readout == "learned readout"
    assert "20" in summary
    assert "admin" in patterns
    assert task_update["value"] == "Write review"


def test_restore_malformed_browser_plan_yields_empty_state() -> None:
    data = {"records": [app.make_record("admin", 5, 8, 456.0)], "plan": {"rows": "bad"}}

    rows, readout, summary, patterns, task_update = app.restore_snapshot(
        data, lambda records: "learned readout" if records else ""
    )

    assert rows == []
    assert readout == "learned readout"
    assert summary == ""
    assert "admin" in patterns
    assert "value" not in task_update


def test_new_plan_clears_browser_plan_but_keeps_records() -> None:
    data = {
        "records": [app.make_record("admin", 5, 8, 456.0)],
        "plan": {"task": "Write review", "rows": [{"step_id": 1}]},
    }

    rows, readout, summary, patterns, task_update, updated = app.new_plan(
        data, lambda records: "pattern html" if records else ""
    )

    assert rows == []
    assert readout == ""
    assert summary == ""
    assert patterns == "pattern html"
    assert task_update["value"] == ""
    assert updated == {"records": data["records"], "plan": None}
    assert data["plan"] is not None


def test_break_down_calibrates_from_browser_records() -> None:
    """Regression: fresh breakdowns must calibrate from BrowserState records,
    not the (empty) server store."""

    def fake_generate(_prompt: str) -> str:
        return json.dumps(
            {
                "steps": [
                    {"text": "Open the folder", "category": "admin", "est_minutes": 10},
                ]
            }
        )

    service = Unstuck(generate=fake_generate, store=Store(":memory:"))
    ui = app.build_ui(service)
    ui.launch(prevent_thread_lock=True, server_port=7950, quiet=True)
    try:
        from gradio_client import Client

        client = Client("http://127.0.0.1:7950", verbose=False)
        # 3 records of admin running 2x long -> multiplier 2.0 -> 10 min becomes 20
        records = [
            {"category": "admin", "est_minutes": 5, "actual_minutes": 10, "completed_at": float(i)}
            for i in range(3)
        ]
        res = client.predict(
            "File my taxes", {"records": records, "plan": None}, api_name="/break_down"
        )
        summary = next(r for r in res if isinstance(r, str) and "summary" in r)
        assert "~20 min total" in summary
        assert "AI estimate: 10 min" in summary
    finally:
        ui.close()


def test_break_down_api_passes_tiny_granularity_to_prompt() -> None:
    prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {
                "steps": [
                    {"text": "Open the folder", "category": "admin", "est_minutes": 5},
                ]
            }
        )

    service = Unstuck(generate=fake_generate, store=Store(":memory:"))
    ui = app.build_ui(service)
    ui.launch(prevent_thread_lock=True, server_port=7951, quiet=True)
    try:
        from gradio_client import Client

        client = Client("http://127.0.0.1:7951", verbose=False)
        client.predict(
            "File my taxes",
            {"records": [], "plan": None},
            "tiny",
            api_name="/break_down",
        )

        assert GRANULARITY_RULES["tiny"] in prompts[0]
    finally:
        ui.close()


def test_share_text_complete_plan_golden() -> None:
    rows = [
        {
            "text": "Open the tax folder",
            "logged": True,
            "actual_minutes": 14,
            "calibrated_minutes": 8,
            "raw_minutes": 6,
        },
        {
            "text": "Email accountant",
            "logged": False,
            "skipped": True,
            "actual_minutes": None,
            "calibrated_minutes": 8,
            "raw_minutes": 5,
        },
        {
            "text": "File the return",
            "logged": True,
            "actual_minutes": 34,
            "calibrated_minutes": 30,
            "raw_minutes": 24,
        },
    ]
    assert app.share_text("Sort my taxes", rows) == (
        'Got unstuck: "Sort my taxes" — 2 steps in 48 min (the AI guessed 30).'
        " Made with Unstuck: https://build-small-hackathon-unstuck.hf.space"
    )


def test_share_text_in_progress_plan_golden() -> None:
    rows = [
        {
            "text": "Open the tax folder",
            "logged": True,
            "actual_minutes": 3,
            "calibrated_minutes": 4,
            "raw_minutes": 4,
        },
        {
            "text": "File the return",
            "logged": False,
            "actual_minutes": None,
            "calibrated_minutes": 25,
            "raw_minutes": 20,
        },
    ]
    assert app.share_text("Sort my taxes", rows) == (
        'Getting unstuck: "Sort my taxes" — 1 of 2 steps done, ~25 min to go.'
        " Made with Unstuck: https://build-small-hackathon-unstuck.hf.space"
    )


def test_share_text_empty_rows_returns_empty() -> None:
    assert app.share_text("anything", []) == ""


def test_share_text_blank_task_uses_fallback_title() -> None:
    rows = [
        {
            "text": "One step",
            "logged": False,
            "actual_minutes": None,
            "calibrated_minutes": 5,
            "raw_minutes": 5,
        }
    ]
    assert 'Getting unstuck: "my task"' in app.share_text("   ", rows)


def test_plan_ics_remaining_steps_golden() -> None:
    from datetime import datetime

    rows = [
        {
            "step_id": 1,
            "text": "Open the tax folder",
            "logged": True,
            "actual_minutes": 3,
            "calibrated_minutes": 4,
        },
        {
            "step_id": 2,
            "text": "Find the latest payslip",
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "calibrated_minutes": 10,
        },
        {
            "step_id": 3,
            "text": "Email accountant; ask about expenses, VAT",
            "logged": False,
            "skipped": False,
            "actual_minutes": None,
            "calibrated_minutes": 15,
        },
    ]
    ics = app.plan_ics("Sort taxes", rows, datetime(2026, 6, 13, 14, 30, 0))
    # only the two unlogged steps become events
    assert ics.count("BEGIN:VEVENT") == 2
    assert "\r\n" in ics  # RFC 5545 CRLF line endings
    # first event starts at the given time, 10 min long
    assert "DTSTART:20260613T143000" in ics
    assert "DURATION:PT10M" in ics
    # second event is back-to-back (14:40), 15 min, with commas/semicolons escaped
    assert "DTSTART:20260613T144000" in ics
    assert "DURATION:PT15M" in ics
    assert "SUMMARY:Email accountant\; ask about expenses\\, VAT" in ics
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.rstrip().endswith("END:VCALENDAR")


def test_plan_ics_all_done_returns_empty() -> None:
    from datetime import datetime

    rows = [
        {"step_id": 1, "text": "a", "logged": True, "actual_minutes": 5, "calibrated_minutes": 5},
        {"step_id": 2, "text": "b", "logged": False, "skipped": True, "actual_minutes": None, "calibrated_minutes": 5},
    ]
    assert app.plan_ics("done plan", rows, datetime(2026, 6, 13, 9, 0, 0)) == ""


def test_plan_ics_empty_rows_returns_empty() -> None:
    from datetime import datetime

    assert app.plan_ics("anything", [], datetime(2026, 6, 13, 9, 0, 0)) == ""


def test_restored_banner_shows_remaining_count() -> None:
    rows = [
        {"text": "a", "logged": True, "actual_minutes": 5, "calibrated_minutes": 5},
        {"text": "b", "logged": False, "skipped": False, "calibrated_minutes": 7},
        {"text": "c", "logged": False, "skipped": False, "calibrated_minutes": 9},
    ]
    banner = app.restored_banner_html(rows)
    assert "Restored your plan" in banner
    assert "2 steps left" in banner


def test_restored_banner_singular_step() -> None:
    rows = [
        {"text": "a", "logged": True, "actual_minutes": 5, "calibrated_minutes": 5},
        {"text": "b", "logged": False, "skipped": False, "calibrated_minutes": 7},
    ]
    assert "1 step left" in app.restored_banner_html(rows)


def test_restored_banner_hidden_when_complete_or_empty() -> None:
    done = [
        {"text": "a", "logged": True, "actual_minutes": 5, "calibrated_minutes": 5},
        {"text": "b", "logged": False, "skipped": True, "calibrated_minutes": 5},
    ]
    assert app.restored_banner_html(done) == ""
    assert app.restored_banner_html([]) == ""


def test_break_down_uses_recall_exemplar_and_seeds_estimates() -> None:
    """A pre-seeded history entry with a real 30-min admin duration should both
    inject its breakdown as an exemplar AND seed the admin estimate to 30."""
    prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {"steps": [{"text": "Open the inbox", "category": "admin", "est_minutes": 10}]}
        )

    service = Unstuck(generate=fake_generate, store=Store(":memory:"))
    # Fake embed: identical vector for every task -> guaranteed cosine 1.0 match.
    ui = app.build_ui(service, embed=lambda text: [1.0, 0.0])
    ui.launch(prevent_thread_lock=True, server_port=7952, quiet=True)
    try:
        from gradio_client import Client

        client = Client("http://127.0.0.1:7952", verbose=False)
        history = [
            {
                "text": "tidy my inbox",
                "embedding": [1.0, 0.0],
                "breakdown": [
                    {"text": "Open the inbox", "category": "admin", "est_minutes": 10}
                ],
                "durations": [{"category": "admin", "actual_minutes": 30}],
                "dismissals": 0,
            }
        ]
        res = client.predict(
            "clear my email backlog",
            {"records": [], "plan": None, "history": history},
            "regular",
            api_name="/break_down",
        )
        summary = next(r for r in res if isinstance(r, str) and "summary" in r)
        # Seeded "for you" estimate is the matched task's real 30 min, not 10.
        assert "~30 min total" in summary
        # The exemplar (a recalled Example line) reached the model prompt.
        assert any("Example: Task \"tidy my inbox\"" in p for p in prompts)
    finally:
        ui.close()
