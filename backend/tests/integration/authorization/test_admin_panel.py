"""Authorization tests for the /admin platform panel (EP11-04a)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import LeagueMemberRole, LeagueState, PlatformRole
from database.session import create_session_factory
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails

ADMIN_PATHS = [
    "/admin/overview",
    "/admin/users",
    "/admin/leagues",
    "/admin/listone?seasonYear=2026",
]


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
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    user_id = UUID(login.json()["user"]["id"])
    return login.json()["accessToken"], user_id


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


def _promote(db_session: Session, user_id: UUID) -> None:
    user = db_session.get(User, user_id)
    assert user is not None
    user.platform_role = PlatformRole.OPERATOR
    db_session.commit()


def _seed_league(db_session: Session, *, name: str, owner_id: UUID) -> UUID:
    league = League(name=name, season_year=2025, state=LeagueState.DRAFT)
    db_session.add(league)
    db_session.flush()
    db_session.add(
        LeagueMembership(league_id=league.id, user_id=owner_id, role=LeagueMemberRole.OWNER)
    )
    db_session.add(
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
    db_session.commit()
    return league.id


def test_admin_routes_require_authentication(client: TestClient) -> None:
    for path in ADMIN_PATHS:
        response = client.get(path)
        assert response.status_code == 401, path


def test_admin_routes_denied_for_member(client: TestClient, db_session: Session) -> None:
    token, _ = _register_and_login(client, "admin.member@example.com")
    for path in ADMIN_PATHS:
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403, path
        assert response.json()["code"] == "forbidden"


def test_admin_routes_denied_for_league_admin(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "admin.league.owner@example.com")
    _seed_league(db_session, name="Lega Test", owner_id=user_id)
    for path in ADMIN_PATHS:
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403, path


def test_admin_overview_for_operator(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "admin.operator.one@example.com")
    _promote(db_session, user_id)

    response = client.get("/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["operatorId"] == str(user_id)
    assert body["environment"] == "test"
    assert body["operatorsCount"] >= 1


def test_admin_overview_does_not_count_deleted_accounts(
    client: TestClient, db_session: Session
) -> None:
    """QA 19-20/11: la dashboard diceva 129 utenti, l'elenco Utenti 112 (contava gli eliminati)."""
    token, operator_id = _register_and_login(client, "admin.overview.op@example.com")
    _promote(db_session, operator_id)
    headers = {"Authorization": f"Bearer {token}"}
    _, deleted_id = _register_and_login(client, "admin.overview.deleted@example.com")
    _, kept_id = _register_and_login(client, "admin.overview.kept@example.com")
    _, former_operator_id = _register_and_login(client, "admin.overview.former.op@example.com")
    _promote(db_session, former_operator_id)

    before = client.get("/admin/overview", headers=headers).json()
    deleted = client.post(f"/admin/users/{deleted_id}/delete", headers=headers)
    assert deleted.status_code == 200, deleted.json()
    # Un operatore con l'account eliminato (es. cancellazione dal profilo) non conta più.
    db_session.execute(
        update(User).where(User.id == former_operator_id).values(deleted_at=func.now())
    )
    db_session.commit()

    after = client.get("/admin/overview", headers=headers).json()
    assert after["usersCount"] == before["usersCount"] - 2
    assert after["operatorsCount"] == before["operatorsCount"] - 1
    # Stesso numero dell'elenco Utenti, che esclude gli account eliminati.
    users = client.get("/admin/users", headers=headers).json()
    assert after["usersCount"] == users["total"]
    assert str(kept_id) in {row["id"] for row in users["items"]}
    assert str(deleted_id) not in {row["id"] for row in users["items"]}
    active_operators = db_session.scalar(
        select(func.count(User.id)).where(
            User.deleted_at.is_(None), User.platform_role == PlatformRole.OPERATOR
        )
    )
    assert after["operatorsCount"] == active_operators


