from __future__ import annotations

import importlib
import sys
import types

import pytest


def reload_embeddings(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    sys.modules.pop("unstuck.embeddings", None)
    import unstuck.embeddings

    return importlib.reload(unstuck.embeddings)


def test_embed_posts_openai_shape_and_parses_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")
    embeddings = reload_embeddings(monkeypatch)

    calls: dict[str, object] = {}

    def fake_post(url: str, headers: dict, payload: dict) -> dict:
        calls["url"] = url
        calls["headers"] = headers
        calls["payload"] = payload
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr(embeddings, "_http_post_json", fake_post)

    vec = embeddings.embed("clean the kitchen")

    assert vec == [0.1, 0.2, 0.3]
    assert calls["url"] == "https://api.tokenfactory.nebius.com/v1/embeddings"
    assert calls["headers"]["Authorization"] == "Bearer dummy"
    assert calls["payload"] == {
        "model": embeddings.NEBIUS_EMBED_MODEL,
        "input": "clean the kitchen",
    }


def test_embed_returns_none_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "nebius")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    embeddings = reload_embeddings(monkeypatch)

    assert embeddings.embed("hi") is None


def test_embed_returns_none_when_backend_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "none")
    embeddings = reload_embeddings(monkeypatch)

    assert embeddings.embed("hi") is None


def test_embed_degrades_to_none_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSTUCK_EMBED_BACKEND", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "dummy")
    embeddings = reload_embeddings(monkeypatch)

    def boom(url: str, headers: dict, payload: dict) -> dict:
        raise RuntimeError("network down")

    monkeypatch.setattr(embeddings, "_http_post_json", boom)

    assert embeddings.embed("hi") is None
