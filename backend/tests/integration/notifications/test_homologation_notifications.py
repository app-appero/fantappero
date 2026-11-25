"""Integration tests for round homologation/correction notifications (EP09-03)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import (
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueState,
    NotificationCategory,
)
from fantasy_turns.homologation_service import apply_round_correction, homologate_round
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from mail.capture import get_captured_emails
from notifications.models import Notification
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture, PlayerMatchStat


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


def _create_finished_round(
    db_session: Session,
    league_id: str,
    competition_ids: list[str],
    *,
    id_offset: int,
    league_created_before_round: bool = True,
    league_state: LeagueState = LeagueState.ACTIVE,
    status: FantasyTurnStatus = FantasyTurnStatus.OPEN,
) -> FantasyRound:
    """Turno finito di due giorni, in una lega di norma attiva e creata prima che il turno
    inizi: con ``league_created_before_round=False`` è un segnaposto «Lega creata dopo questo
    turno»."""
    now = datetime.now(UTC)
    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.state = league_state
    if league_created_before_round:
        league.created_at = now - timedelta(days=3)
    db_session.flush()
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=2),
        window_end_at=now,
        cutoff_at=now - timedelta(hours=1),
        status=status,
        generated_at=now,
        opens_at=now - timedelta(days=2),
    )
    db_session.add(fantasy_round)
    db_session.flush()

    home = Club(provider_id=id_offset, name=f"Club Omo {id_offset}A")
    away = Club(provider_id=id_offset + 1, name=f"Club Omo {id_offset}B")
    db_session.add_all([home, away])
    db_session.flush()

    competition_id = UUID(competition_ids[0])
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()

    fixture = Fixture(
        provider_id=id_offset + 50_000,
        sport_season_id=season.id,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff_at=now - timedelta(hours=2),
        status_short="FT",
    )
    db_session.add(fixture)
    db_session.flush()
    db_session.add(
        FantasyRoundFixture(
            round_id=fantasy_round.id,
            league_id=UUID(league_id),
            fixture_id=fixture.id,
            observed_kickoff_at=fixture.kickoff_at,
        )
    )
    # L'omologazione richiede le statistiche giocatore definitive di entrambe le squadre.
    for index, club in enumerate((home, away)):
        db_session.add(
            PlayerMatchStat(
                fixture_id=fixture.id,
                athlete_provider_id=id_offset + 700 + index,
                club_id=club.id,
                minutes=90,
                stats_json={},
                stats_hash=f"omo-{id_offset}-{index}",
            )
        )
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round


def test_homologation_and_correction_notify_league_members(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, owner_id = _register_and_login(client, "homolog-owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Omologazione")
    fantasy_round = _create_finished_round(db_session, league_id, competition_ids, id_offset=970001)

    homologate_round(db_session, round_id=fantasy_round.id, actor_id=owner_id)
    db_session.commit()

    homolog_notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == owner_id,
            Notification.category == NotificationCategory.RISULTATI,
            Notification.template_key == "risultati.omologazione",
        )
    )
    assert homolog_notification is not None
    assert homolog_notification.deep_link.startswith("/classifica?lega=")

    apply_round_correction(
        db_session, round_id=fantasy_round.id, actor_id=owner_id, reason="Errore voto arbitro"
    )
    db_session.commit()

    correction_notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == owner_id,
            Notification.category == NotificationCategory.RISULTATI,
            Notification.template_key == "risultati.correzione",
        )
    )
    assert correction_notification is not None

    # Two distinct events (homologation, then correction) — never collapsed into one.
    all_risultati = db_session.scalars(
        select(Notification).where(
            Notification.user_id == owner_id,
            Notification.category == NotificationCategory.RISULTATI,
        )
    ).all()
    assert len(all_risultati) == 2


def _homologation_notifications(db_session: Session, user_id: UUID) -> list[Notification]:
    return list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.template_key == "risultati.omologazione",
            )
        ).all()
    )


def _homologation_audit(db_session: Session, league_id: str) -> LeagueAuditEvent | None:
    return db_session.scalar(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROUND_HOMOLOGATED,
        )
    )


def test_round_started_before_the_league_is_homologated_without_notifying(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """QA notte 24-25/11: un turno iniziato prima della creazione della lega non l'ha giocato
    nessuno. Si omologa (audit con ``beforeLeagueCreation``) ma «Turno concluso» non parte,
    nemmeno in una lega attiva."""
    token, owner_id = _register_and_login(client, "homolog-placeholder@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Nata Dopo")
    fantasy_round = _create_finished_round(
        db_session,
        league_id,
        competition_ids,
        id_offset=970101,
        league_created_before_round=False,
    )

    homologate_round(db_session, round_id=fantasy_round.id, actor_id=owner_id)
    db_session.commit()

    assert _homologation_notifications(db_session, owner_id) == []
    audit = _homologation_audit(db_session, league_id)
    assert audit is not None
    assert audit.details["beforeLeagueCreation"] is True


def test_round_of_a_league_still_in_setup_is_homologated_without_notifying(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Lega in configurazione (pilota, turno 11 di una lega nata il 24/11): il turno mai aperto
    si omologa senza notifiche e in Turni risulta concluso, non «programmato»."""
    token, owner_id = _register_and_login(client, "homolog-setup@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega In Configurazione")
    fantasy_round = _create_finished_round(
        db_session,
        league_id,
        competition_ids,
        id_offset=970201,
        league_created_before_round=False,
        league_state=LeagueState.CONFIGURING,
        status=FantasyTurnStatus.SCHEDULED,
    )

    headers = {"Authorization": f"Bearer {token}"}
    before = client.get(f"/leagues/{league_id}/turni", headers=headers)
    assert before.status_code == 200
    [row] = [item for item in before.json() if item["id"] == str(fantasy_round.id)]
    assert row["effectiveStatus"] == "scheduled"
    assert row["homologationStatus"] == "provisional"

    homologate_round(db_session, round_id=fantasy_round.id, actor_id=owner_id)
    db_session.commit()

    assert _homologation_notifications(db_session, owner_id) == []
    assert _homologation_audit(db_session, league_id) is not None

    listing = client.get(f"/leagues/{league_id}/turni", headers=headers)
    [row] = [item for item in listing.json() if item["id"] == str(fantasy_round.id)]
    assert row["status"] == "scheduled"  # stato memorizzato: il turno non è mai stato aperto
    assert row["effectiveStatus"] == "locked"
    assert row["homologationStatus"] == "homologated"
    assert row["modificationAllowed"] is False
    assert row["matchStatus"] == "completed"
    detail = client.get(f"/leagues/{league_id}/turni/{fantasy_round.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["effectiveStatus"] == "locked"
    assert detail.json()["homologationStatus"] == "homologated"


def test_round_of_a_league_created_before_it_in_setup_is_not_notified(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Anche un turno dopo la creazione non notifica finché la lega non è attiva."""
    token, owner_id = _register_and_login(client, "homolog-auction@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega In Asta")
    fantasy_round = _create_finished_round(
        db_session,
        league_id,
        competition_ids,
        id_offset=970301,
        league_state=LeagueState.AUCTION,
    )

    homologate_round(db_session, round_id=fantasy_round.id, actor_id=owner_id)
    db_session.commit()

    assert _homologation_notifications(db_session, owner_id) == []
    audit = _homologation_audit(db_session, league_id)
    assert audit is not None
    assert "beforeLeagueCreation" not in audit.details