def test_admin_users_list_and_promote_revoke(client: TestClient, db_session: Session) -> None:
    op_token, op_id = _register_and_login(client, "admin.operator.two@example.com")
    _promote(db_session, op_id)
    _, target_id = _register_and_login(client, "admin.target@example.com")

    listing = client.get(
        "/admin/users?query=admin.target",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert listing.status_code == 200
    emails = [row["email"] for row in listing.json()["items"]]
    assert "admin.target@example.com" in emails

    promote = client.post(
        f"/admin/users/{target_id}/promote",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert promote.status_code == 200
    assert promote.json()["platformRole"] == "operator"

    revoke = client.post(
        f"/admin/users/{target_id}/revoke",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert revoke.status_code == 200
    assert revoke.json()["platformRole"] == "user"


def test_admin_cannot_revoke_last_operator(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "admin.sole.operator@example.com")
    _promote(db_session, user_id)
    # Isolate from operators promoted by other tests sharing this module's database.
    db_session.execute(
        update(User)
        .where(User.id != user_id, User.platform_role == PlatformRole.OPERATOR)
        .values(platform_role=PlatformRole.USER)
    )
    db_session.commit()

    response = client.post(
        f"/admin/users/{user_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "last_operator"


def test_admin_promote_unknown_user_returns_not_found(
    client: TestClient, db_session: Session
) -> None:
    token, user_id = _register_and_login(client, "admin.operator.three@example.com")
    _promote(db_session, user_id)

    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.post(
        f"/admin/users/{missing_id}/promote",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "admin_user_not_found"


def test_admin_leagues_list_shows_owner(client: TestClient, db_session: Session) -> None:
    token, op_id = _register_and_login(client, "admin.operator.four@example.com")
    _promote(db_session, op_id)
    _, owner_id = _register_and_login(client, "admin.league.owner.two@example.com")
    _seed_league(db_session, name="Lega Globale", owner_id=owner_id)

    response = client.get("/admin/leagues", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    names = {row["name"] for row in response.json()["items"]}
    assert "Lega Globale" in names


def test_admin_can_delete_active_league_and_members_are_notified(
    client: TestClient, db_session: Session
) -> None:
    from sqlalchemy import select

    from notifications.models import Notification

    token, op_id = _register_and_login(client, "admin.operator.del@example.com")
    _promote(db_session, op_id)
    _, owner_id = _register_and_login(client, "admin.league.owner.del@example.com")
    league_id = _seed_league(db_session, name="Lega Da Eliminare", owner_id=owner_id)
    db_session.execute(
        update(League).where(League.id == league_id).values(state=LeagueState.ACTIVE)
    )
    db_session.commit()

    response = client.delete(
        f"/admin/leagues/{league_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(League, league_id) is None
    notes = db_session.scalars(
        select(Notification).where(
            Notification.user_id == owner_id, Notification.template_key == "lega.eliminata"
        )
    ).all()
    assert len(notes) == 1

    again = client.delete(
        f"/admin/leagues/{league_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert again.status_code == 404


def test_admin_delete_league_withdraws_pending_named_invites(
    client: TestClient, db_session: Session
) -> None:
    """QA 21→22/11: anche con l'eliminazione da operatore la notifica «Nuovo invito»
    restava all'invitato, senza nessun «Lega eliminata»."""
    from auth.models.user_profile import UserProfile
    from notifications.models import Notification

    token, op_id = _register_and_login(client, "admin.operator.del.invite@example.com")
    _promote(db_session, op_id)
    owner_token, owner_id = _register_and_login(client, "admin.owner.del.invite@example.com")
    _, guest_id = _register_and_login(client, "admin.guest.del.invite@example.com")
    profile = db_session.scalars(select(UserProfile).where(UserProfile.user_id == guest_id)).one()
    profile.available_for_invites = True
    db_session.commit()
    league_id = _seed_league(db_session, name="Lega Inviti Operatore", owner_id=owner_id)
    invited = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(guest_id)},
    )
    assert invited.status_code in (200, 201), invited.text

    def guest_notes(template_key: str) -> list[Notification]:
        return list(
            db_session.scalars(
                select(Notification).where(
                    Notification.user_id == guest_id, Notification.template_key == template_key
                )
            ).all()
        )

    assert len(guest_notes("sistema.invito_lega")) == 1

    response = client.delete(
        f"/admin/leagues/{league_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204
    db_session.expire_all()
    assert guest_notes("sistema.invito_lega") == []
    deleted = guest_notes("lega.eliminata")
    assert [note.body for note in deleted] == [
        "La lega Lega Inviti Operatore è stata eliminata dall'amministrazione."
    ]
    # Il proprietario resta avvisato una volta sola, come prima.
    owner_notes = db_session.scalars(
        select(Notification).where(
            Notification.user_id == owner_id, Notification.template_key == "lega.eliminata"
        )
    ).all()
    assert len(owner_notes) == 1


def test_admin_delete_league_denied_for_member(client: TestClient, db_session: Session) -> None:
    token, _ = _register_and_login(client, "admin.member.del@example.com")
    response = client.delete(
        "/admin/leagues/00000000-0000-4000-8000-000000000099",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_listone_refresh_denied_for_member(client: TestClient, db_session: Session) -> None:
    token, _ = _register_and_login(client, "admin.listone.member@example.com")
    response = client.post(
        "/admin/listone/aggiorna?seasonYear=2026",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_admin_listone_refresh_job_lifecycle_for_operator(
    client: TestClient, db_session: Session
) -> None:
    """No API_FOOTBALL_KEY in this test env, so the eager job fails deterministically —
    exercises the full start → poll round trip without depending on real provider access."""
    token, user_id = _register_and_login(client, "admin.operator.five@example.com")
    _promote(db_session, user_id)

    start = client.post(
        "/admin/listone/aggiorna?seasonYear=2026",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert start.status_code == 200
    job_id = start.json()["jobId"]
    assert start.json()["status"] == "queued"

    progress = client.get(
        f"/admin/listone/aggiorna/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert progress.status_code == 200
    body = progress.json()
    assert body["status"] == "failed"
    assert body["errorCode"] == "provider_key_missing"


def test_league_listone_refresh_is_operator_only(client: TestClient, db_session: Session) -> None:
    """Rosario 22/11: il listone vale per tutte le leghe della stagione, quindi
    «Aggiorna listone» dalla lega lo può lanciare solo l'operatore, non l'amministratore."""
    owner_token, owner_id = _register_and_login(client, "listone.league.owner@example.com")
    member_token, member_id = _register_and_login(client, "listone.league.member@example.com")
    operator_token, operator_id = _register_and_login(client, "listone.league.operator@example.com")
    _promote(db_session, operator_id)
    league_id = _seed_league(db_session, name="Lega Listone Operatore", owner_id=owner_id)
    db_session.add(
        LeagueMembership(league_id=league_id, user_id=member_id, role=LeagueMemberRole.MEMBER)
    )
    db_session.commit()
    start_path = f"/leagues/{league_id}/amministrazione/listone/aggiorna"
    progress_path = f"{start_path}/00000000-0000-4000-8000-000000000123"

    for path, method in ((start_path, "POST"), (progress_path, "GET")):
        denied = client.request(method, path, headers={"Authorization": f"Bearer {owner_token}"})
        assert denied.status_code == 403, (path, denied.text)
        assert denied.json() == {
            "message": "Solo l'operatore può aggiornare il listone.",
            "code": "listone_refresh_operator_only",
        }
    # Il partecipante semplice resta fuori come prima.
    member = client.post(start_path, headers={"Authorization": f"Bearer {member_token}"})
    assert member.status_code == 403
    assert member.json()["code"] == "forbidden"

    # L'operatore, anche senza essere iscritto alla lega, avvia e segue il job.
    # Senza API_FOOTBALL_KEY nell'ambiente di test il job eager fallisce subito.
    started = client.post(start_path, headers={"Authorization": f"Bearer {operator_token}"})
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "queued"
    progress = client.get(
        f"{start_path}/{started.json()['jobId']}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["status"] == "failed"
    assert progress.json()["errorCode"] == "provider_key_missing"


def test_admin_listone_refresh_progress_unknown_job_not_found(
    client: TestClient, db_session: Session
) -> None:
    token, user_id = _register_and_login(client, "admin.operator.six@example.com")
    _promote(db_session, user_id)

    response = client.get(
        "/admin/listone/aggiorna/does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "listone_refresh_job_not_found"


def test_admin_active_listone_refresh_denied_for_member(
    client: TestClient, db_session: Session
) -> None:
    token, _ = _register_and_login(client, "admin.listone.active.member@example.com")
    response = client.get(
        "/admin/listone/aggiorna",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_admin_active_listone_refresh_discoverable_by_any_operator(
    client: TestClient, db_session: Session
) -> None:
    """A second operator (who never called .../aggiorna to start it) must still
    be able to discover and watch a job someone else started (EP11-05)."""
    from admin.listone_service import PLATFORM_JOB_SCOPE
    from leagues.listone_refresh_progress import ListoneRefreshProgress, save_progress

    starter_token, starter_id = _register_and_login(client, "admin.operator.eight@example.com")
    _promote(db_session, starter_id)
    watcher_token, watcher_id = _register_and_login(client, "admin.operator.nine@example.com")
    _promote(db_session, watcher_id)

    save_progress(
        ListoneRefreshProgress(
            job_id="integration-active-job",
            league_id=PLATFORM_JOB_SCOPE,
            status="running",
            percent=42,
            stage="roster",
            message="Rosa 80/190: Test Club",
        )
    )
    try:
        response = client.get(
            "/admin/listone/aggiorna",
            headers={"Authorization": f"Bearer {watcher_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body is not None
        assert body["jobId"] == "integration-active-job"
        assert body["status"] == "running"
        assert body["percent"] == 42

        save_progress(
            ListoneRefreshProgress(
                job_id="integration-active-job",
                league_id=PLATFORM_JOB_SCOPE,
                status="completed",
                percent=100,
                stage="completed",
                message="Fatto.",
            )
        )
        cleared = client.get(
            "/admin/listone/aggiorna",
            headers={"Authorization": f"Bearer {starter_token}"},
        )
        assert cleared.status_code == 200
        assert cleared.json() is None
    finally:
        # Never leave a fake "active" job pointer behind for later tests.
        save_progress(
            ListoneRefreshProgress(
                job_id="integration-active-job",
                league_id=PLATFORM_JOB_SCOPE,
                status="completed",
                percent=100,
                stage="completed",
                message="Fatto.",
            )
        )
