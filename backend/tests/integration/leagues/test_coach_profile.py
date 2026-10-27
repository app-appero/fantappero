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

    # Nessun nome di lega nel payload; l'email c'è, visibile solo a chi
    # amministra la lega (EP13-P06bis).
    serialized = response.text
    assert league.name not in serialized
    assert body["email"] == coach.email
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


def test_requester_can_query_their_own_profile(
    client: TestClient, competition_ids: list[str]
) -> None:
    """Regressione bug 8a: cliccare sul proprio nome in Classifica non deve
    restituire "Profilo non trovato". La directory espone già sé stessi con
    `isSelf=True`, quindi il lookup singolo deve restare coerente e non
    escludere il chiamante."""
    token, user_id = _register_and_login(client, "dir-self@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Se Stesso")

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["userId"] == str(user_id)


def test_current_league_member_is_reachable_from_standings(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Click su un nome in Classifica: il compagno/avversario di lega è
    già membro della lega interrogata, e deve restare profilabile
    (regressione: prima veniva escluso come i candidati già iscritti)."""
    token, _ = _register_and_login(client, "dir-standings-admin@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Classifica")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "compagno", seed)
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=coach.id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["userId"] == str(coach.id)


def test_a_plain_member_can_open_a_teammates_profile_without_seeing_email(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Click su un nome in Classifica da parte di chi NON amministra la lega:
    deve funzionare (prima richiedeva Permission.LEAGUE_ADMIN, bloccando
    qualunque membro normale), ma senza l'email del fantallenatore
    guardato — quella resta un dato riservato a chi amministra la lega
    (EP13-P06bis)."""
    admin_token, _ = _register_and_login(client, "member-view-admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Membro")

    member_token, member_id = _register_and_login(client, "member-view-caller@example.com")
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "visto-da-membro", seed)
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=coach.id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["userId"] == str(coach.id)
    assert body["email"] is None


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


def _promote_to_operator(db_session: Session, user_id: UUID) -> None:
    user = db_session.get(User, user_id)
    assert user is not None
    user.platform_role = PlatformRole.OPERATOR
    db_session.commit()


def test_impersonated_league_admin_can_open_a_teammates_profile(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Regressione bug 8b: un operatore impersona un utente normale (A, admin
    della propria lega) e deve poter aprire il profilo di un ALTRO
    fantallenatore (B) della stessa lega, esattamente come se A avesse
    effettuato login normalmente.

    L'endpoint di `impersonate` emette un access token che è, a tutti gli
    effetti, il token dell'utente target: non esiste un claim separato che
    preservi l'identità dell'operatore reale (`backend/src/admin/service.py`,
    `create_access_token(user_id=user.id, ...)`). Di conseguenza i permessi
    durante l'impersonazione sono SEMPRE quelli dell'utente impersonato nella
    lega richiesta (qui: admin, perché A ha creato la lega), non quelli
    dell'operatore. Questo test fissa quel comportamento come corretto."""
    operator_token, operator_id = _register_and_login(client, "imp-operator@example.com")
    _promote_to_operator(db_session, operator_id)

    normal_token, normal_id = _register_and_login(client, "imp-normal-admin@example.com")
    league_id = _create_league(client, normal_token, competition_ids, "Lega Impersonata")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    teammate = _make_coach(db_session, "impersonato-teammate", seed)
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=teammate.id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()

    impersonate = client.post(
        f"/admin/users/{normal_id}/impersonate",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert impersonate.status_code == 200, impersonate.text
    impersonated_token = impersonate.json()["accessToken"]

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{teammate.id}",
        headers={"Authorization": f"Bearer {impersonated_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["userId"] == str(teammate.id)


def test_profile_works_for_a_coach_with_unverified_email(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Regressione: la directory elenca anche fantallenatori con email non
    verificata (badge "Email non verificata" in UI) — il profilo deve
    restare apribile per loro, non rispondere "Fantallenatore non trovato"
    solo perché non hanno ancora verificato l'email."""
    token, _ = _register_and_login(client, "unverified-viewer@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Non Verificato")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    coach = _make_coach(db_session, "non-verificato", seed)
    coach.email_verified_at = None
    db_session.add(coach)
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{coach.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["userId"] == str(coach.id)


def test_profile_works_for_a_coach_without_a_profile_row(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Regressione: un fantallenatore creato manualmente (utente MANUALE)
    può non avere ancora una riga `UserProfile` (nickname/avatar/display
    name mai impostati). Il profilo deve comunque apparire, con il nome
    visualizzato ricavato dall'email come fa già la directory, non un
    "Fantallenatore non trovato" per assenza di un INNER JOIN su un profilo
    che semplicemente non esiste ancora."""
    token, _ = _register_and_login(client, "no-profile-viewer@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Senza Profilo")

    seed = int(datetime.now(UTC).timestamp() * 1000) % 400_000
    bare_user = User(
        email=f"manuale-{seed}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=NOW - timedelta(days=400),
        user_type=UserType.HUMAN,
    )
    db_session.add(bare_user)
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori/{bare_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["userId"] == str(bare_user.id)
    assert body["displayName"] == f"manuale-{seed}"
    assert body["availableForInvites"] is False
