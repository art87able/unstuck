from __future__ import annotations

from unstuck.recall import Match, select


def _entry(text: str, embedding: list[float], dismissals: int = 0) -> dict:
    return {
        "text": text,
        "embedding": embedding,
        "breakdown": [],
        "durations": [],
        "dismissals": dismissals,
    }


def test_select_returns_match_above_threshold() -> None:
    history = [_entry("clean kitchen", [1.0, 0.0])]

    match = select([1.0, 0.0], history, threshold=0.8)

    assert isinstance(match, Match)
    assert match.index == 0
    assert match.similarity == 1.0


def test_select_returns_none_below_threshold() -> None:
    history = [_entry("orthogonal", [0.0, 1.0])]

    assert select([1.0, 0.0], history, threshold=0.8) is None


def test_select_picks_highest_cosine() -> None:
    history = [
        _entry("near", [0.9, 0.1]),
        _entry("exact", [1.0, 0.0]),
    ]

    match = select([1.0, 0.0], history, threshold=0.5)

    assert match is not None
    assert match.index == 1


def test_select_skips_entries_dismissed_twice() -> None:
    history = [_entry("exact but dismissed", [1.0, 0.0], dismissals=2)]

    assert select([1.0, 0.0], history, threshold=0.5) is None


def test_select_skips_entries_without_embedding() -> None:
    history = [{"text": "no vec", "embedding": [], "dismissals": 0}]

    assert select([1.0, 0.0], history, threshold=0.5) is None


def test_select_empty_history_returns_none() -> None:
    assert select([1.0, 0.0], [], threshold=0.5) is None


def test_select_none_query_returns_none() -> None:
    assert select(None, [_entry("x", [1.0, 0.0])], threshold=0.5) is None
