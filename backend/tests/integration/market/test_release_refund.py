"""Integration tests for voluntary release and credit refund (EP08-04 / FR-MKT-02)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
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
    role: FantasyRole = FantasyRole.D,
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


def _own_athlete_at_slot(
    client: TestClient, league_id: str, token: str, athlete: Athlete, *, purchase_credits: int
) -> str:
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": purchase_credits},
    )
    assert response.status_code == 200
    return team_id


def test_voluntary_release_preview_matches_applied_refund(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "release.preview@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Anteprima Svincolo")
    athlete = _seed_athlete(db_session, 9401, "Rilasciato Standard")
    team_id = _own_athlete_at_slot(client, league_id, admin_token, athlete, purchase_credits=200)

    preview = client.get(
        f"/leagues/{league_id}/mercato/svincolo/0/anteprima",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"causa": "voluntary"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["purchaseCredits"] == 200
    assert body["refundPercent"] == 50
    assert body["refundCredits"] == 100

    applied = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "voluntary"},
    )
    assert applied.status_code == 200
    result = applied.json()
    assert result["refundCredits"] == 100
    assert result["balance"] == 1000 - 200 + 100

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is not None
    assert slot.athlete_id is None

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    ledger_entry = db_session.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_RELEASE_REFUND,
        )
    )
    assert ledger_entry is not None
    assert ledger_entry.amount == 100


def test_league_exit_reason_refunds_full_amount(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "release.exit@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Uscita Campionati")
    athlete = _seed_athlete(db_session, 9402, "Trasferito Fuori")
    team_id = _own_athlete_at_slot(client, league_id, admin_token, athlete, purchase_credits=150)

    applied = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "league_exit"},
    )
    assert applied.status_code == 200
    result = applied.json()
    assert result["refundPercent"] == 100
    assert result["refundCredits"] == 150
    assert result["balance"] == 1000  # fully restored

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    assert account.balance == 1000


def test_configured_league_percentage_overrides_standard_default(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "release.configured@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Percentuale Custom")
    athlete = _seed_athlete(db_session, 9403, "Rilascio Personalizzato")
    _own_athlete_at_slot(client, league_id, admin_token, athlete, purchase_credits=100)

    rules = client.get(
        f"/leagues/{league_id}", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()["rules"]
    update = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "presetName": "standard",
            "participantCount": rules["participantCount"],
            "roster": rules["roster"],
            "totalCredits": rules["totalCredits"],
            "voluntaryReleaseRefundPercent": 75,
            "options": {"allowTrades": True, "allowManualInvites": True},
        },
    )
    assert update.status_code == 200
    assert update.json()["voluntaryReleaseRefundPercent"] == 75

    preview = client.get(
        f"/leagues/{league_id}/mercato/svincolo/0/anteprima",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"causa": "voluntary"},
    )
    assert preview.status_code == 200
    assert preview.json()["refundPercent"] == 75
    assert preview.json()["refundCredits"] == 75


def test_release_rejects_empty_slot_and_invalid_reason(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "release.invalid@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Slot Vuoto")

    empty_slot = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "voluntary"},
    )
    assert empty_slot.status_code == 400
    assert empty_slot.json()["code"] == "release_slot_empty"

    athlete = _seed_athlete(db_session, 9404, "Motivo Invalido")
    _own_athlete_at_slot(client, league_id, admin_token, athlete, purchase_credits=50)
    bad_reason = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "not_a_reason"},
    )
    assert bad_reason.status_code == 400
    assert bad_reason.json()["code"] == "invalid_release_reason"


def test_concurrent_release_attempts_apply_refund_exactly_once(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "release.conc@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Concorrenza Svincolo")
    athlete = _seed_athlete(db_session, 9405, "Concorrente Svincolo")
    team_id = _own_athlete_at_slot(client, league_id, admin_token, athlete, purchase_credits=120)

    def _release(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/svincolo/0",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "voluntary"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_release, range(4)))

    # Exactly one call finds the occupied slot; the rest see it already empty.
    assert statuses.count(200) == 1
    assert statuses.count(400) == 3

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    assert account.balance == 1000 - 120 + 60  # refunded exactly once
    ledger_entries = db_session.scalars(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_RELEASE_REFUND,
        )
    ).all()
    assert len(ledger_entries) == 1
