"""Immutable credit ledger helpers (EP05-02)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import CreditLedgerReason
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyTeam
from fantasy_teams.validators import (
    validate_credit_amount_nonzero,
    validate_ledger_balance_non_negative,
    validate_transaction_id,
)
from leagues.models.league_rules import LeagueRules


def resolve_initial_credits(session: Session, league_id: UUID) -> int:
    rules = session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
    if rules is None:
        return 1000
    return rules.total_credits


def find_account_for_team(
    session: Session,
    fantasy_team_id: UUID,
    *,
    for_update: bool = False,
) -> CreditAccount | None:
    stmt = select(CreditAccount).where(CreditAccount.fantasy_team_id == fantasy_team_id)
    if for_update:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def reconstruct_balance(session: Session, account_id: UUID) -> int:
    entries = session.scalars(
        select(CreditLedgerEntry)
        .where(CreditLedgerEntry.account_id == account_id)
        .order_by(CreditLedgerEntry.created_at.asc(), CreditLedgerEntry.id.asc())
    ).all()
    return sum(entry.amount for entry in entries)


def apply_ledger_movement(
    session: Session,
    account: CreditAccount,
    *,
    amount: int,
    reason: CreditLedgerReason,
    transaction_id: str,
    actor_id: UUID | None = None,
    note: str | None = None,
) -> tuple[CreditLedgerEntry, bool]:
    """Append a ledger entry and update balance atomically.

    Returns ``(entry, created)``. Replaying the same ``transaction_id`` is idempotent.
    Caller must hold a row lock on ``account`` when concurrent writers are possible.
    """
    txn = validate_transaction_id(transaction_id)
    validate_credit_amount_nonzero(amount)

    existing = session.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.transaction_id == txn,
        )
    )
    if existing is not None:
        return existing, False

    new_balance = validate_ledger_balance_non_negative(account.balance + amount)
    entry = CreditLedgerEntry(
        account_id=account.id,
        amount=amount,
        reason=reason,
        transaction_id=txn,
        balance_after=new_balance,
        note=note[:255] if note else None,
        actor_id=actor_id,
    )
    account.balance = new_balance
    account.version += 1
    try:
        with session.begin_nested():
            session.add(entry)
            session.flush()
    except IntegrityError as exc:
        # Concurrent insert with same transaction_id — treat as idempotent replay.
        session.refresh(account)
        replayed = session.scalar(
            select(CreditLedgerEntry).where(
                CreditLedgerEntry.account_id == account.id,
                CreditLedgerEntry.transaction_id == txn,
            )
        )
        if replayed is not None:
            return replayed, False
        raise ValidationAuthError(
            "Conflitto sul movimento di crediti.",
            code="credit_ledger_conflict",
        ) from exc
    return entry, True


def ensure_credit_account_for_team(
    session: Session,
    team: FantasyTeam,
    *,
    actor_id: UUID | None = None,
) -> tuple[CreditAccount, bool]:
    """Ensure a credit account exists, seeding with initial allocation if needed.

    Returns ``(account, initialized)``.
    """
    existing = find_account_for_team(session, team.id, for_update=True)
    if existing is not None:
        return existing, False

    initial = resolve_initial_credits(session, team.league_id)
    account = CreditAccount(
        fantasy_team_id=team.id,
        balance=0,
        version=0,
    )
    session.add(account)
    session.flush()

    if initial > 0:
        apply_ledger_movement(
            session,
            account,
            amount=initial,
            reason=CreditLedgerReason.INITIAL_ALLOCATION,
            transaction_id=f"initial:{team.id}",
            actor_id=actor_id,
            note="Allocazione iniziale crediti di lega",
        )
    return account, True
