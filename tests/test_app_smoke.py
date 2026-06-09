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
