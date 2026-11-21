"""Queryable read view over the league audit trail (EP11-03).

Reads the same `LeagueAuditEvent` rows every domain module already writes
(market, trade, homologation, roster, league config, ...) — no new source of
truth, no risk of drifting from what actually happened. League-scoped and
gated by `LEAGUE_ADMIN`, so a league admin only ever sees their own league.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.date_filters import checked_filter_date
from auth.models.user import User
from database.enums import LeagueAuditAction, MarketSessionStatus
from leagues.audit_log_schemas import AuditLogEntryResponse, AuditLogListResponse
from leagues.models.league_audit_event import LeagueAuditEvent
from market.models import MarketSession
from market.windows import effective_status

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


_SEALED_BID_ACTIONS = (
    LeagueAuditAction.MARKET_BID_SUBMITTED,
    LeagueAuditAction.MARKET_BID_WITHDRAWN,
)


class AuditLogService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _open_session_ids(self, league_id: UUID) -> list[str]:
        now = datetime.now(UTC)
        rows = self._session.scalars(
            select(MarketSession).where(MarketSession.league_id == league_id)
        ).all()
        return [
            str(row.id)
            for row in rows
            if effective_status(row, now=now)
            not in (MarketSessionStatus.CLOSED, MarketSessionStatus.RESOLVED)
        ]

    def list_events(
        self,
        *,
        league_id: UUID,
        action: LeagueAuditAction | None = None,
        actor_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AuditLogListResponse:
        date_from = checked_filter_date(date_from)
        date_to = checked_filter_date(date_to)
        filters = [LeagueAuditEvent.league_id == league_id]
        # Le buste segrete non si leggono nemmeno da qui finché la sessione è aperta.
        open_sessions = self._open_session_ids(league_id)
        if open_sessions:
            filters.append(
                ~(
                    LeagueAuditEvent.action.in_(_SEALED_BID_ACTIONS)
                    & LeagueAuditEvent.details["sessionId"].astext.in_(open_sessions)
                )
            )
        if action is not None:
            filters.append(LeagueAuditEvent.action == action)
        if actor_id is not None:
            filters.append(LeagueAuditEvent.actor_id == actor_id)
        if date_from is not None:
            filters.append(LeagueAuditEvent.created_at >= date_from)
        if date_to is not None:
            filters.append(LeagueAuditEvent.created_at <= date_to)

        total_count = self._session.scalar(
            select(func.count()).select_from(LeagueAuditEvent).where(*filters)
        )
        total_count = total_count or 0
        total_pages = math.ceil(total_count / page_size) if total_count else 0

        rows = self._session.scalars(
            select(LeagueAuditEvent)
            .where(*filters)
            .order_by(LeagueAuditEvent.created_at.desc(), LeagueAuditEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        actor_ids = {row.actor_id for row in rows}
        actors = {
            user.id: user
            for user in self._session.scalars(select(User).where(User.id.in_(actor_ids)))
        }

        items = [
            AuditLogEntryResponse(
                id=str(row.id),
                occurredAt=row.created_at.isoformat(),
                # Evento automatico: nessun autore, non la stringa «None».
                actorId=str(row.actor_id) if row.actor_id is not None else None,
                actorDisplayName=(
                    actors[row.actor_id].display_name if row.actor_id in actors else None
                ),
                action=row.action.value,
                details=row.details,
            )
            for row in rows
        ]
        return AuditLogListResponse(
            items=items, page=page, pageSize=page_size, total=total_count, totalPages=total_pages
        )
