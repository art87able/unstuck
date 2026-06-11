from __future__ import annotations

import pytest

gr = pytest.importorskip("gradio")

import app
from unstuck.service import Unstuck
from unstuck.store import Store


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


def test_build_ui_does_not_call_backend() -> None:
    def fail(_prompt: str) -> str:
        raise RuntimeError("backend unavailable")

    svc = Unstuck(generate=fail, store=Store(":memory:"))

    ui = app.build_ui(svc)

    assert isinstance(ui, gr.Blocks)
