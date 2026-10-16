"""Formazioni probabili: parsing, nomi, affidabilità e client senza rete."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx

from sports_data.predicted.client import FotmobClient, FotmobError
from sports_data.predicted.names import SquadPlayer, clubs_match, match_squad_player, normalize_club
from sports_data.predicted.parse import parse_lineup_payload, parse_matches_by_date
from sports_data.predicted.validate import (
    RELIABILITY_PARTIAL,
    RELIABILITY_REJECTED,
    RELIABILITY_UNVERIFIED,
    RELIABILITY_VALIDATED,
    blocks_selection,
    check_side,
    classify_reliability,
    grids_for_starters,
    side_starters,
    starter_key,
)


def _player(name: str, *, fotmob_id: int | None = None, **extra: object) -> dict:
    payload: dict[str, object] = {"name": name, "id": fotmob_id or abs(hash(name)) % 100000}
    payload.update(extra)
    return payload


def test_parse_predicted_lineup_shape() -> None:
    payload = {
        "lineup": {
            "lineupType": "predicted",
            "source": "enetpulse",
            "homeTeam": {
                "name": "Juventus",
                "formation": "4-2-3-1",
                "coach": {"name": "Thiago Motta"},
                "starters": [
                    {
                        "id": 701154,
                        "name": "Kylian Mbappé",
                        "positionId": 115,
                        "shirtNumber": "10",
                        "marketValue": 120694930,
                        "horizontalLayout": 50,
                        "verticalLayout": 12,
                    }
                ],
                "unavailable": [
                    {
                        "id": 846033,
                        "name": "Vinícius Júnior",
                        "unavailability": {
                            "type": "suspension",
                            "expectedReturn": "Early November 2026",
                            "expectedReturnDate": "2026-11-08T17:00:00Z",
                        },
                    }
                ],
            },
            "awayTeam": {"name": "Lazio", "formation": "4-3-3", "starters": [], "unavailable": []},
        }
    }
    parsed = parse_lineup_payload(payload)
    assert parsed.lineup_type == "predicted"
    assert parsed.source == "enetpulse"
    assert parsed.home is not None
    assert parsed.home.formation == "4-2-3-1"
    assert parsed.home.coach_name == "Thiago Motta"
    starter = parsed.home.players[0]
    assert starter.name == "Kylian Mbappé"
    assert starter.shirt_number == 10
    assert starter.layout_x == 50
    assert parsed.home.players[1].is_unavailable
    assert parsed.home.players[1].unavailability_type == "suspension"
    assert parsed.home.players[1].expected_return_at == datetime(2026, 11, 8, 17, 0, tzinfo=UTC)


def test_confirmed_is_not_inferred_from_predicted() -> None:
    assert parse_lineup_payload({"lineup": {"lineupType": "predicted"}}).lineup_type == "predicted"
    assert parse_lineup_payload({"lineup": {"lineupType": "official"}}).lineup_type == "confirmed"
    assert parse_lineup_payload({"lineup": {"lineupType": "maybe"}}).lineup_type == "unknown"
    assert parse_lineup_payload([]).warnings == ("invalid_schema",)


def test_by_date_accepts_wrapper_shapes() -> None:
    direct = parse_matches_by_date(
        {"matches": [{"id": 5749705, "home": {"name": "Juventus"}, "away": {"name": "Lazio"}}]}
    )
    nested = parse_matches_by_date(
        {
            "leagues": [
                {
                    "matches": [
                        {
                            "matchId": 1,
                            "homeTeam": {"name": "Lille"},
                            "awayTeam": {"shortName": "Rennes"},
                        }
                    ]
                }
            ]
        }
    )
    assert direct[0].fotmob_match_id == 5749705
    assert nested[0].home_name == "Lille"
    assert nested[0].away_name == "Rennes"


def test_club_aliases_do_not_use_fotmob_ids() -> None:
    assert clubs_match("Juventus", "Juventus FC")
    assert clubs_match("Bayer Leverkusen", "Bayer 04 Leverkusen")
    assert clubs_match("Manchester United", "Man United")
    assert clubs_match("AC Milan", "Milan")
    assert not clubs_match("Inter", "Milan")
    assert normalize_club("Paris Saint-Germain") == "paris saint germain"


def test_player_match_is_unique_or_nothing() -> None:
    kylian = uuid4()
    silva_a = uuid4()
    silva_b = uuid4()
    squad = [
        SquadPlayer(kylian, "Kylian Mbappé", "Kylian", "Mbappé"),
        SquadPlayer(silva_a, "Thiago Silva", "Thiago", "Silva"),
        SquadPlayer(silva_b, "Fabio Silva", "Fabio", "Silva"),
    ]
    assert match_squad_player("K. Mbappé", squad) == kylian
    assert match_squad_player("Silva", squad) is None


def test_reliability_requires_eleven_unique_mapped_starters() -> None:
    home_players = tuple(
        parse_lineup_payload(
            {
                "lineup": {
                    "homeTeam": {
                        "name": "Home",
                        "formation": "4-3-3",
                        "starters": [
                            _player(f"Home {index}", fotmob_id=index + 1) for index in range(11)
                        ],
                    }
                }
            }
        ).home.players  # type: ignore[union-attr]
    )
    side = parse_lineup_payload(
        {
            "lineup": {
                "homeTeam": {
                    "name": "Home",
                    "formation": "4-3-3",
                    "starters": [
                        _player(f"Home {index}", fotmob_id=index + 1) for index in range(11)
                    ],
                },
                "awayTeam": {
                    "name": "Away",
                    "formation": "4-4-2",
                    "starters": [
                        _player(f"Away {index}", fotmob_id=index + 20) for index in range(11)
                    ],
                },
            }
        }
    )
    assert side.home is not None and side.away is not None
    mapped = {starter_key(player) for player in side_starters(side.home)} | {
        starter_key(player) for player in side_starters(side.away)
    }
    full = classify_reliability(
        check_side(side.home, mapped_starter_keys=mapped),
        check_side(side.away, mapped_starter_keys=mapped),
        player_count=len(side.home.players) + len(side.away.players),
    )
    assert full.code == RELIABILITY_VALIDATED

    none_mapped = classify_reliability(
        check_side(side.home, mapped_starter_keys=set()),
        check_side(side.away, mapped_starter_keys=set()),
        player_count=22,
    )
    assert none_mapped.code == RELIABILITY_UNVERIFIED

    partial = classify_reliability(
        check_side(side.home, mapped_starter_keys={starter_key(side_starters(side.home)[0])}),
        check_side(side.away, mapped_starter_keys=set()),
        player_count=22,
    )
    assert partial.code == RELIABILITY_PARTIAL

    empty = classify_reliability(
        check_side(None, mapped_starter_keys=set()),
        check_side(None, mapped_starter_keys=set()),
        player_count=0,
    )
    assert empty.code == RELIABILITY_REJECTED
    assert home_players


def test_duplicate_and_unavailable_starter_are_warnings() -> None:
    same = _player("Same", fotmob_id=7)
    parsed = parse_lineup_payload(
        {
            "lineup": {
                "homeTeam": {
                    "name": "Home",
                    "formation": "4-3-3",
                    "starters": [same, same],
                    "unavailable": [
                        {
                            "id": 7,
                            "name": "Same",
                            "unavailability": {"type": "injury", "expectedReturn": "Doubtful"},
                        }
                    ],
                }
            }
        }
    )
    check = check_side(parsed.home, mapped_starter_keys=set())
    assert check.duplicate
    assert check.starter_also_unavailable
    assert side_starters(parsed.home) == []


def test_doubtful_does_not_block_and_suspension_does() -> None:
    kickoff = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
    assert not blocks_selection(
        mapped=True,
        unavailability_type="injury",
        uncertain=True,
        expected_return_at=None,
        kickoff_at=kickoff,
    )
    assert blocks_selection(
        mapped=True,
        unavailability_type="suspension",
        uncertain=False,
        expected_return_at=datetime(2026, 11, 8, 17, 0, tzinfo=UTC),
        kickoff_at=kickoff,
    )
    assert not blocks_selection(
        mapped=False,
        unavailability_type="suspension",
        uncertain=False,
        expected_return_at=None,
        kickoff_at=kickoff,
    )
    assert not blocks_selection(
        mapped=True,
        unavailability_type="suspension",
        uncertain=False,
        expected_return_at=datetime(2026, 10, 18, 17, 0, tzinfo=UTC),
        kickoff_at=kickoff,
    )


def test_grids_put_the_isolated_goalkeeper_on_row_one() -> None:
    parsed = parse_lineup_payload(
        {
            "lineup": {
                "homeTeam": {
                    "name": "Home",
                    "formation": "4-3-3",
                    "starters": [
                        {"id": 1, "name": "GK", "horizontalLayout": 50, "verticalLayout": 90},
                        {"id": 2, "name": "D1", "horizontalLayout": 20, "verticalLayout": 70},
                        {"id": 3, "name": "D2", "horizontalLayout": 40, "verticalLayout": 70},
                        {"id": 4, "name": "D3", "horizontalLayout": 60, "verticalLayout": 70},
                        {"id": 5, "name": "D4", "horizontalLayout": 80, "verticalLayout": 70},
                        {"id": 6, "name": "C1", "horizontalLayout": 30, "verticalLayout": 45},
                        {"id": 7, "name": "C2", "horizontalLayout": 50, "verticalLayout": 45},
                        {"id": 8, "name": "C3", "horizontalLayout": 70, "verticalLayout": 45},
                        {"id": 9, "name": "A1", "horizontalLayout": 25, "verticalLayout": 15},
                        {"id": 10, "name": "A2", "horizontalLayout": 50, "verticalLayout": 15},
                        {"id": 11, "name": "A3", "horizontalLayout": 75, "verticalLayout": 15},
                    ],
                }
            }
        }
    )
    assert parsed.home is not None
    grids = grids_for_starters(side_starters(parsed.home))
    assert grids["id:1"] == "1:1"
    assert grids["id:9"].startswith("4:")


def test_client_retries_429_and_never_puts_the_key_in_the_error() -> None:
    secret = "super-secret-rapidapi-key"
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-rapidapi-key"] == secret
        assert secret not in str(request.url)
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"key": secret})
        return httpx.Response(200, json={"lineup": {"lineupType": "predicted"}})

    sleeps: list[float] = []
    with FotmobClient(
        secret,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    ) as client:
        first = client.lineups(5749705)
        second = client.lineups(5749705)
    assert first["lineup"]["lineupType"] == "predicted"
    assert second == first
    assert calls["n"] == 2
    assert client.requests_made == 2

    def denied(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": secret})

    with FotmobClient(secret, transport=httpx.MockTransport(denied), sleep=sleeps.append) as client:
        try:
            client.lineups(1)
        except FotmobError as exc:
            assert secret not in str(exc)
            assert exc.status == 401
        else:
            raise AssertionError("expected auth error")
