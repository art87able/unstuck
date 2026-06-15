from __future__ import annotations

import math
import os
from dataclasses import dataclass
from statistics import median
from typing import Any

RECALL_THRESHOLD = float(os.environ.get("UNSTUCK_RECALL_THRESHOLD", "0.80"))
MAX_DISMISSALS = 2


@dataclass
class Match:
    index: int
    similarity: float
    entry: dict[str, Any]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def select(
    query_vec: list[float] | None,
    history: list[dict[str, Any]],
    threshold: float = RECALL_THRESHOLD,
) -> Match | None:
    """Return the highest-cosine history entry at/above threshold, skipping entries
    dismissed >= MAX_DISMISSALS times or lacking an embedding. Pure; no I/O."""
    if not query_vec:
        return None
    best: Match | None = None
    for index, entry in enumerate(history):
        if int(entry.get("dismissals", 0)) >= MAX_DISMISSALS:
            continue
        vec = entry.get("embedding")
        if not vec:
            continue
        similarity = _cosine(query_vec, list(vec))
        if similarity >= threshold and (best is None or similarity > best.similarity):
            best = Match(index=index, similarity=similarity, entry=entry)
    return best


def seed_estimates(
    rows: list[dict[str, Any]], entry: dict[str, Any]
) -> list[dict[str, Any]]:
    """Override calibrated_minutes for rows whose category has a real duration in the
    matched entry (median of that category's actuals); leave others untouched. Pure."""
    by_category: dict[str, list[int]] = {}
    for duration in entry.get("durations", []):
        by_category.setdefault(str(duration["category"]), []).append(
            int(duration["actual_minutes"])
        )

    seeded: list[dict[str, Any]] = []
    for row in rows:
        actuals = by_category.get(str(row.get("category")))
        if actuals:
            new_row = dict(row)
            new_row["calibrated_minutes"] = max(1, int(round(median(actuals))))
            seeded.append(new_row)
        else:
            seeded.append(row)
    return seeded
