"""Per-user daily quota for AI-assisted advice (EP10-05).

No Gratis/Pro entitlement tiers exist yet (EP11-01 lands later); this
enforces one default daily cap per user across all EP10 features. The limit
is a plain module constant on purpose — a future entitlement lookup can
replace ``DEFAULT_DAILY_LIMIT`` without changing this function's contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_assistant.exceptions import AiQuotaExceededError
from ai_assistant.models import AiInteraction

DEFAULT_DAILY_LIMIT = 20


def check_daily_quota(
    session: Session,
    user_id: UUID,
    *,
    limit: int = DEFAULT_DAILY_LIMIT,
    now: datetime | None = None,
) -> None:
    reference = now or datetime.now(UTC)
    window_start = reference - timedelta(hours=24)
    count = session.scalar(
        select(func.count(AiInteraction.id)).where(
            AiInteraction.user_id == user_id,
            AiInteraction.created_at >= window_start,
        )
    )
    if (count or 0) >= limit:
        raise AiQuotaExceededError()
