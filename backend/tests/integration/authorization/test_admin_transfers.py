"""Authorization and lifecycle tests for the /admin transfer review queue (OQ-12)."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import PlatformRole
from database.session import create_session_factory
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club
from sports_data.roster.models import Athlete, Transfer


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


def _seed_pending_transfer(db_session: Session, *, suffix: str) -> UUID:
    club = Club(provider_id=900_000 + hash(suffix) % 1000, name=f"Club {suffix}")
    athlete = Athlete(provider_id=900_000 + hash(suffix) % 1000 + 1, canonical_name=f"Player {suffix}")
    db_session.add_all([club, athlete])
    db_session.flush()
    transfer = Transfer(
        athlete_id=athlete.id,
        transfer_date=date(2026, 8, 1),
        from_club_id=club.id,
        to_club_id=None,
        transfer_type="Loan",
        requires_admin_review=True,
        provider_key=f"pending-transfer-{suffix}",
    )
    db_session.add(transfer)
    db_session.commit()
    return transfer.id


def test_pending_transfers_requires_authentication(client: TestClient) -> None:
    response = client.get("/admin/transfers/pending-review")
    assert response.status_code == 401


def test_pending_transfers_denied_for_non_operator(
    client: TestClient, db_session: Session
) -> None:
    token, _ = _register_and_login(client, "transfers.member@example.com")
    response = client.get(
        "/admin/transfers/pending-review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_pending_transfer_appears_and_can_be_reviewed(
    client: TestClient, db_session: Session
) -> None:
    token, operator_id = _register_and_login(client, "transfers.operator@example.com")
    _promote(db_session, operator_id)
    transfer_id = _seed_pending_transfer(db_session, suffix="alpha")

    listing = client.get(
        "/admin/transfers/pending-review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200
    ids = [row["id"] for row in listing.json()["items"]]
    assert str(transfer_id) in ids

    review = client.post(
        f"/admin/transfers/{transfer_id}/review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert review.status_code == 200
    assert review.json()["reviewedByUserId"] == str(operator_id)

    listing_after = client.get(
        "/admin/transfers/pending-review",
        headers={"Authorization": f"Bearer {token}"},
    )
    ids_after = [row["id"] for row in listing_after.json()["items"]]
    assert str(transfer_id) not in ids_after


def test_reviewing_twice_is_rejected(client: TestClient, db_session: Session) -> None:
    token, operator_id = _register_and_login(client, "transfers.operator.two@example.com")
    _promote(db_session, operator_id)
    transfer_id = _seed_pending_transfer(db_session, suffix="beta")

    first = client.post(
        f"/admin/transfers/{transfer_id}/review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/admin/transfers/{transfer_id}/review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "admin_transfer_already_reviewed"


def test_reviewing_unknown_transfer_is_not_found(
    client: TestClient, db_session: Session
) -> None:
    token, operator_id = _register_and_login(client, "transfers.operator.three@example.com")
    _promote(db_session, operator_id)

    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.post(
        f"/admin/transfers/{missing_id}/review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "admin_transfer_not_found"
