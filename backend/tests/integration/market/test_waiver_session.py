"""Integration tests for the sealed-bid waiver window (EP08-03 / FR-MKT-01)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import CreditLedgerReason, FantasyRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyRosterSlot
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_athlete(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole = FantasyRole.A,
    season_year: int = 2026,
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _own_first_athlete_on_roster(
    client: TestClient, db_session: Session, league_id: str, token: str, athlete: Athlete
) -> str:
    """Fill the caller's slot 0 with ``athlete`` for free; returns the fantasy team id."""
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert rosa["filledSlots"] == 0  # sanity: roster started empty
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 200
    return team_id


def _create_open_waiver_session(client: TestClient, admin_token: str, league_id: str) -> str:
    now = datetime.now(UTC)
    response = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(minutes=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "open"
    return response.json()["id"]


def test_waiver_bid_requires_release_athlete_owned_by_team(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "waiver.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Svincoli")
    free_agent = _seed_athlete(db_session, 9301, "Svincolato Libero")
    owned = _seed_athlete(db_session, 9302, "Giocatore Posseduto", role=FantasyRole.D)
    _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)

    missing_release = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50},
    )
    assert missing_release.status_code == 400
    assert missing_release.json()["code"] == "release_athlete_required"

    not_owned = _seed_athlete(db_session, 9303, "Non Mio", role=FantasyRole.D)
    wrong_release = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50, "releaseAthleteId": str(not_owned.id)},
    )
    assert wrong_release.status_code == 400
    assert wrong_release.json()["code"] == "release_athlete_not_owned"

    ok = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50, "releaseAthleteId": str(owned.id)},
    )
    assert ok.status_code == 200
    assert ok.json()["releaseAthleteId"] == str(owned.id)
    assert ok.json()["releaseAthleteName"] == "Giocatore Posseduto"


def test_auction_bid_rejects_release_athlete_id(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "waiver.auction.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Vs Svincoli")
    athlete = _seed_athlete(db_session, 9304, "Libero Asta")
    now = datetime.now(UTC)
    session_resp = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(minutes=1)).isoformat(),
        },
    )
    session_id = session_resp.json()["id"]

    rejected = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50, "releaseAthleteId": str(athlete.id)},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "release_athlete_not_allowed"


def test_waiver_resolution_swaps_players_with_no_refund(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "waiver.swap.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Svincoli")
    free_agent = _seed_athlete(db_session, 9305, "Nuovo Acquisto", role=FantasyRole.D)
    owned = _seed_athlete(db_session, 9306, "Vecchio Giocatore", role=FantasyRole.D)
    team_id = _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    bid = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 80, "releaseAthleteId": str(owned.id)},
    )
    assert bid.status_code == 200

    client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolution = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "assigned"
    assert outcome["amountCredits"] == 80

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is not None
    assert slot.athlete_id == free_agent.id
    assert slot.purchase_credits == 80

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == slot.fantasy_team_id)
    )
    assert account is not None
    assert account.balance == 1000 - 80  # no refund for the released player (EP08-04 scope)

    ledger_entry = db_session.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_WAIVER_ACQUISITION,
        )
    )
    assert ledger_entry is not None
    assert ledger_entry.amount == -80


def test_waiver_bid_lost_when_release_athlete_no_longer_owned(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """If the named release athlete leaves the roster before resolution, the bid loses
    instead of corrupting the roster ("cambio annullato se crea rosa invalida")."""
    admin_token, admin_id = _register_and_login(client, "waiver.stale.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Svincolo Obsoleto")
    free_agent = _seed_athlete(db_session, 9307, "Obsoleto Target", role=FantasyRole.D)
    owned = _seed_athlete(db_session, 9308, "Rilasciato Prima", role=FantasyRole.D)
    team_id = _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    bid = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 60, "releaseAthleteId": str(owned.id)},
    )
    assert bid.status_code == 200

    # The team releases that same player manually before the waiver resolves.
    release = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert release.status_code == 200

    client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolution = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "unassigned"

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is not None
    assert slot.athlete_id is None  # untouched by the failed waiver, still empty from the release
