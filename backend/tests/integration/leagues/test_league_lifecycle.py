"""Integration coverage for EP03-05 league lifecycle."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import (
    FantasyRoundHomologationStatus,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueCalendarStatus,
    LeagueMemberRole,
    LeagueState,
    PlatformRole,
)
from database.session import create_session_factory
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.season_conclude import try_conclude_league_if_season_complete
from mail.capture import get_captured_emails


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
def db_session(db_url: str, migrated_engine: object) -> Session:
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


def _transition(client: TestClient, token: str, league_id: str, target: str):
    return client.post(
        f"/leagues/{league_id}/amministrazione/stato",
        headers={"Authorization": f"Bearer {token}"},
        json={"targetState": target},
    )


def _standard_rules_payload(participant_count: int) -> dict[str, object]:
    return {
        "presetName": "standard",
        "participantCount": participant_count,
        "roster": {
            "rosterSize": 35,
            "goalkeepers": 3,
            "defenders": 11,
            "midfielders": 11,
            "forwards": 10,
        },
        "totalCredits": 1000,
        "options": {"allowTrades": True, "allowManualInvites": True},
    }


def test_create_starts_configuring_and_auction_path_is_audited(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "lifecycle.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Lifecycle")

    panel = client.get(
        f"/leagues/{league_id}/amministrazione",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert panel.status_code == 200
    assert panel.json()["lifecycle"]["state"] == "configuring"
    assert panel.json()["configurationSaved"] is False
    assert "participant_count_mismatch" in {
        row["code"] for row in panel.json()["lifecycle"]["blockers"]
    }
    # Alla creazione non serve più draft → configuring: già in setup.
    assert panel.json()["lifecycle"]["allowedTransitions"] == []

    rules_update = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=_standard_rules_payload(4),
    )
    assert rules_update.status_code == 200
    assert rules_update.json()["participantCount"] == 4
    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    for index in range(3):
        member_token, _ = _register_and_login(
            client,
            f"lifecycle.member{index}@example.com",
        )
        accepted = client.post(
            "/leagues/inviti/accetta",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"token": invite.json()["token"]},
        )
        assert accepted.status_code == 200
        assert accepted.json()["alreadyMember"] is False

    # Partecipanti ok: asta sì (API), avvio stagione no (manca calendario/rose).
    ready_for_auction = client.get(
        f"/leagues/{league_id}/amministrazione",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ready_for_auction.status_code == 200
    assert ready_for_auction.json()["lifecycle"]["allowedTransitions"] == ["auction"]
    assert {row["code"] for row in ready_for_auction.json()["lifecycle"]["blockers"]} >= {
        "calendar_not_configured",
        "fantasy_teams_not_configured",
    }
    blocked_active = _transition(client, owner_token, league_id, "active")
    assert blocked_active.status_code == 400
    assert blocked_active.json()["code"] == "league_transition_blocked"

    auction = _transition(client, owner_token, league_id, "auction")
    assert auction.status_code == 200
    assert auction.json()["state"] == "auction"
    assert auction.json()["allowedTransitions"] == ["configuring"]
    assert {row["code"] for row in auction.json()["blockers"]} == {
        "calendar_not_configured",
        "fantasy_teams_not_configured",
    }

    noop = _transition(client, owner_token, league_id, "auction")
    blocked = _transition(client, owner_token, league_id, "active")
    assert noop.status_code == 200
    assert noop.json()["state"] == "auction"
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "league_transition_blocked"

    db_session.expire_all()
    league = db_session.get(League, UUID(league_id))
    assert league is not None
    assert league.state == LeagueState.AUCTION
    audits = db_session.scalars(
        select(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_STATE_CHANGED,
        )
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    assert len(audits) == 1
    assert audits[0].details == {"before": "configuring", "after": "auction"}
    assert audits[0].actor_id == owner_id


def test_active_state_hides_manual_conclude(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "lifecycle.active@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Active")

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.state = LeagueState.ACTIVE
    db_session.commit()

    panel = client.get(
        f"/leagues/{league_id}/amministrazione",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert panel.status_code == 200
    assert panel.json()["lifecycle"]["state"] == "active"
    assert panel.json()["lifecycle"]["allowedTransitions"] == []

    manual = _transition(client, owner_token, league_id, "concluded")
    assert manual.status_code == 400
    assert manual.json()["code"] == "league_transition_blocked"


def test_invalid_transition_is_rejected(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lifecycle.invalid@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Salto")

    # configuring → concluded non è nel grafo (salta active).
    response = _transition(client, token, league_id, "concluded")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_league_transition"


def test_transition_requires_league_admin(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "lifecycle.permission.owner@example.com")
    member_token, member_id = _register_and_login(
        client,
        "lifecycle.permission.member@example.com",
    )
    league_id = _create_league(client, owner_token, competition_ids, "Lega Permesso Stato")
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()

    response = _transition(client, member_token, league_id, "configuring")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_STATE_CHANGED,
            )
        )
        == 0
    )


def test_auto_conclude_when_all_h2h_rounds_homologated(db_session: Session) -> None:
    now = datetime.now(UTC)
    owner = User(
        email=f"auto.conclude.{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified_at=now,
        platform_role=PlatformRole.USER,
    )
    member = User(
        email=f"auto.conclude.m.{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified_at=now,
        platform_role=PlatformRole.USER,
    )
    db_session.add_all([owner, member])
    db_session.flush()

    league = League(name="Lega Auto Conclude", season_year=2026, state=LeagueState.ACTIVE)
    db_session.add(league)
    db_session.flush()
    home_m = LeagueMembership(
        league_id=league.id, user_id=owner.id, role=LeagueMemberRole.OWNER
    )
    away_m = LeagueMembership(
        league_id=league.id, user_id=member.id, role=LeagueMemberRole.MEMBER
    )
    db_session.add_all([home_m, away_m])
    db_session.flush()

    rounds: list[FantasyRound] = []
    for number in (1, 2):
        start = now - timedelta(days=21 - number * 7)
        fantasy_round = FantasyRound(
            league_id=league.id,
            number=number,
            kind=FantasyTurnKind.WEEKEND,
            window_start_at=start,
            window_end_at=start + timedelta(days=3),
            status=FantasyTurnStatus.LOCKED,
            generated_at=now,
            homologation_status=FantasyRoundHomologationStatus.PROVISIONAL,
        )
        db_session.add(fantasy_round)
        rounds.append(fantasy_round)
    db_session.flush()

    calendar = LeagueCalendar(
        league_id=league.id,
        status=LeagueCalendarStatus.CONFIRMED,
        algorithm_version="test_v1",
        participant_fingerprint="fp",
        participant_count=4,
        round_count=2,
        matchup_count=2,
        bye_count=0,
        generated_at=now,
        confirmed_at=now,
    )
    db_session.add(calendar)
    db_session.flush()
    for number in (1, 2):
        db_session.add(
            LeagueCalendarSlot(
                calendar_id=calendar.id,
                round_number=number,
                slot_index=0,
                is_bye=False,
                home_membership_id=home_m.id,
                away_membership_id=away_m.id,
            )
        )
    db_session.commit()

    assert try_conclude_league_if_season_complete(db_session, league.id) is False
    db_session.refresh(league)
    assert league.state == LeagueState.ACTIVE

    rounds[0].homologation_status = FantasyRoundHomologationStatus.HOMOLOGATED
    rounds[0].homologated_at = now
    db_session.commit()
    assert try_conclude_league_if_season_complete(db_session, league.id) is False

    rounds[1].homologation_status = FantasyRoundHomologationStatus.HOMOLOGATED
    rounds[1].homologated_at = now
    db_session.commit()
    assert try_conclude_league_if_season_complete(db_session, league.id) is True
    db_session.commit()
    db_session.refresh(league)
    assert league.state == LeagueState.CONCLUDED

    audit = db_session.scalars(
        select(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == league.id,
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_STATE_CHANGED,
        )
        .order_by(LeagueAuditEvent.created_at.desc())
    ).first()
    assert audit is not None
    assert audit.actor_id == owner.id
    assert audit.details == {
        "before": "active",
        "after": "concluded",
        "source": "auto_season_complete",
    }
    assert try_conclude_league_if_season_complete(db_session, league.id) is False
