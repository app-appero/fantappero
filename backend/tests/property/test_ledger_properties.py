"""Property-based tests for the credit ledger invariants (EP12-02).

Complements the example-based unit tests in
``tests/unit/fantasy_teams/test_credit_validators.py`` and the single-scenario
concurrency test in ``tests/integration/fantasy_teams/test_credit_ledger.py``
with randomized sequences, so the "nessun saldo negativo" invariant is checked
against many shapes of input, not just hand-picked boundary values.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.exceptions import ValidationAuthError
from database.enums import CreditLedgerReason
from database.session import create_session_factory
from fantasy_teams.ledger import apply_ledger_movement, reconstruct_balance
from fantasy_teams.models import CreditAccount
from fantasy_teams.validators import (
    validate_credit_amount_nonzero,
    validate_ledger_balance_non_negative,
)
from leagues.models.competition import Competition
from mail.capture import get_captured_emails


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


@pytest.fixture
def team_owner_token(client: TestClient) -> str:
    """Registered once per test run — Hypothesis reuses it across all examples
    (argon2 hashing is too slow to repeat per example; only ``amounts`` varies)."""
    token, _ = _register_and_login(client, f"ledger.prop.{uuid4().hex[:10]}@example.com")
    return token


# ---------------------------------------------------------------------------
# Pure validator properties (no DB) — fast, wide input coverage.
# ---------------------------------------------------------------------------


@given(balance=st.integers(min_value=0, max_value=10_000_000))
def test_validate_ledger_balance_accepts_any_non_negative(balance: int) -> None:
    assert validate_ledger_balance_non_negative(balance) == balance


@given(balance=st.integers(min_value=-10_000_000, max_value=-1))
def test_validate_ledger_balance_rejects_any_negative(balance: int) -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_ledger_balance_non_negative(balance)
    assert exc.value.code == "insufficient_credits"


@given(amount=st.integers(min_value=-10_000_000, max_value=10_000_000).filter(lambda v: v != 0))
def test_validate_credit_amount_nonzero_accepts_any_nonzero(amount: int) -> None:
    assert validate_credit_amount_nonzero(amount) == amount


# ---------------------------------------------------------------------------
# Real ledger service property (against Postgres) — random movement sequences
# must never leave a negative balance, and the stored balance must always
# match the sum reconstructed from the append-only entry log.
# ---------------------------------------------------------------------------


@given(
    amounts=st.lists(
        st.integers(min_value=-1600, max_value=1600).filter(lambda value: value != 0),
        min_size=1,
        max_size=6,
    )
)
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_ledger_balance_stays_non_negative_and_reconstructible(
    amounts: list[int],
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    team_owner_token: str,
) -> None:
    league = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {team_owner_token}"},
        json={
            "name": f"Lega Property {uuid4().hex[:8]}",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert league.status_code == 201
    league_id = league.json()["id"]

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {team_owner_token}"},
    )
    assert credits.status_code == 200
    team_id = UUID(credits.json()["fantasyTeamId"])

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == team_id)
    )
    assert account is not None

    for index, amount in enumerate(amounts):
        try:
            apply_ledger_movement(
                db_session,
                account,
                amount=amount,
                reason=CreditLedgerReason.ADMIN_ADJUSTMENT,
                transaction_id=f"prop-{league_id}-{index}",
            )
            db_session.commit()
        except ValidationAuthError as exc:
            # Rejected because it would go negative — nothing was mutated
            # (the raise happens before any flush), so the account and
            # session stay exactly as they were before this attempt.
            assert exc.code == "insufficient_credits"

        assert account.balance >= 0
        assert account.balance == reconstruct_balance(db_session, account.id)
