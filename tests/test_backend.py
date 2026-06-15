from __future__ import annotations

import importlib
import sys
import types

import pytest


def reload_backend(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    sys.modules.pop("unstuck.backend", None)
    import unstuck.backend

    return importlib.reload(unstuck.backend)


def test_with_fallback_skips_fallback_when_primary_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = import_backend_for_factory(monkeypatch)
    calls: list[str] = []

    def primary(prompt: str) -> str:
        calls.append(f"primary:{prompt}")
        return "primary ok"

    def fallback(prompt: str) -> str:
        calls.append(f"fallback:{prompt}")
        return "fallback ok"

    generate = backend.with_fallback(primary, fallback)

    assert generate("hi") == "primary ok"
    assert calls == ["primary:hi"]


def test_with_fallback_returns_fallback_when_primary_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = import_backend_for_factory(monkeypatch)
    calls: list[str] = []

    def primary(prompt: str) -> str:
        calls.append(f"primary:{prompt}")
        raise RuntimeError("primary failed")

    def fallback(prompt: str) -> str:
        calls.append(f"fallback:{prompt}")
        return "fallback ok"

    generate = backend.with_fallback(primary, fallback)

    assert generate("hi") == "fallback ok"
    assert calls == ["primary:hi", "fallback:hi"]


def test_with_fallback_propagates_fallback_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = import_backend_for_factory(monkeypatch)

    def primary(prompt: str) -> str:
        raise RuntimeError(prompt)

    def fallback(prompt: str) -> str:
        raise ValueError(prompt)

    generate = backend.with_fallback(primary, fallback)

    with pytest.raises(ValueError, match="hi"):
        generate("hi")


def import_backend_for_factory(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class FakeInferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def chat_completion(self, **kwargs: object) -> object:
            message = types.SimpleNamespace(content="ok")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.InferenceClient = FakeInferenceClient
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setenv("UNSTUCK_BACKEND", "hf_inference")
    sys.modules.pop("unstuck.backend", None)
    return importlib.import_module("unstuck.backend")


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


def test_nebius_backend_respects_temperature_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeInferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

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
    monkeypatch.setenv("UNSTUCK_TEMPERATURE", "0.7")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    assert calls["chat_completion_kwargs"] == {
        "model": backend.NEBIUS_MODEL,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 512,
        "temperature": 0.7,
    }


def test_hf_inference_backend_respects_temperature_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeInferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls["init_args"] = args

        def chat_completion(self, **kwargs: object) -> object:
            calls["chat_completion_kwargs"] = kwargs
            message = types.SimpleNamespace(content="ok")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.InferenceClient = FakeInferenceClient
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setenv("UNSTUCK_BACKEND", "hf_inference")
    monkeypatch.setenv("UNSTUCK_TEMPERATURE", "0.7")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    assert calls["init_args"] == (backend.MODEL_ID,)
    assert calls["chat_completion_kwargs"] == {
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 512,
        "temperature": 0.7,
    }


def test_nebius_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSTUCK_BACKEND", "nebius")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="NEBIUS_API_KEY"):
        reload_backend(monkeypatch)


def _install_fake_llama_cpp(
    monkeypatch: pytest.MonkeyPatch, calls: dict[str, object]
) -> None:
    """Insert a fake `llama_cpp` so the offgrid backend never loads real weights
    or touches the network."""

    class FakeLlama:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls["init_args"] = args
            calls["init_kwargs"] = kwargs

        def create_chat_completion(self, **kwargs: object) -> object:
            calls["chat_kwargs"] = kwargs
            return {"choices": [{"message": {"content": "ok"}}]}

    fake_llama_cpp = types.ModuleType("llama_cpp")
    fake_llama_cpp.Llama = FakeLlama  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama_cpp)


def test_offgrid_backend_runs_on_a_local_gguf(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    _install_fake_llama_cpp(monkeypatch, calls)
    monkeypatch.setenv("UNSTUCK_BACKEND", "offgrid")
    monkeypatch.setenv("OFFGRID_GGUF_PATH", "/models/qwen3-4b.gguf")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    # On-device: a local file path is loaded — no base_url, no api_key, no network.
    init_kwargs = calls["init_kwargs"]
    assert isinstance(init_kwargs, dict)
    assert init_kwargs["model_path"] == "/models/qwen3-4b.gguf"
    assert calls["chat_kwargs"] == {
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 512,
        "temperature": 0,
    }


def test_offgrid_backend_respects_temperature_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    _install_fake_llama_cpp(monkeypatch, calls)
    monkeypatch.setenv("UNSTUCK_BACKEND", "offgrid")
    monkeypatch.setenv("OFFGRID_GGUF_PATH", "/models/qwen3-4b.gguf")
    monkeypatch.setenv("UNSTUCK_TEMPERATURE", "0.5")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    assert calls["chat_kwargs"] == {
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 512,
        "temperature": 0.5,
    }


def test_minicpm_backend_uses_minicpm_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeInferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls["init_kwargs"] = kwargs

        def chat_completion(self, **kwargs: object) -> object:
            calls["chat_completion_kwargs"] = kwargs
            message = types.SimpleNamespace(content="ok")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.InferenceClient = FakeInferenceClient
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setenv("UNSTUCK_BACKEND", "minicpm")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    assert calls["init_kwargs"] == {
        "base_url": backend.MINICPM_BASE_URL,
        "api_key": "dummy",
    }
    assert calls["chat_completion_kwargs"] == {
        "model": backend.MINICPM_MODEL,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 512,
        "temperature": 0,
    }


def test_nemotron_backend_passes_nemotron_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeInferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls["init_args"] = args

        def chat_completion(self, **kwargs: object) -> object:
            calls["chat_completion_kwargs"] = kwargs
            message = types.SimpleNamespace(content="ok")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.InferenceClient = FakeInferenceClient
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setenv("UNSTUCK_BACKEND", "nemotron")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")

    backend = reload_backend(monkeypatch)

    assert backend.generate("hi") == "ok"
    assert calls["chat_completion_kwargs"]["model"] == backend.NEMOTRON_MODEL


def test_unknown_backend_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSTUCK_BACKEND", "bogus")

    with pytest.raises(ValueError, match="bogus"):
        reload_backend(monkeypatch)
