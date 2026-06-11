from __future__ import annotations

import importlib
import sys
import types

import pytest


def reload_backend(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    sys.modules.pop("unstuck.backend", None)
    import unstuck.backend

    return importlib.reload(unstuck.backend)


def test_nebius_backend_uses_openai_compatible_inference_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeInferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls["init_args"] = args
            calls["init_kwargs"] = kwargs

        def chat_completion(self, **kwargs: object) -> object:
            calls["chat_completion_kwargs"] = kwargs
            message = types.SimpleNamespace(content="ok")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.InferenceClient = FakeInferenceClient
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setenv("UNSTUCK_BACKEND", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    assert calls["init_kwargs"] == {
        "base_url": backend.NEBIUS_BASE_URL,
        "api_key": "dummy",
    }
    assert calls["chat_completion_kwargs"] == {
        "model": backend.NEBIUS_MODEL,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 512,
        "temperature": 0,
    }


def test_nebius_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSTUCK_BACKEND", "nebius")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="NEBIUS_API_KEY"):
        reload_backend(monkeypatch)


def test_unknown_backend_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSTUCK_BACKEND", "bogus")

    with pytest.raises(ValueError, match="bogus"):
        reload_backend(monkeypatch)
