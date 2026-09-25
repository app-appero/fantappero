"""Unit tests for /injuries reason classification (OQ-11)."""

from __future__ import annotations

import pytest

from database.enums import PlayerAvailabilityCategory
from sports_data.availability.classify import KNOWN_REASONS, classify_availability_reason


@pytest.mark.parametrize("reason", sorted(KNOWN_REASONS))
def test_every_known_reason_classifies_without_falling_back(reason: str) -> None:
    """Ogni valore osservato su dati reali deve matchare la tabella fissa."""
    assert classify_availability_reason(reason) == KNOWN_REASONS[reason]


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("Knee Injury", PlayerAvailabilityCategory.INJURY),
        ("Red Card", PlayerAvailabilityCategory.SUSPENSION),
        ("Yellow Cards", PlayerAvailabilityCategory.SUSPENSION),
        ("Illness", PlayerAvailabilityCategory.ILLNESS),
        ("Coach's decision", PlayerAvailabilityCategory.OTHER),
    ],
)
def test_real_observed_values_classify_correctly(
    reason: str, expected: PlayerAvailabilityCategory
) -> None:
    assert classify_availability_reason(reason) == expected


def test_case_insensitive_match() -> None:
    assert classify_availability_reason("knee injury") == PlayerAvailabilityCategory.INJURY
    assert classify_availability_reason("KNEE INJURY") == PlayerAvailabilityCategory.INJURY


def test_unseen_value_falls_back_to_keyword_rules_not_nlp() -> None:
    """Un valore mai osservato non deve mai sollevare: fallback deterministico."""
    assert classify_availability_reason("Suspended For One Match") == (
        PlayerAvailabilityCategory.SUSPENSION
    )
    assert classify_availability_reason("Season-Ending Injury") == (
        PlayerAvailabilityCategory.INJURY
    )
    assert classify_availability_reason("Totally Unrecognized Reason") == (
        PlayerAvailabilityCategory.OTHER
    )


def test_missing_reason_is_other_not_a_crash() -> None:
    assert classify_availability_reason(None) == PlayerAvailabilityCategory.OTHER
    assert classify_availability_reason("") == PlayerAvailabilityCategory.OTHER
    assert classify_availability_reason("   ") == PlayerAvailabilityCategory.OTHER


# --------------------------------------------------------------------------
# map_player_availabilities — forma reale del payload /injuries (OQ-11),
# verificata con una chiamata live nel corso dell'indagine (non nel corpus
# offline: /injuries non era mai stato acquisito, vedi nota B4 generale).
# --------------------------------------------------------------------------


def test_map_player_availabilities_parses_real_payload_shape() -> None:
    from sports_data.provider.envelope import parse_envelope
    from sports_data.provider.mapping import map_player_availabilities

    payload = {
        "get": "injuries",
        "parameters": {"team": "487", "season": "2026"},
        "errors": [],
        "results": 2,
        "paging": {"current": 1, "total": 1},
        "response": [
            {
                "player": {
                    "id": 12345,
                    "name": "Example Player",
                    "type": "Missing Fixture",
                    "reason": "Knee Injury",
                },
                "team": {"id": 487, "name": "Example FC"},
                "fixture": {"id": 999001, "date": "2026-09-19T18:45:00+00:00"},
                "league": {"id": 135, "season": 2026},
            },
            {
                # Riga senza reason valorizzato: va scartata, non forzata a "".
                "player": {"id": 67890, "name": "No Reason Player", "type": "Questionable"},
                "team": {"id": 487, "name": "Example FC"},
                "fixture": {"id": 999001},
                "league": {"id": 135, "season": 2026},
            },
        ],
    }
    envelope = parse_envelope(payload, endpoint="/injuries", http_status=200)
    mapped = map_player_availabilities(
        envelope, competition_provider_id=135, season_year=2026
    )

    assert len(mapped) == 1
    row = mapped[0]
    assert row.athlete_provider_id == 12345
    assert row.club_provider_id == 487
    assert row.fixture_provider_id == 999001
    assert row.competition_provider_id == 135
    assert row.season_year == 2026
    assert row.status_type_raw == "Missing Fixture"
    assert row.reason_raw == "Knee Injury"
    assert row.provider_key == "12345:999001:135:2026"
