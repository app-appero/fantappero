"""Integration tests for the lineup deadline reminder task (EP09-02)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyModule, FantasyTurnKind, FantasyTurnStatus, NotificationCategory
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from notifications.models import Notification
from notifications.reminder_service import LineupReminderService


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


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


def _create_round(
    db_session: Session,
    league_id: str,
    *,
    cutoff: datetime,
    number: int = 1,
) -> FantasyRound:
    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=number,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=cutoff - timedelta(days=1),
        window_end_at=cutoff + timedelta(days=3),
        cutoff_at=cutoff,
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round


def test_reminder_sent_once_for_team_without_lineup(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "reminder-basic@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Reminder")
    cutoff = datetime.now(UTC) + timedelta(hours=2)
    _create_round(db_session, league_id, cutoff=cutoff)

    result = LineupReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_hours=24
    )
    db_session.commit()
    assert result["reminders_sent"] == 1

    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.category == NotificationCategory.FORMAZIONE,
        )
    )
    assert notification is not None
    assert notification.deep_link.startswith("/formazione?lega=")

    # Re-running before the cutoff must not duplicate the reminder.
    again = LineupReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_hours=24
    )
    db_session.commit()
    assert again["reminders_sent"] == 0


def test_reminder_skips_team_with_submitted_lineup(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "reminder-submitted@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Reminder Sub")
    cutoff = datetime.now(UTC) + timedelta(hours=2)
    fantasy_round = _create_round(db_session, league_id, cutoff=cutoff)
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()

    from fantasy_lineups.models import LineupSubmission

    db_session.add(
        LineupSubmission(
            league_id=UUID(league_id),
            round_id=fantasy_round.id,
            fantasy_team_id=team.id,
            module=FantasyModule.M442,
            submitted_at=datetime.now(UTC),
            submitted_by_user_id=user_id,
        )
    )
    db_session.commit()

    result = LineupReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_hours=24
    )
    assert result["reminders_sent"] == 0


def test_reminder_ignores_rounds_outside_window_or_past_cutoff(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "reminder-outside@example.com")
    league_far = _create_league(client, token, competition_ids, "Lega Reminder Far")
    _create_round(db_session, league_far, cutoff=datetime.now(UTC) + timedelta(days=10))

    token2, _ = _register_and_login(client, "reminder-past@example.com")
    league_past = _create_league(client, token2, competition_ids, "Lega Reminder Past")
    _create_round(db_session, league_past, cutoff=datetime.now(UTC) - timedelta(hours=1), number=2)

    result = LineupReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_hours=24
    )
    assert result["reminders_sent"] == 0


def _set_lock_margin(db_session: Session, league_id: str, minutes: int) -> None:
    from leagues.models.league_rules import LeagueRules

    rules = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == UUID(league_id))
    ).one()
    rules.lineup_lock_margin_minutes = minutes
    db_session.commit()


def _reminder_for(db_session: Session, user_id: UUID) -> Notification | None:
    return db_session.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.template_key == "formazione.scadenza_turno",
        )
    )


def test_reminder_text_says_the_real_lock_time_not_the_kickoff(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """QA 20-21/11: «Il turno 11 chiude alle 20/11/2026 21:00» con il blocco vero alle 20:45."""
    from notifications.reminder_service import _format_local

    token, user_id = _register_and_login(client, "reminder-lock-time@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Reminder Blocco")
    _set_lock_margin(db_session, league_id, 15)
    cutoff = (datetime.now(UTC) + timedelta(hours=3)).replace(second=0, microsecond=0)
    _create_round(db_session, league_id, cutoff=cutoff, number=11)

    LineupReminderService(db_session).send_due_reminders(now=datetime.now(UTC), window_hours=24)
    db_session.commit()

    notification = _reminder_for(db_session, user_id)
    assert notification is not None
    lock_local = _format_local(cutoff - timedelta(minutes=15), "Europe/Rome")
    kickoff_local = _format_local(cutoff, "Europe/Rome")
    assert notification.title == "Scadenza formazione in arrivo"
    assert notification.body.endswith(
        f"Turno 11: la formazione si blocca alle {lock_local}. Salvala prima del blocco."
    )
    assert kickoff_local not in notification.body
    assert notification.template_version == 2


def test_no_reminder_between_the_lock_and_the_kickoff(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Calcio d'inizio fra 5 minuti, margine 15: la formazione è già bloccata."""
    token, user_id = _register_and_login(client, "reminder-locked@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Reminder Bloccata")
    _set_lock_margin(db_session, league_id, 15)
    _create_round(db_session, league_id, cutoff=datetime.now(UTC) + timedelta(minutes=5))

    LineupReminderService(db_session).send_due_reminders(now=datetime.now(UTC), window_hours=24)
    db_session.commit()

    assert _reminder_for(db_session, user_id) is None


def test_reminder_window_is_measured_on_the_lock(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Finestra di un'ora: il calcio d'inizio è fra 70 minuti, ma il blocco fra 55 è dentro."""
    token, user_id = _register_and_login(client, "reminder-window-lock@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Reminder Finestra")
    _set_lock_margin(db_session, league_id, 15)
    _create_round(db_session, league_id, cutoff=datetime.now(UTC) + timedelta(minutes=70))

    LineupReminderService(db_session).send_due_reminders(now=datetime.now(UTC), window_hours=1)
    db_session.commit()

    assert _reminder_for(db_session, user_id) is not None
