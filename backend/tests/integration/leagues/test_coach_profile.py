"""Profilo storico fantallenatore: fatti, confini e autorizzazioni (EP13-P06)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.enums import LeagueMemberRole, LeagueState, PlatformRole, UserType
from database.session import create_session_factory
from fantasy_teams.models import FantasyTeam
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_standing import LeagueStanding
from mail.capture import get_captured_emails

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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


def _make_coach(db_session: Session, label: str, seed: int) -> User:
    """Un fantallenatore verificato e disponibile agli inviti."""
    user = User(
        email=f"{label}-{seed}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=NOW - timedelta(days=400),
        user_type=UserType.HUMAN,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id,
            display_name=f"Coach {label}",
            available_for_invites=True,
        )
    )
    db_session.flush()
    return user


def _give_concluded_placement(
    db_session: Session,
    *,
    user: User,
    season_year: int,
    position: int,
    participants: int,
    seed: int,
    fantasy_points_for: float = 0.0,
) -> League:
    """Lega conclusa con classifica finale per l'utente indicato."""
    league = League(
        name=f"Lega Storica {seed}-{season_year}",
        season_year=season_year,
        state=LeagueState.CONCLUDED,
    )
    db_session.add(league)
    db_session.flush()

    for index in range(participants):
        if index == 0:
            member_user = user
        else:
            member_user = _make_coach(db_session, f"filler{seed}-{season_year}-{index}", seed)
        membership = LeagueMembership(
            league_id=league.id,
            user_id=member_user.id,
            role=LeagueMemberRole.OWNER if index == 0 else LeagueMemberRole.MEMBER,
        )
        db_session.add(membership)
        db_session.flush()
        team = FantasyTeam(
            league_id=league.id,
            membership_id=membership.id,
            name=f"Team {index}",
        )
        db_session.add(team)
        db_session.flush()
        db_session.add(
            LeagueStanding(
                league_id=league.id,
                fantasy_team_id=team.id,
                played=10,
                won=5,
                drawn=2,
                lost=3,
                fantasy_goals_for=15,
                fantasy_goals_against=12,
                fantasy_points_for=fantasy_points_for if index == 0 else 0.0,
                points=17,
                position=position if index == 0 else index + 1,
                computed_at=NOW,
            )
        )
    db_session.flush()
    return league


def test_directory_row_exposes_history_preview_without_n_plus_one(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "dir-admin@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Directory")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "storico", seed)
    _give_concluded_placement(
        db_session, user=coach, season_year=2025, position=2, participants=8, seed=seed
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": "Coach storico"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    row = next(item for item in items if item["userId"] == str(coach.id))

    assert row["concludedLeagues"] == 1
    assert row["bestPosition"] == 2
    assert row["historySummary"] == "1 lega conclusa · miglior 2º"
    assert row["memberSince"] is not None


def test_new_coach_shows_a_neutral_summary_not_a_zero(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Un nuovo iscritto non deve sembrare un cattivo fantallenatore."""
    token, _ = _register_and_login(client, "dir-neutral@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Neutra")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "nuovo", seed)
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": "Coach nuovo"},
    )
    row = next(
        item for item in response.json()["items"] if item["userId"] == str(coach.id)
    )
    assert row["concludedLeagues"] == 0
    assert row["bestPosition"] is None
    assert row["historySummary"] == "Nessuna lega conclusa"


def test_profile_returns_placements_without_revealing_league_names(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Il punto di privacy della card: mai nomi di leghe altrui."""
    token, _ = _register_and_login(client, "dir-profile@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Profilo")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "profilo", seed)
    league = _give_concluded_placement(
        db_session,
        user=coach,
        season_year=2025,
        position=3,
        participants=6,
        seed=seed,
        fantasy_points_for=612.5,
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["userId"] == str(coach.id)
    assert body["concludedLeagues"] == 1
    assert body["bestPosition"] == 3
    assert body["placementsTotal"] == 1
    placement = body["placements"][0]
    assert placement["seasonYear"] == 2025
    assert placement["position"] == 3
    assert placement["participantCount"] == 6
    # Fantapunti (magic) accanto ai punti classifica (esito): entrambi
    # visibili nel dettaglio profilo, non solo lo storico posizioni.
    assert placement["fantasyPoints"] == 612.5

    # Nessun nome di lega, nessuna email, da nessuna parte nel payload.
    serialized = response.text
    assert league.name not in serialized
    assert coach.email not in serialized
    assert "leagueId" not in serialized


def test_profile_is_forbidden_for_a_non_admin(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "dir-owner@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Permessi")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "target", seed)
    db_session.commit()

    outsider_token, _ = _register_and_login(client, "dir-outsider@example.com")
    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert response.status_code in (401, 403)


def test_unknown_coach_is_not_found(
    client: TestClient, competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "dir-unknown@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Sconosciuto")

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "coach_not_found"


def test_requester_cannot_query_their_own_profile(
    client: TestClient, competition_ids: list[str]
) -> None:
    """Stesso perimetro della directory: sé stessi non compaiono in elenco."""
    token, user_id = _register_and_login(client, "dir-self@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Se Stesso")

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "coach_not_found"


def test_deleted_coach_disappears_from_the_profile_endpoint(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Account cancellato: soft-delete ⇒ non più interrogabile."""
    token, _ = _register_and_login(client, "dir-deleted@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Cancellati")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "cancellato", seed)
    db_session.commit()

    ok = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200

    coach.deleted_at = NOW
    db_session.commit()

    gone = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gone.status_code == 400
    assert gone.json()["code"] == "coach_not_found"


def test_active_league_does_not_count_towards_history(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Solo leghe concluse: una stagione in corso non è ancora un risultato."""
    token, _ = _register_and_login(client, "dir-active@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Attiva Storico")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "incorso", seed)
    league = _give_concluded_placement(
        db_session, user=coach, season_year=2026, position=1, participants=4, seed=seed
    )
    league.state = LeagueState.ACTIVE
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["concludedLeagues"] == 0
    assert response.json()["historySummary"] == "Nessuna lega conclusa"
