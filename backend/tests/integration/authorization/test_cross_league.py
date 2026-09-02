"""Cross-league authorization and IDOR regression tests (EP02-03)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import LeagueMemberRole, LeagueState, PlatformRole
from database.session import create_session_factory
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails


def _extract_token_from_email_body(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else None


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    token = _extract_token_from_email_body(get_captured_emails()[-1].message.text_body)
    assert token
    client.post("/auth/verify-email", json={"token": token})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    user_id = UUID(login.json()["user"]["id"])
    return login.json()["accessToken"], user_id


def _seed_league(
    session: Session,
    *,
    name: str,
    owner_id: UUID,
    member_id: UUID | None = None,
) -> UUID:
    league = League(name=name, season_year=2025, state=LeagueState.DRAFT)
    session.add(league)
    session.flush()
    session.add(
        LeagueMembership(
            league_id=league.id,
            user_id=owner_id,
            role=LeagueMemberRole.OWNER,
        )
    )
    session.add(
        LeagueRules(
            league_id=league.id,
            preset_name="standard",
            participant_count=8,
            roster_size=35,
            goalkeepers=3,
            defenders=11,
            midfielders=11,
            forwards=10,
            total_credits=1000,
            allow_trades=True,
            allow_manual_invites=True,
        )
    )
    if member_id is not None:
        session.add(
            LeagueMembership(
                league_id=league.id,
                user_id=member_id,
                role=LeagueMemberRole.MEMBER,
            )
        )
    session.commit()
    return league.id


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_cross_league_view_denied(client: TestClient, db_session: Session) -> None:
    token_a, user_a = _register_and_login(client, "league.owner.a@example.com")
    token_b, user_b = _register_and_login(client, "league.owner.b@example.com")

    league_a = _seed_league(db_session, name="Lega A", owner_id=user_a)
    league_b = _seed_league(db_session, name="Lega B", owner_id=user_b)

    own = client.get(
        f"/leagues/{league_a}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    foreign = client.get(
        f"/leagues/{league_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert own.status_code == 200
    assert own.json()["name"] == "Lega A"
    assert foreign.status_code == 403
    assert foreign.json()["code"] == "league_access_denied"


def test_cross_league_admin_panel_denied_for_member(
    client: TestClient, db_session: Session
) -> None:
    token_owner, owner_id = _register_and_login(client, "admin.owner@example.com")
    token_member, member_id = _register_and_login(client, "admin.member@example.com")

    league_id = _seed_league(
        db_session,
        name="Lega Admin",
        owner_id=owner_id,
        member_id=member_id,
    )

    owner_panel = client.get(
        f"/leagues/{league_id}/amministrazione",
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    member_panel = client.get(
        f"/leagues/{league_id}/amministrazione",
        headers={"Authorization": f"Bearer {token_member}"},
    )

    assert owner_panel.status_code == 200
    assert member_panel.status_code == 403
    assert member_panel.json()["code"] == "forbidden"


def test_list_leagues_only_shows_own_memberships(client: TestClient, db_session: Session) -> None:
    token_a, user_a = _register_and_login(client, "mine.a@example.com")
    token_b, user_b = _register_and_login(client, "mine.b@example.com")

    _seed_league(db_session, name="Solo A", owner_id=user_a)
    _seed_league(db_session, name="Solo B", owner_id=user_b)

    list_a = client.get("/leagues/mine", headers={"Authorization": f"Bearer {token_a}"})
    list_b = client.get("/leagues/mine", headers={"Authorization": f"Bearer {token_b}"})

    assert list_a.status_code == 200
    assert list_b.status_code == 200
    names_a = {item["name"] for item in list_a.json()}
    names_b = {item["name"] for item in list_b.json()}
    assert names_a == {"Solo A"}
    assert names_b == {"Solo B"}


def test_unknown_league_returns_not_found(client: TestClient) -> None:
    token, _ = _register_and_login(client, "unknown.league@example.com")
    missing_id = "00000000-0000-4000-8000-000000000001"
    response = client.get(
        f"/leagues/{missing_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "league_not_found"


def test_platform_operator_can_access_foreign_league(
    client: TestClient, db_session: Session
) -> None:
    _, owner_id = _register_and_login(client, "operator.owner@example.com")
    token_operator, operator_id = _register_and_login(client, "operator.staff@example.com")

    league_id = _seed_league(db_session, name="Lega Operatore", owner_id=owner_id)

    operator = db_session.get(User, operator_id)
    assert operator is not None
    operator.platform_role = PlatformRole.OPERATOR
    db_session.commit()

    foreign = client.get(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {token_operator}"},
    )
    assert foreign.status_code == 200
    assert foreign.json()["name"] == "Lega Operatore"
