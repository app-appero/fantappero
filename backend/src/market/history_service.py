"""Market history: read-only, filterable view of the market audit trail (EP08-08 / FR-MKT-04).

The league already writes an immutable `LeagueAuditEvent` row for every market
mutation (session lifecycle, bids, resolutions, releases/refunds, trade
decisions, admin credit adjustments) in the same transaction as the mutation
itself — see `market/service.py::_add_audit` and `market/trade_service.py::
_add_audit`. This module does not introduce a new source of truth: it reads
that existing trail, so it can never diverge from the ledger/ownership state
it describes ("coerente con ledger/possessi") and never performs a write of
its own ("Nessuna operazione parziale" is trivially satisfied — there is no
operation to leave partial).
"""

from __future__ import annotations

import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import LeagueAuditAction
from leagues.models.league_audit_event import LeagueAuditEvent
from market.history_schemas import MarketHistoryEntryResponse, MarketHistoryListResponse
from market.models import TradeProposal

# Every audit action that can appear in the market history, grouped by the
# category the card asks the feed to distinguish ("acquisti, svincoli,
# scambi, crediti, interventi manuali"). Credit movements are not a separate
# audit action of their own for market-originated flows (the amount is
# already carried inline in the acquisto/svincolo/scambio event that caused
# it — see the `details` payload of each), so "crediti" surfaces as a field
# on every entry rather than as a fifth category; the one place credits move
# without an acquisto/svincolo/scambio behind them is a manual admin
# adjustment, which is exactly `CREDIT_LEDGER_ENTRY_POSTED` below.
_ACQUISTO_ACTIONS = frozenset(
    {
        LeagueAuditAction.MARKET_SESSION_CREATED,
        LeagueAuditAction.MARKET_SESSION_CLOSED,
        LeagueAuditAction.MARKET_BID_SUBMITTED,
        LeagueAuditAction.MARKET_BID_WITHDRAWN,
        LeagueAuditAction.MARKET_SESSION_RESOLVED,
        LeagueAuditAction.MARKET_TIEBREAK_OPENED,
    }
)
_SCAMBIO_ACTIONS = frozenset(
    {
        LeagueAuditAction.MARKET_TRADE_PROPOSED,
        LeagueAuditAction.MARKET_TRADE_CANCELLED,
        LeagueAuditAction.MARKET_TRADE_ACCEPTED,
        LeagueAuditAction.MARKET_TRADE_REJECTED,
        LeagueAuditAction.MARKET_TRADE_COUNTERED,
        LeagueAuditAction.MARKET_TRADE_APPROVED,
        LeagueAuditAction.MARKET_TRADE_REJECTED_BY_ADMIN,
    }
)
# FANTASY_ROSTER_SLOT_RELEASED is emitted both by the market's voluntary/exit
# release flow (market/service.py::apply_release, `details` always carries
# "reason") and by admin manual roster management (fantasy_teams/service.py,
# no "reason" key). Only the former belongs in the *market* history.
_SVINCOLO_ACTION = LeagueAuditAction.FANTASY_ROSTER_SLOT_RELEASED
# CREDIT_LEDGER_ENTRY_POSTED is only ever raised for a manual admin credit
# adjustment (fantasy_teams/service.py::admin_post_credit_movement); market
# flows post to the ledger without a standalone audit row of this kind, since
# their own acquisto/svincolo/scambio event already carries the amount.
_INTERVENTO_MANUALE_ACTION = LeagueAuditAction.CREDIT_LEDGER_ENTRY_POSTED

_ALL_HISTORY_ACTIONS = frozenset(
    _ACQUISTO_ACTIONS | _SCAMBIO_ACTIONS | {_SVINCOLO_ACTION, _INTERVENTO_MANUALE_ACTION}
)

VALID_CATEGORIES = frozenset({"acquisto", "svincolo", "scambio", "intervento_manuale"})

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
# A single league's market history is bounded by one season's worth of
# sessions, bids, trades and manual adjustments — a few hundred rows in
# practice. Scanning the most recent slice below (rather than the full
# table) keeps the team/category filtering below simple and in-memory
# without needing brittle JSONB path queries across the several different
# `details` shapes each action uses; it is not meant to scale to a
# multi-season, cross-league analytics view.
_MAX_EVENTS_SCANNED = 2000


