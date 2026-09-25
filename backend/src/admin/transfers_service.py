"""Admin queue for transfers pending manual review (OQ-12).

Espone in sola lettura ciò che `sports_data.roster.validators` già decide
(Loan/N.D. non sono affidabili per svincolo automatico): finora il flag
``requires_admin_review`` veniva scritto ma non letto da nessuna API o UI,
quindi nessun admin poteva davvero vederlo. Questo modulo aggiunge solo la
visibilità e la conferma manuale — non introduce nuova logica di
rilevamento, quella esiste già.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from admin.exceptions import AdminTransferAlreadyReviewedError, AdminTransferNotFoundError
from admin.schemas import (
    AdminPendingTransferResponse,
    AdminTransferReviewedResponse,
    PaginatedAdminPendingTransfersResponse,
)
from auth.models.user import User
from database.enums import LeagueAuditAction
from leagues.models.league_audit_event import LeagueAuditEvent
from sports_data.roster.models import Transfer


def _total_pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


class AdminTransfersService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_pending_review(self, *, page: int, page_size: int) -> PaginatedAdminPendingTransfersResponse:
        base = (
            select(Transfer)
            .where(
                Transfer.requires_admin_review.is_(True),
                Transfer.reviewed_at.is_(None),
            )
            .options(
                selectinload(Transfer.athlete),
                selectinload(Transfer.from_club),
                selectinload(Transfer.to_club),
            )
        )
        total = self._session.scalar(
            select(func.count()).select_from(
                select(Transfer.id)
                .where(
                    Transfer.requires_admin_review.is_(True),
                    Transfer.reviewed_at.is_(None),
                )
                .subquery()
            )
        )
        rows = self._session.scalars(
            base.order_by(Transfer.transfer_date.desc(), Transfer.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return PaginatedAdminPendingTransfersResponse(
            items=[_to_pending_response(row) for row in rows],
            page=page,
            pageSize=page_size,
            total=total or 0,
            totalPages=_total_pages(total or 0, page_size),
        )

    def mark_reviewed(self, *, actor: User, transfer_id: UUID) -> AdminTransferReviewedResponse:
        transfer = self._session.get(Transfer, transfer_id)
        if transfer is None:
            raise AdminTransferNotFoundError
        if transfer.reviewed_at is not None:
            raise AdminTransferAlreadyReviewedError

        now = datetime.now(UTC)
        transfer.reviewed_at = now
        transfer.reviewed_by_user_id = actor.id
        self._session.flush()
        self._session.add(
            LeagueAuditEvent(
                league_id=None,
                actor_id=actor.id,
                action=LeagueAuditAction.ROSTER_TRANSFER_REVIEWED,
                details={
                    "transferId": str(transfer.id),
                    "athleteId": str(transfer.athlete_id),
                    "transferType": transfer.transfer_type,
                },
            )
        )
        self._session.flush()
        return AdminTransferReviewedResponse(
            id=str(transfer.id),
            reviewedAt=now,
            reviewedByUserId=str(actor.id),
        )


def _to_pending_response(row: Transfer) -> AdminPendingTransferResponse:
    return AdminPendingTransferResponse(
        id=str(row.id),
        athleteId=str(row.athlete_id),
        athleteName=row.athlete.canonical_name if row.athlete else "",
        transferDate=row.transfer_date.isoformat(),
        fromClubName=row.from_club.name if row.from_club else None,
        toClubName=row.to_club.name if row.to_club else None,
        transferType=row.transfer_type,
        createdAt=row.created_at,
    )
