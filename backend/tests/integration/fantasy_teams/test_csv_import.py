"""Integration tests for CSV roster import preview/confirm (EP05-04)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import FantasyRosterSlot, RosterImportSession
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
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


def _create_league(
    client: TestClient,
    token: str,
    competition_ids: list[str],
    name: str,
) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
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


def test_csv_template_and_preview_does_not_write_roster(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "csv.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    team_name = rosa.json()["name"]
    athlete = _seed_athlete(db_session, 9001, "CSV Player")

    template = client.get(
        f"/leagues/{league_id}/amministrazione/import-csv/modello",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert template.status_code == 200
    assert "text/csv" in template.headers["content-type"]
    assert b"squadra,provider_id,nome,crediti" in template.content

    csv_body = (
        f"squadra,provider_id,nome,crediti\n"
        f"{team_name},{athlete.provider_id},{athlete.canonical_name},15\n"
    ).encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["canConfirm"] is True
    assert body["errorCount"] == 0
    assert body["rows"][0]["status"] == "ok"
    assert body["rows"][0]["athleteId"] == str(athlete.id)

    filled = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.league_id == UUID(league_id),
            FantasyRosterSlot.athlete_id == athlete.id,
        )
    )
    assert filled is None


def test_csv_confirm_atomic_and_idempotent(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "csv.confirm@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Confirm")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    team_name = rosa.json()["name"]
    team_id = rosa.json()["id"]
    a1 = _seed_athlete(db_session, 9101, "Import One")
    a2 = _seed_athlete(db_session, 9102, "Import Two")

    csv_body = (
        "squadra,provider_id,nome,crediti\n"
        f"{team_name},{a1.provider_id},{a1.canonical_name},20\n"
        f"{team_name},{a2.provider_id},{a2.canonical_name},30\n"
    ).encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200
    import_id = preview.json()["importId"]

    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{import_id}/conferma",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolutions": []},
    )
    assert confirm.status_code == 200
    assert confirm.json()["assignedCount"] == 2
    assert confirm.json()["status"] == "confirmed"

    slots = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.athlete_id.is_not(None),
        )
    ).all()
    assert len(slots) == 2
    assert {slot.athlete_id for slot in slots} == {a1.id, a2.id}

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert credits.status_code == 200
    assert credits.json()["balance"] == 1000 - 50

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_CSV_IMPORTED,
        )
    ).all()
    assert len(audit) == 1

    again = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{import_id}/conferma",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolutions": []},
    )
    assert again.status_code == 200
    assert again.json()["assignedCount"] == 2
    audit_again = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_CSV_IMPORTED,
        )
    ).all()
    assert len(audit_again) == 1


def test_csv_preview_row_errors_and_member_forbidden(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "csv.admin2@example.com")
    member_token, member_id = _register_and_login(client, "csv.member2@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega CSV Err")
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=member_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()

    # Ensure owner team exists
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {owner_token}"})

    bad = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {owner_token}"},
        files={
            "file": (
                "bad.csv",
                b"squadra,provider_id,nome,crediti\nGhost,99999,Nobody,5\n",
                "text/csv",
            )
        },
    )
    assert bad.status_code == 200
    assert bad.json()["canConfirm"] is False
    assert bad.json()["errorCount"] >= 1
    assert bad.json()["rows"][0]["status"] == "error"

    forbidden = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {member_token}"},
        files={"file": ("x.csv", b"squadra,provider_id,nome,crediti\nA,1,B,1\n", "text/csv")},
    )
    assert forbidden.status_code in {403, 401}

    sessions = db_session.scalars(
        select(RosterImportSession).where(RosterImportSession.league_id == UUID(league_id))
    ).all()
    assert len(sessions) >= 1
    assert all(row.status.value == "draft" for row in sessions)
