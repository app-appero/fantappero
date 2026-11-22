# ruff: noqa: F811
"""Valore di mercato e media stagionale nelle risposte del mercato e nella scheda (1.3).

``marketValue`` (crediti della lega) e ``seasonAverage`` su: listone della Rosa (da cui la app
ricava gli Svincolati), offerte di asta a buste e svincoli, lotto dell'asta live, calciatori
delle proposte di scambio; ``career`` nella scheda calciatore. Il ricalcolo passa
dall'endpoint dell'operatore.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _register_and_login,
    _trade_league,
    competition_ids,
    db_session,
)
from tests.integration.fantasy_turns.test_fantasy_turns import _promote_to_operator

from database.enums import FantasyRole, LeagueMemberRole
from fantasy_ratings.config import DEFAULT_FORMULA_VERSION
from fantasy_ratings.models import PlayerMatchRating
from fantasy_turns.models import FantasyRoundFixture
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from market.valuation import base_reference_value, credits_for_budget
from market.valuation_models import AthleteMarketValue
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete
from sports_data.season_stats.models import AthleteSeasonStat

REFRESH_URL = "/admin/listone/valori/ricalcola"


def _provider_row(
    db_session: Session,
    athlete: Athlete,
    *,
    season: int,
    rating: float | None,
    apps: int,
    club_provider_id: int = 1,
    club_name: str = "Club Storico",
) -> None:
    db_session.add(
        AthleteSeasonStat(
            athlete_provider_id=athlete.provider_id,
            athlete_id=athlete.id,
            season_year=season,
            source="provider",
            club_provider_id=club_provider_id,
            club_name=club_name,
            competition_provider_id=135,
            competition_name="Serie A",
            appearances=apps,
            minutes=apps * 80,
            rating=rating,
            goals=3,
            assists=2,
            goals_conceded=0,
            penalties_saved=0,
            yellow_cards=1,
            red_cards=0,
        )
    )


def _vote(db_session: Session, round_id: str, athlete: Athlete, display: float) -> None:
    """Una partita finita della stagione in corso con un nostro voto.

    Partita nuova (fuori dal turno aperto, che resterebbe «in corso» e chiuderebbe il mercato),
    stessa stagione e stessi club della prima partita del turno.
    """
    fixture_id = db_session.scalars(
        select(FantasyRoundFixture.fixture_id).where(FantasyRoundFixture.round_id == UUID(round_id))
    ).first()
    template = db_session.get(Fixture, fixture_id)
    assert template is not None
    fixture = Fixture(
        provider_id=template.provider_id + 900,
        sport_season_id=template.sport_season_id,
        home_club_id=template.home_club_id,
        away_club_id=template.away_club_id,
        kickoff_at=datetime.now(UTC) - timedelta(days=7),
        status_short="FT",
        home_goals=2,
        away_goals=1,
    )
    db_session.add(fixture)
    db_session.flush()
    db_session.add(
        PlayerMatchStat(
            fixture_id=fixture.id,
            athlete_id=athlete.id,
            athlete_provider_id=athlete.provider_id,
            club_id=fixture.home_club_id,
            minutes=90,
            is_substitute=False,
            stats_json={"goals": {"total": 1, "assists": 0}, "cards": {"yellow": 0, "red": 0}},
            stats_hash="mv",
        )
    )
    db_session.add(
        PlayerMatchRating(
            fixture_id=fixture.id,
            athlete_id=athlete.id,
            athlete_provider_id=athlete.provider_id,
            formula_version=DEFAULT_FORMULA_VERSION,
            role=FantasyRole.A,
            minutes=90,
            eligible=True,
            eligibility_reason="minutes_threshold",
            base=6.0,
            raw_before_clamp=display,
            raw=display,
            display=display,
            stats_hash="mv",
            fantasy_score=display + 3,
        )
    )


def _free_athlete(db_session: Session, provider_id: int, name: str, role: FantasyRole) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=2026,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
    return athlete


def _refresh(client: TestClient, db_session: Session, email: str) -> dict:
    token, user_id = _register_and_login(client, email)
    _promote_to_operator(db_session, user_id)
    response = client.post(
        REFRESH_URL, headers=_headers(token), json={"seasonYear": 2026, "force": True}
    )
    assert response.status_code == 200, response.json()
    return response.json()


def test_market_fields_on_listone_trade_and_athlete_card(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="mv.fields", id_offset=8_910_000
    )
    forwards = setup["roles_a"][FantasyRole.A]
    current, previous, nothing = (db_session.get(Athlete, forwards[i]) for i in range(3))
    assert current and previous and nothing
    _vote(db_session, setup["round_id"], current, 7.0)
    _provider_row(db_session, current, season=2025, rating=6.4, apps=20)
    _provider_row(db_session, previous, season=2025, rating=6.8571, apps=30)
    _provider_row(db_session, previous, season=2024, rating=7.1, apps=28, club_name="Vecchio Club")
    db_session.commit()

    summary = _refresh(client, db_session, "mv.fields.op@example.com")
    assert summary["skipped"] is False
    assert summary["athletesValued"] >= 70
    assert summary["athletesWithCurrentAverage"] >= 1
    assert summary["athletesWithPreviousAverage"] >= 1

    league_id = setup["league_id"]
    listone = client.get(f"/leagues/{league_id}/listone", headers=_headers(setup["token_a"]))
    assert listone.status_code == 200
    by_id = {entry["athleteId"]: entry for entry in listone.json()}

    # Con almeno un voto nella stagione in corso: la nostra media, verde.
    assert by_id[str(current.id)]["seasonAverage"] == {
        "value": 7.0,
        "seasonYear": 2026,
        "seasonLabel": "26/27",
        "isCurrent": True,
    }
    # Senza voti: la media del fornitore della stagione scorsa, «25/26», rossa.
    assert by_id[str(previous.id)]["seasonAverage"] == {
        "value": 6.86,
        "seasonYear": 2025,
        "seasonLabel": "25/26",
        "isCurrent": False,
    }
    # Nessun dato: niente media e il valore base del ruolo.
    assert by_id[str(nothing.id)]["seasonAverage"] is None
    assert by_id[str(nothing.id)]["marketValue"] == credits_for_budget(
        base_reference_value("A"), 1000
    )
    for entry in listone.json():
        assert isinstance(entry["marketValue"], int) and entry["marketValue"] >= 1
    assert by_id[str(previous.id)]["marketValue"] > by_id[str(nothing.id)]["marketValue"]

    # Crediti proporzionali al budget della lega.
    stored = db_session.scalar(
        select(AthleteMarketValue).where(
            AthleteMarketValue.athlete_id == previous.id, AthleteMarketValue.season_year == 2026
        )
    )
    assert stored is not None
    assert by_id[str(previous.id)]["marketValue"] == credits_for_budget(
        stored.reference_value, 1000
    )
    rules = db_session.scalar(select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)))
    assert rules is not None
    rules.total_credits = 500
    db_session.commit()
    halved = client.get(f"/leagues/{league_id}/listone", headers=_headers(setup["token_a"]))
    halved_by_id = {entry["athleteId"]: entry for entry in halved.json()}
    assert halved_by_id[str(previous.id)]["marketValue"] == credits_for_budget(
        stored.reference_value, 500
    )

    # Proposta di scambio: i calciatori portano Valore e media.
    requested = setup["roles_b"][FantasyRole.A][0]
    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_headers(setup["token_a"]),
        json={
            "recipientTeamId": setup["team_b"],
            "offeredAthleteIds": [str(current.id)],
            "requestedAthleteIds": [str(requested)],
            "offeredCredits": 0,
            "requestedCredits": 0,
            "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        },
    )
    assert proposal.status_code == 201, proposal.json()
    offered = proposal.json()["offeredAthletes"][0]
    assert offered["seasonAverage"]["isCurrent"] is True
    assert offered["marketValue"] == halved_by_id[str(current.id)]["marketValue"]
    listed = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte", headers=_headers(setup["token_b"])
    )
    assert listed.status_code == 200
    requested_row = listed.json()["proposals"][0]["requestedAthletes"][0]
    assert requested_row["marketValue"] >= 1

    # Scheda calciatore: storico dalla stagione in corso alla più vecchia.
    card = client.get(
        f"/leagues/{league_id}/calciatori/{previous.id}", headers=_headers(setup["token_a"])
    )
    assert card.status_code == 200
    body = card.json()
    assert body["seasonAverage"]["seasonLabel"] == "25/26"
    assert body["marketValue"] == halved_by_id[str(previous.id)]["marketValue"]
    assert [(row["seasonLabel"], row["source"]) for row in body["career"]] == [
        ("25/26", "provider"),
        ("24/25", "provider"),
    ]
    first = body["career"][0]
    assert first["averageRating"] == 6.86
    assert first["appearances"] == 30
    assert first["cleanSheets"] is None  # non nota per le stagioni passate
    assert first["isCurrent"] is False
    assert body["career"][1]["clubName"] == "Vecchio Club"

    card_current = client.get(
        f"/leagues/{league_id}/calciatori/{current.id}", headers=_headers(setup["token_a"])
    ).json()
    assert [(row["seasonYear"], row["source"]) for row in card_current["career"]] == [
        (2026, "fantappero"),
        (2025, "provider"),
    ]
    now_row = card_current["career"][0]
    assert now_row["isCurrent"] is True
    assert (now_row["appearances"], now_row["votes"], now_row["averageRating"]) == (1, 1, 7.0)
    assert now_row["goals"] == 1


def test_market_fields_on_sealed_bids_and_live_lot(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "mv.bids.admin@example.com")
    member_token, member_id = _register_and_login(client, "mv.bids.member@example.com")
    created = client.post(
        "/leagues",
        headers=_headers(admin_token),
        json={"name": "Lega Valore", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    db_session.add(
        LeagueMembership(league_id=UUID(league_id), user_id=member_id, role=LeagueMemberRole.MEMBER)
    )
    bid_target = _free_athlete(db_session, 8_920_001, "Centrocampista Buste", FantasyRole.C)
    lot_target = _free_athlete(db_session, 8_920_002, "Attaccante Lotto", FantasyRole.A)
    _provider_row(db_session, bid_target, season=2025, rating=7.05, apps=33)
    db_session.commit()
    _refresh(client, db_session, "mv.bids.op@example.com")

    now = datetime.now(UTC)
    session = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers=_headers(admin_token),
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert session.status_code == 201, session.json()
    session_id = session.json()["id"]
    bid = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{bid_target.id}",
        headers=_headers(member_token),
        json={"amountCredits": 5},  # il Valore è solo un consiglio: la validazione non cambia
    )
    assert bid.status_code == 200, bid.json()
    assert bid.json()["seasonAverage"] == {
        "value": 7.05,
        "seasonYear": 2025,
        "seasonLabel": "25/26",
        "isCurrent": False,
    }
    assert bid.json()["marketValue"] >= 1
    bids = client.get(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte",
        headers=_headers(member_token),
    )
    assert bids.json()["bids"][0]["marketValue"] == bid.json()["marketValue"]
    closed = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers=_headers(admin_token),
    )
    assert closed.status_code == 200, closed.json()

    live = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers=_headers(admin_token),
        json={
            "opensAt": now.isoformat(),
            "closesAt": (now + timedelta(hours=2)).isoformat(),
            "nominationMode": "manual",
            "minIncrementCredits": 1,
            "softCloseSeconds": 5,
            "lotDurationSeconds": 30,
        },
    )
    assert live.status_code == 201, live.json()
    live_id = live.json()["id"]
    started = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/avvia",
        headers=_headers(admin_token),
    )
    assert started.status_code == 200, started.json()
    lot = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/lotti/nomina",
        headers=_headers(admin_token),
        json={"athleteId": str(lot_target.id)},
    )
    assert lot.status_code == 201, lot.json()
    base_forward = credits_for_budget(base_reference_value("A"), 1000)
    assert lot.json()["marketValue"] == base_forward
    assert lot.json()["seasonAverage"] is None
    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/stato",
        headers=_headers(member_token),
    )
    assert state.status_code == 200
    assert state.json()["currentLot"]["marketValue"] == base_forward
    lots = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/lotti",
        headers=_headers(member_token),
    )
    assert lots.json()["lots"][0]["marketValue"] == base_forward
