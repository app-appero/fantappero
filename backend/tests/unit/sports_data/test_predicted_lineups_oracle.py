"""Integrazione Soccer-Oracle per le formazioni probabili: client, parsing, fallback.

Nessuna chiamata di rete reale: il client usa ``httpx.MockTransport`` e la
sincronizzazione usa sessioni/fixture finte (``MagicMock``/``SimpleNamespace``),
come già fatto per ``_probable_hints`` in ``test_probable_hints.py``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from sports_data.predicted.oracle_client import SoccerOracleClient, SoccerOracleError
from sports_data.predicted.oracle_parse import parse_oracle_lineups_response
from sports_data.predicted.sync import (
    _MISSING_KEY,
    PredictedSyncSummary,
    _add_oracle_player,
    _confident_shirt_match,
    _OracleSquadMember,
    _store_oracle_snapshot,
    _sync_via_oracle,
    sync_predicted_lineups,
)

# ---------------------------------------------------------------------------
# Client: nessuna rete reale, chiave mai nei log/errori.
# ---------------------------------------------------------------------------


def test_client_sends_service_key_header_and_never_leaks_it() -> None:
    secret = "super-secret-oracle-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-service-key"] == secret
        assert secret not in str(request.url)
        return httpx.Response(
            200,
            json={"count": 1, "fixtures": [{"fixture_id": 101, "lineup_type": None, "teams": []}]},
        )

    with SoccerOracleClient(
        secret, base_url="https://oracle.test", transport=httpx.MockTransport(handler)
    ) as client:
        payload = client.lineups([101])
    assert payload["fixtures"][0]["fixture_id"] == 101


def test_client_auth_error_does_not_leak_the_key() -> None:
    secret = "super-secret-oracle-key"

    def denied(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": secret})

    with SoccerOracleClient(
        secret, base_url="https://oracle.test", transport=httpx.MockTransport(denied)
    ) as client:
        with pytest.raises(SoccerOracleError) as excinfo:
            client.lineups([101])
    assert secret not in str(excinfo.value)
    assert excinfo.value.status == 403


def test_client_retries_5xx_then_gives_up() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    sleeps: list[float] = []
    with SoccerOracleClient(
        "key",
        base_url="https://oracle.test",
        max_retries=1,
        transport=httpx.MockTransport(flaky),
        sleep=sleeps.append,
    ) as client:
        with pytest.raises(SoccerOracleError) as excinfo:
            client.lineups([101])
    assert calls["n"] == 2  # tentativo iniziale + 1 retry
    assert excinfo.value.status == 503


def test_client_rejects_too_many_fixture_ids_without_a_network_call() -> None:
    def never(request: httpx.Request) -> httpx.Response:
        raise AssertionError("non deve chiamare la rete")

    with SoccerOracleClient(
        "key", base_url="https://oracle.test", transport=httpx.MockTransport(never)
    ) as client:
        with pytest.raises(SoccerOracleError):
            client.lineups(list(range(51)))


def test_links_bulk_posts_the_contract_shape() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"count": 1})

    with SoccerOracleClient(
        "key", base_url="https://oracle.test", transport=httpx.MockTransport(handler)
    ) as client:
        client.links_bulk(
            [
                {
                    "api_sports_id": 1,
                    "fotmob_id": 2,
                    "name": "Mario Rossi",
                    "birth_date": "1999-01-01",
                }
            ]
        )
    assert captured["body"]["source"] == "external_project"
    assert captured["body"]["links"][0]["api_sports_id"] == 1


# ---------------------------------------------------------------------------
# Parsing: payload malformati non devono far crashare il job.
# ---------------------------------------------------------------------------


def test_parse_well_formed_response() -> None:
    payload = {
        "count": 1,
        "fixtures": [
            {
                "fixture_id": 555,
                "lineup_type": "predicted",
                "source": "fotmob",
                "unmapped_starters": 1,
                "teams": [
                    {
                        "team_api_id": 10,
                        "formation": "4-3-3",
                        "starters": [
                            {
                                "name": "Mario Rossi",
                                "api_sports_id": None,
                                "fotmob_id": 999,
                                "identity_id": None,
                                "mapped": False,
                                "confidence": 0.0,
                                "shirt_number": 7,
                            }
                        ],
                        "bench": [],
                        "unavailable": [
                            {
                                "name": "Luca Bianchi",
                                "api_sports_id": 42,
                                "fotmob_id": 43,
                                "mapped": True,
                                "confidence": 1.0,
                                "shirt_number": 9,
                                "absence": {
                                    "type": "injury",
                                    "expected_return": "Doubtful",
                                    "expected_return_date": "2026-11-01T18:00:00Z",
                                    "certainty": "doubtful",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    parsed = parse_oracle_lineups_response(payload)
    lineup = parsed[555]
    assert lineup.lineup_type == "predicted"
    assert lineup.unmapped_starters == 1
    team = lineup.teams[0]
    assert team.starters[0].mapped is False
    assert team.starters[0].shirt_number == 7
    assert team.unavailable[0].absence_type == "injury"
    assert team.unavailable[0].absence_uncertain is True
    assert team.unavailable[0].absence_expected_return_at == datetime(
        2026, 11, 1, 18, 0, tzinfo=UTC
    )


def test_parse_malformed_payload_yields_nothing_not_an_exception() -> None:
    assert parse_oracle_lineups_response(None) == {}
    assert parse_oracle_lineups_response({}) == {}
    assert parse_oracle_lineups_response({"fixtures": "not-a-list"}) == {}
    assert parse_oracle_lineups_response({"fixtures": [{"no_fixture_id": True}]}) == {}
    # una fixture senza dati: lineup_type nullo e teams vuoto, non un crash.
    parsed = parse_oracle_lineups_response(
        {"fixtures": [{"fixture_id": 1, "lineup_type": None, "teams": []}]}
    )
    assert parsed[1].lineup_type is None
    assert parsed[1].teams == ()


# ---------------------------------------------------------------------------
# Riscontro interno (maglia + cognome) per i mapped=false di Soccer-Oracle.
# ---------------------------------------------------------------------------


def test_confident_shirt_match_requires_unique_shirt_and_surname() -> None:
    silva_a = uuid4()
    silva_b = uuid4()
    squad = [
        _OracleSquadMember(
            athlete_id=silva_a, provider_id=1, last_name="silva", shirt_number=10, birth_date=None
        ),
        _OracleSquadMember(
            athlete_id=silva_b,
            provider_id=2,
            last_name="silva",
            shirt_number=22,
            birth_date=date(2000, 1, 1),
        ),
    ]
    # maglia 22 + cognome "silva" individua un solo giocatore anche se il
    # cognome da solo e' ambiguo (due Silva in rosa).
    match = _confident_shirt_match("Fabio Silva", 22, squad)
    assert match is not None
    assert match.athlete_id == silva_b

    # senza numero di maglia non si rischia un abbinamento alla cieca.
    assert _confident_shirt_match("Fabio Silva", None, squad) is None

    # maglia che non esiste in rosa: nessun indizio forte, resta non abbinato.
    assert _confident_shirt_match("Fabio Silva", 99, squad) is None


def test_confident_shirt_match_stays_none_when_still_ambiguous() -> None:
    squad = [
        _OracleSquadMember(
            athlete_id=uuid4(), provider_id=1, last_name="silva", shirt_number=10, birth_date=None
        ),
        _OracleSquadMember(
            athlete_id=uuid4(), provider_id=2, last_name="silva", shirt_number=10, birth_date=None
        ),
    ]
    assert _confident_shirt_match("Thiago Silva", 10, squad) is None


# ---------------------------------------------------------------------------
# Salvataggio del giocatore: non abbinato, abbinato per ID, assente/infortunato.
# ---------------------------------------------------------------------------


def _oracle_player(**overrides: object) -> object:
    from sports_data.predicted.oracle_parse import OraclePlayer

    defaults: dict[str, object] = {
        "name": "Mario Rossi",
        "api_sports_id": None,
        "fotmob_id": None,
        "identity_id": None,
        "mapped": False,
        "confidence": 0.0,
        "shirt_number": None,
        "absence_type": None,
        "absence_label": None,
        "absence_expected_return_at": None,
        "absence_uncertain": False,
    }
    defaults.update(overrides)
    return OraclePlayer(**defaults)


def test_add_oracle_player_unmapped_stays_without_athlete_id_and_without_colour() -> None:
    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    player = _oracle_player(mapped=False, confidence=0.0, shirt_number=None)

    _add_oracle_player(
        session,
        snapshot=SimpleNamespace(id=uuid4()),
        player=player,
        side="home",
        club_id=uuid4(),
        squad=[],
        kickoff_at=None,
        is_starter=True,
        is_unavailable=False,
        min_confidence=0.6,
        sort_order=1,
        pending_links=[],
    )
    row = added[0]
    assert row.athlete_id is None


def test_add_oracle_player_below_confidence_threshold_is_not_trusted() -> None:
    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    session.scalar.return_value = SimpleNamespace(id=uuid4())  # un Athlete esisterebbe...
    player = _oracle_player(mapped=True, confidence=0.4, api_sports_id=42)  # ...ma sotto soglia

    _add_oracle_player(
        session,
        snapshot=SimpleNamespace(id=uuid4()),
        player=player,
        side="home",
        club_id=uuid4(),
        squad=[],
        kickoff_at=None,
        is_starter=True,
        is_unavailable=False,
        min_confidence=0.6,
        sort_order=1,
        pending_links=[],
    )
    row = added[0]
    assert row.athlete_id is None


def test_add_oracle_player_mapped_above_threshold_resolves_athlete_id() -> None:
    athlete_id = uuid4()
    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    session.scalar.return_value = SimpleNamespace(id=athlete_id)
    player = _oracle_player(mapped=True, confidence=1.0, api_sports_id=42)

    _add_oracle_player(
        session,
        snapshot=SimpleNamespace(id=uuid4()),
        player=player,
        side="home",
        club_id=uuid4(),
        squad=[],
        kickoff_at=None,
        is_starter=True,
        is_unavailable=False,
        min_confidence=0.6,
        sort_order=1,
        pending_links=[],
    )
    row = added[0]
    assert row.athlete_id == athlete_id


def test_add_oracle_player_unmapped_but_confident_shirt_match_queues_link() -> None:
    athlete_id = uuid4()
    squad = [
        _OracleSquadMember(
            athlete_id=athlete_id,
            provider_id=777,
            last_name="rossi",
            shirt_number=7,
            birth_date=date(1999, 5, 1),
        )
    ]
    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    player = _oracle_player(mapped=False, confidence=0.0, shirt_number=7, fotmob_id=321)
    pending_links: list[dict[str, object]] = []

    _add_oracle_player(
        session,
        snapshot=SimpleNamespace(id=uuid4()),
        player=player,
        side="home",
        club_id=uuid4(),
        squad=squad,
        kickoff_at=None,
        is_starter=True,
        is_unavailable=False,
        min_confidence=0.6,
        sort_order=1,
        pending_links=pending_links,
    )
    row = added[0]
    assert row.athlete_id == athlete_id
    assert pending_links == [
        {
            "api_sports_id": 777,
            "fotmob_id": 321,
            "name": "Mario Rossi",
            "birth_date": "1999-05-01",
        }
    ]


def test_add_oracle_player_unavailable_injured_blocks_selection() -> None:
    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    session.scalar.return_value = SimpleNamespace(id=uuid4())
    kickoff = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
    player = _oracle_player(
        mapped=True,
        confidence=1.0,
        api_sports_id=42,
        absence_type="injury",
        absence_label="Infortunato",
        absence_expected_return_at=datetime(2026, 11, 5, 12, 0, tzinfo=UTC),
        absence_uncertain=False,
    )

    _add_oracle_player(
        session,
        snapshot=SimpleNamespace(id=uuid4()),
        player=player,
        side="home",
        club_id=uuid4(),
        squad=[],
        kickoff_at=kickoff,
        is_starter=False,
        is_unavailable=True,
        min_confidence=0.6,
        sort_order=1,
        pending_links=[],
    )
    row = added[0]
    assert row.is_unavailable is True
    assert row.unavailability_type == "injury"
    assert row.blocks_selection is True


def test_add_oracle_player_doubtful_absence_does_not_block() -> None:
    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    session.scalar.return_value = SimpleNamespace(id=uuid4())
    player = _oracle_player(
        mapped=True,
        confidence=1.0,
        api_sports_id=42,
        absence_type="injury",
        absence_label="Doubtful",
        absence_uncertain=True,
    )

    _add_oracle_player(
        session,
        snapshot=SimpleNamespace(id=uuid4()),
        player=player,
        side="home",
        club_id=uuid4(),
        squad=[],
        kickoff_at=datetime(2026, 10, 20, 18, 0, tzinfo=UTC),
        is_starter=False,
        is_unavailable=True,
        min_confidence=0.6,
        sort_order=1,
        pending_links=[],
    )
    row = added[0]
    assert row.blocks_selection is False


# ---------------------------------------------------------------------------
# Fallback: API giu' o chiave assente.
# ---------------------------------------------------------------------------


def test_sync_without_client_and_without_oracle_sets_missing_key_message() -> None:
    session = MagicMock()
    summary = sync_predicted_lineups(session, None, oracle=None)
    assert summary.message == _MISSING_KEY
    session.scalars.assert_not_called()


def test_sync_falls_back_to_missing_key_when_oracle_down_and_no_fotmob_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = SimpleNamespace(
        id=uuid4(),
        provider_id=1001,
        home_club_id=uuid4(),
        away_club_id=uuid4(),
        sport_season_id=uuid4(),
        kickoff_at=datetime(2026, 10, 20, 18, 0, tzinfo=UTC),
        home_club=SimpleNamespace(provider_id=10, name="Home"),
        away_club=SimpleNamespace(provider_id=20, name="Away"),
    )
    monkeypatch.setattr(
        "sports_data.predicted.sync._candidate_fixtures", lambda *a, **k: [fixture]
    )
    monkeypatch.setattr(
        "sports_data.predicted.sync._has_recent_snapshot", lambda *a, **k: False
    )
    oracle = MagicMock()
    oracle.lineups.side_effect = SoccerOracleError(503, "down")
    session = MagicMock()

    summary = sync_predicted_lineups(session, None, oracle=oracle)
    assert summary.message == _MISSING_KEY
    oracle.lineups.assert_called_once()


def test_sync_via_oracle_all_or_nothing_propagates_failure_to_caller() -> None:
    fixture = SimpleNamespace(provider_id=1001)
    oracle = MagicMock()
    oracle.lineups.side_effect = SoccerOracleError(500, "boom")
    summary = PredictedSyncSummary()
    with pytest.raises(SoccerOracleError):
        _sync_via_oracle(MagicMock(), oracle, [fixture], summary, datetime.now(UTC), 0.6)


def test_sync_via_oracle_does_nothing_for_an_empty_fixture_list() -> None:
    oracle = MagicMock()
    summary = PredictedSyncSummary()
    _sync_via_oracle(MagicMock(), oracle, [], summary, datetime.now(UTC), 0.6)
    oracle.lineups.assert_not_called()


# ---------------------------------------------------------------------------
# Snapshot: nessun dato oggi non crea una riga vuota.
# ---------------------------------------------------------------------------


def test_store_oracle_snapshot_skips_when_no_lineup_data_yet() -> None:
    from sports_data.predicted.oracle_parse import OracleFixtureLineup

    session = MagicMock()
    added: list[object] = []
    session.add.side_effect = added.append
    fixture = SimpleNamespace(
        id=uuid4(),
        home_club=SimpleNamespace(provider_id=10),
        away_club=SimpleNamespace(provider_id=20),
        home_club_id=uuid4(),
        away_club_id=uuid4(),
        sport_season_id=uuid4(),
        kickoff_at=None,
    )
    summary = PredictedSyncSummary()
    lineup = OracleFixtureLineup(lineup_type=None, source=None, unmapped_starters=None, teams=())

    _store_oracle_snapshot(session, fixture, lineup, summary, datetime.now(UTC), 0.6, [])
    assert added == []
    assert summary.snapshots_saved == 0
