from __future__ import annotations

from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any


MIN_SAMPLES = 3


def _ratios(
    records: Iterable[Mapping[str, Any]], category: str | None = None
) -> list[float]:
    ratios: list[float] = []
    for record in records:
        if category is not None and record.get("category") != category:
            continue

        est = record.get("est_minutes")
        actual = record.get("actual_minutes")
        if not est or not actual:
            continue

        ratios.append(float(actual) / float(est))

    return ratios


def multiplier(category: str, records: Iterable[Mapping[str, Any]]) -> float:
    """Return the learned time-bias multiplier for a category."""
    rows = list(records)
    category_ratios = _ratios(rows, category)
    if len(category_ratios) >= MIN_SAMPLES:
        return float(median(category_ratios))

    global_ratios = _ratios(rows)
    if global_ratios:
        return float(median(global_ratios))

    return 1.0


def calibrate(raw_minutes: int, mult: float) -> int:
    """Apply a multiplier while preserving a positive integer estimate."""
    return max(1, int(round(raw_minutes * mult)))
