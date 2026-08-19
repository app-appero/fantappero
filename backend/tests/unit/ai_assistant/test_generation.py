"""Unit tests for deterministic generation formatting helpers (EP10-01)."""

from __future__ import annotations

from ai_assistant.generation import MODEL_VERSION, format_minutes, format_rating


def test_format_rating_known_and_unknown() -> None:
    assert format_rating(7.456) == "7.46"
    assert format_rating(None) == "n/d"


def test_format_minutes_known_and_unknown() -> None:
    assert format_minutes(63.4) == "63'"
    assert format_minutes(None) == "n/d"


def test_model_version_is_stable_identifier() -> None:
    assert MODEL_VERSION == "deterministic-rules-v1"
