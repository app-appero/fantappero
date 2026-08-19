"""Queryable read view over the league audit trail (EP11-03).

Reads the same `LeagueAuditEvent` rows every domain module already writes
(market, trade, homologation, roster, league config, ...) — no new source of
truth, no risk of drifting from what actually happened. League-scoped and
gated by `LEAGUE_ADMIN`, so a league admin only ever sees their own league.
"""

from __future__ import annotations

import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.models.user import User
from database.enums import LeagueAuditAction
from leagues.audit_log_schemas import AuditLogEntryResponse, AuditLogListResponse
from leagues.models.league_audit_event import LeagueAuditEvent

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class AuditLogService:
    def __init__(self, session: Session) -> None:
        self._session = session

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
        filters = [LeagueAuditEvent.league_id == league_id]
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
                actorId=str(row.actor_id),
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
