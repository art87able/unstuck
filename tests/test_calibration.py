from __future__ import annotations

from unstuck.calibration import MIN_SAMPLES, calibrate, multiplier


def test_no_history_returns_neutral_multiplier() -> None:
    assert multiplier("admin", []) == 1.0


def test_category_multiplier_uses_median_after_minimum_samples() -> None:
    records = [
        {"category": "admin", "est_minutes": 10, "actual_minutes": 20},
        {"category": "admin", "est_minutes": 10, "actual_minutes": 40},
        {"category": "admin", "est_minutes": 10, "actual_minutes": 30},
        {"category": "creative", "est_minutes": 10, "actual_minutes": 10},
    ]

    assert multiplier("admin", records) == 3.0


def test_falls_back_to_global_median_before_category_minimum_samples() -> None:
    assert MIN_SAMPLES == 3

    records = [
        {"category": "admin", "est_minutes": 10, "actual_minutes": 20},
        {"category": "admin", "est_minutes": 10, "actual_minutes": 40},
        {"category": "creative", "est_minutes": 10, "actual_minutes": 10},
    ]

    assert multiplier("admin", records) == 2.0


def test_records_with_zero_or_missing_estimate_or_actual_are_ignored() -> None:
    records = [
        {"category": "admin", "est_minutes": 10, "actual_minutes": 30},
        {"category": "admin", "est_minutes": 0, "actual_minutes": 90},
        {"category": "admin", "actual_minutes": 90},
        {"category": "admin", "est_minutes": 10, "actual_minutes": 0},
        {"category": "admin", "est_minutes": 10},
        {"category": "creative", "est_minutes": 10, "actual_minutes": 10},
    ]

    assert multiplier("admin", records) == 2.0


def test_calibrate_rounds_and_floors_at_one() -> None:
    assert calibrate(10, 3.0) == 30
    assert calibrate(10, 0.04) == 1