def category_for(action: LeagueAuditAction, details: dict[str, object] | None) -> str | None:
    if action == _SVINCOLO_ACTION:
        return "svincolo" if details and "reason" in details else None
    if action in _ACQUISTO_ACTIONS:
        return "acquisto"
    if action in _SCAMBIO_ACTIONS:
        return "scambio"
    if action == _INTERVENTO_MANUALE_ACTION:
        return "intervento_manuale"
    return None


def proposal_ids_in(details: dict[str, object] | None) -> set[str]:
    details = details or {}
    ids: set[str] = set()
    for key in ("proposalId", "originalProposalId", "counterProposalId"):
        value = details.get(key)
        if isinstance(value, str):
            ids.add(value)
    return ids


def team_ids_for(
    details: dict[str, object] | None,
    proposal_teams: dict[str, tuple[str, str]],
) -> set[str]:
    details = details or {}
    ids: set[str] = set()
    for key in ("fantasyTeamId", "proposerTeamId", "recipientTeamId"):
        value = details.get(key)
        if isinstance(value, str):
            ids.add(value)
    team_ids = details.get("teamIds")
    if isinstance(team_ids, list):
        ids.update(value for value in team_ids if isinstance(value, str))
    winners = details.get("winners")
    if isinstance(winners, list):
        for winner in winners:
            if isinstance(winner, dict):
                team_id = winner.get("fantasyTeamId")
                if isinstance(team_id, str):
                    ids.add(team_id)
    for proposal_id in proposal_ids_in(details):
        teams = proposal_teams.get(proposal_id)
        if teams is not None:
            ids.update(teams)
    return ids


class MarketHistoryService:
    """Read-only aggregation over the existing market audit trail."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_history(
        self,
        league_access: LeagueAccess,
        *,
        category: str | None = None,
        fantasy_team_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> MarketHistoryListResponse:
        if category is not None and category not in VALID_CATEGORIES:
            raise ValidationAuthError(
                "Categoria di storico non valida.",
                code="invalid_history_category",
            )

        query = (
            select(LeagueAuditEvent)
            .where(
                LeagueAuditEvent.league_id == league_access.league.id,
                LeagueAuditEvent.action.in_(_ALL_HISTORY_ACTIONS),
            )
            .order_by(LeagueAuditEvent.created_at.desc(), LeagueAuditEvent.id.desc())
            .limit(_MAX_EVENTS_SCANNED)
        )
        if date_from is not None:
            query = query.where(LeagueAuditEvent.created_at >= date_from)
        if date_to is not None:
            query = query.where(LeagueAuditEvent.created_at <= date_to)

        rows = self._session.scalars(query).all()

        proposal_ids: set[str] = set()
        for row in rows:
            if row.action in _SCAMBIO_ACTIONS:
                proposal_ids.update(proposal_ids_in(row.details))
        proposal_teams: dict[str, tuple[str, str]] = {}
        if proposal_ids:
            proposal_uuids = {UUID(value) for value in proposal_ids}
            for proposal_id, proposer_team_id, recipient_team_id in self._session.execute(
                select(
                    TradeProposal.id, TradeProposal.proposer_team_id, TradeProposal.recipient_team_id
                ).where(TradeProposal.id.in_(proposal_uuids))
            ):
                proposal_teams[str(proposal_id)] = (
                    str(proposer_team_id),
                    str(recipient_team_id),
                )

        filtered: list[tuple[LeagueAuditEvent, str]] = []
        for row in rows:
            row_category = category_for(row.action, row.details)
            if row_category is None:
                continue
            if category is not None and row_category != category:
                continue
            if fantasy_team_id is not None and str(fantasy_team_id) not in team_ids_for(
                row.details, proposal_teams
            ):
                continue
            filtered.append((row, row_category))

        total = len(filtered)
        total_pages = math.ceil(total / page_size) if total else 0
        start = (page - 1) * page_size
        page_rows = filtered[start : start + page_size]

        return MarketHistoryListResponse(
            items=[
                MarketHistoryEntryResponse(
                    id=str(row.id),
                    occurredAt=row.created_at.isoformat(),
                    category=row_category,
                    action=row.action.value,
                    actorId=str(row.actor_id),
                    details=row.details,
                )
                for row, row_category in page_rows
            ],
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )
