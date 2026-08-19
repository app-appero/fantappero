"""Entitlement resolution: current plan, safe server-side downgrade (EP11-01).

Never touches credits, roster moves, trades or scores — the only thing an
entitlement changes is which limits (e.g. the EP10-05 AI daily quota) apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from billing.models import UserEntitlement
from database.enums import SubscriptionPlan

FREE_AI_DAILY_LIMIT = 20
PRO_AI_DAILY_LIMIT = 100


@dataclass(frozen=True)
class EntitlementStatus:
    plan: SubscriptionPlan
    active_until: datetime | None
    ai_daily_limit: int


class EntitlementService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_status(self, user_id: UUID, *, now: datetime | None = None) -> EntitlementStatus:
        reference = now or datetime.now(UTC)
        row = self._session.get(UserEntitlement, user_id)
        if row is None or row.plan == SubscriptionPlan.FREE:
            return EntitlementStatus(SubscriptionPlan.FREE, None, FREE_AI_DAILY_LIMIT)

        if row.active_until is not None and row.active_until <= reference:
            # Safe downgrade: an expired PRO window reverts to FREE immediately,
            # persisted here so every subsequent read (and quota check) sees it.
            row.plan = SubscriptionPlan.FREE
            row.active_until = None
            self._session.flush()
            return EntitlementStatus(SubscriptionPlan.FREE, None, FREE_AI_DAILY_LIMIT)

        return EntitlementStatus(SubscriptionPlan.PRO, row.active_until, PRO_AI_DAILY_LIMIT)

    def activate_pro_until(self, user_id: UUID, *, until: datetime) -> UserEntitlement:
        row = self._session.get(UserEntitlement, user_id)
        if row is None:
            row = UserEntitlement(user_id=user_id, plan=SubscriptionPlan.PRO, active_until=until)
            self._session.add(row)
        else:
            row.plan = SubscriptionPlan.PRO
            row.active_until = until
        self._session.flush()
        return row
