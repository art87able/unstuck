from __future__ import annotations

import json
import os
import urllib.request

EMBED_BACKEND = os.environ.get("UNSTUCK_EMBED_BACKEND", "nebius")
NEBIUS_EMBED_BASE_URL = os.environ.get(
    "NEBIUS_EMBED_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
)
NEBIUS_EMBED_MODEL = os.environ.get("NEBIUS_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
_TIMEOUT = float(os.environ.get("UNSTUCK_EMBED_TIMEOUT", "10"))


def _http_post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    """POST JSON, return decoded JSON. The single network seam — mocked in tests."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _embed_nebius(text: str, key: str) -> list[float]:
    url = NEBIUS_EMBED_BASE_URL.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {"model": NEBIUS_EMBED_MODEL, "input": text}
    body = _http_post_json(url, headers, payload)
    return [float(value) for value in body["data"][0]["embedding"]]


def embed(text: str) -> list[float] | None:
    """Embed text for recall. Returns None whenever recall cannot run (disabled
    backend, missing key, or any error) so recall stays strictly additive."""
    if EMBED_BACKEND == "nebius":
        key = os.environ.get("NEBIUS_API_KEY")
        if not key:
            return None
        try:
            return _embed_nebius(text, key)
        except Exception:
            return None
    return None
