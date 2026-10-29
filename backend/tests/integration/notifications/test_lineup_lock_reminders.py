"""Integration tests for the per-kickoff progressive lock reminder task.

Distinct from `test_lineup_reminders.py` (one reminder per round cutoff):
here each distinct lock instant — which may involve one or many roster
players sharing a kickoff — gets its own notification, deduplicated per
`(round, team, instant)`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole, FantasyTurnKind, FantasyTurnStatus, NotificationCategory
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from notifications.lock_reminder_service import LineupLockReminderService
from notifications.models import Notification
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture
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


def _create_round_with_two_fixtures(
    db_session: Session,
    league_id: str,
    *,
    id_offset: int,
    competition_ids: list[str],
    late_kickoff: datetime,
) -> tuple[FantasyRound, UUID, UUID]:
    """Un turno con due partite: una già iniziata (`early_home`, locked) e
    una non ancora (`late_home`, entro la finestra di preavviso)."""
    now = datetime.now(UTC)
    cutoff = late_kickoff + timedelta(hours=2)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=1),
        window_end_at=cutoff + timedelta(days=1),
        cutoff_at=cutoff,
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    early_home = Club(provider_id=id_offset, name=f"Club LLR {id_offset}-early-home")
    early_away = Club(provider_id=id_offset + 1, name=f"Club LLR {id_offset}-early-away")
    late_home = Club(provider_id=id_offset + 2, name=f"Club LLR {id_offset}-late-home")
    late_away = Club(provider_id=id_offset + 3, name=f"Club LLR {id_offset}-late-away")
    db_session.add_all([early_home, early_away, late_home, late_away])
    db_session.flush()

    competition_id = UUID(competition_ids[0])
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id,
            SportSeason.year == 2026,
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()

    early_fixture = Fixture(
        provider_id=id_offset + 50_000,
        sport_season_id=season.id,
        home_club_id=early_home.id,
        away_club_id=early_away.id,
        kickoff_at=now - timedelta(hours=2),
        status_short="1H",
    )
    late_fixture = Fixture(
        provider_id=id_offset + 50_001,
        sport_season_id=season.id,
        home_club_id=late_home.id,
        away_club_id=late_away.id,
        kickoff_at=late_kickoff,
        status_short="NS",
    )
    db_session.add_all([early_fixture, late_fixture])
    db_session.flush()
    db_session.add_all(
        [
            FantasyRoundFixture(
                round_id=fantasy_round.id,
                league_id=UUID(league_id),
                fixture_id=early_fixture.id,
                observed_kickoff_at=early_fixture.kickoff_at,
            ),
            FantasyRoundFixture(
                round_id=fantasy_round.id,
                league_id=UUID(league_id),
                fixture_id=late_fixture.id,
                observed_kickoff_at=late_fixture.kickoff_at,
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round, early_home.id, late_home.id


def _seed_roster(
    db_session: Session,
    *,
    id_offset: int,
    early_club_id: UUID,
    late_club_id: UUID,
    late_count: int,
) -> list[Athlete]:
    """Rosa minima: 1 portiere già bloccato (early) + `late_count` difensori
    che si bloccheranno tutti insieme al prossimo kickoff (late)."""
    athletes: list[Athlete] = []
    provider_id = id_offset
    locked_keeper = Athlete(provider_id=provider_id, canonical_name="P locked")
    provider_id += 1
    db_session.add(locked_keeper)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=locked_keeper.id,
            season_year=2026,
            role=FantasyRole.P,
            mapping_version="v1.0.0",
            provider_position_raw="P",
            club_id=early_club_id,
        )
    )
    athletes.append(locked_keeper)

    for index in range(late_count):
        athlete = Athlete(provider_id=provider_id, canonical_name=f"D late {index + 1}")
        provider_id += 1
        db_session.add(athlete)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                athlete_id=athlete.id,
                season_year=2026,
                role=FantasyRole.D,
                mapping_version="v1.0.0",
                provider_position_raw="D",
                club_id=late_club_id,
            )
        )
        athletes.append(athlete)
    db_session.commit()
    return athletes


def _assign_roster(db_session: Session, league_id: str, athletes: list[Athlete]) -> None:
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    slots = db_session.scalars(
        select(FantasyRosterSlot)
        .where(FantasyRosterSlot.fantasy_team_id == team.id)
        .order_by(FantasyRosterSlot.slot_index.asc())
    ).all()
    assert len(slots) >= len(athletes)
    for slot, athlete in zip(slots, athletes, strict=False):
        slot.athlete_id = athlete.id
        slot.purchase_credits = 1
    db_session.commit()


def test_lock_reminder_counts_every_player_sharing_the_next_kickoff(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "lock-reminder-count@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Blocco Conteggio")
    late_kickoff = datetime.now(UTC) + timedelta(hours=1)
    _fantasy_round, early_club_id, late_club_id = _create_round_with_two_fixtures(
        db_session,
        league_id,
        id_offset=9_100_000,
        competition_ids=competition_ids,
        late_kickoff=late_kickoff,
    )
    athletes = _seed_roster(
        db_session,
        id_offset=9_100_100,
        early_club_id=early_club_id,
        late_club_id=late_club_id,
        late_count=3,
    )
    _assign_roster(db_session, league_id, athletes)

    result = LineupLockReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_minutes=180
    )
    db_session.commit()
    assert result["reminders_sent"] == 1

    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.category == NotificationCategory.FORMAZIONE,
            Notification.template_key == "formazione.blocco_imminente",
        )
    )
    assert notification is not None
    assert notification.deep_link == "/formazione"
    # I 3 difensori "late" bloccano insieme, non il portiere già bloccato
    # ("early") prima del giro: nessuna colonna params separata, il testo
    # è già renderizzato al momento della creazione.
    assert "3 calciatori" in notification.body
    assert "si bloccano" in notification.body

    # Rilanciare prima che l'istante di blocco cambi non deve duplicare.
    again = LineupLockReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_minutes=180
    )
    db_session.commit()
    assert again["reminders_sent"] == 0


def test_lock_reminder_ignores_instants_outside_the_window(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    # Conteggi assoluti (teams_checked/rounds_checked) non sono asserti qui:
    # il modulo condivide il DB fra i test (nessun reset per funzione), e il
    # job scansiona TUTTE le leghe — stesso motivo per cui anche
    # test_lineup_reminders.py verifica solo la notifica del proprio utente,
    # mai un contatore assoluto.
    token, user_id = _register_and_login(client, "lock-reminder-far@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Blocco Lontano")
    late_kickoff = datetime.now(UTC) + timedelta(hours=10)
    _fantasy_round, early_club_id, late_club_id = _create_round_with_two_fixtures(
        db_session,
        league_id,
        id_offset=9_200_000,
        competition_ids=competition_ids,
        late_kickoff=late_kickoff,
    )
    athletes = _seed_roster(
        db_session,
        id_offset=9_200_100,
        early_club_id=early_club_id,
        late_club_id=late_club_id,
        late_count=1,
    )
    _assign_roster(db_session, league_id, athletes)

    LineupLockReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_minutes=180
    )
    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.template_key == "formazione.blocco_imminente",
        )
    )
    assert notification is None


def test_lock_reminder_skips_teams_with_an_empty_roster(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "lock-reminder-empty@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Blocco Rosa Vuota")
    _create_round_with_two_fixtures(
        db_session,
        league_id,
        id_offset=9_300_000,
        competition_ids=competition_ids,
        late_kickoff=datetime.now(UTC) + timedelta(hours=1),
    )

    LineupLockReminderService(db_session).send_due_reminders(
        now=datetime.now(UTC), window_minutes=180
    )
    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.template_key == "formazione.blocco_imminente",
        )
    )
    assert notification is None
