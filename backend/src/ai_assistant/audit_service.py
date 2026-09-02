"""Audit trail writer for AI-assisted advice (EP10-01), reused as a cache (EP10-05)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.models import AiInteraction
from database.enums import AiAssistantFeature

DEFAULT_CACHE_TTL_MINUTES = 5


def find_cached_interaction(
    session: Session,
    *,
    user_id: UUID,
    feature: AiAssistantFeature,
    prompt_key: str,
    input_payload: dict[str, object],
    ttl_minutes: int = DEFAULT_CACHE_TTL_MINUTES,
    now: datetime | None = None,
) -> AiInteraction | None:
    """Return a recent interaction with identical input, if any (avoids recompute)."""
    reference = now or datetime.now(UTC)
    window_start = reference - timedelta(minutes=ttl_minutes)
    rows = session.scalars(
        select(AiInteraction)
        .where(
            AiInteraction.user_id == user_id,
            AiInteraction.feature == feature,
            AiInteraction.prompt_key == prompt_key,
            AiInteraction.created_at >= window_start,
        )
        .order_by(AiInteraction.created_at.desc())
    ).all()
    for row in rows:
        if row.input_json == input_payload:
            return row
    return None


class AiAuditService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        user_id: UUID,
        league_id: UUID | None,
        feature: AiAssistantFeature,
        input_payload: dict[str, object],
        prompt_key: str,
        prompt_version: int,
        model_version: str,
        output_text: str,
        output_payload: dict[str, object] | None = None,
    ) -> AiInteraction:
        interaction = AiInteraction(
            user_id=user_id,
            league_id=league_id,
            feature=feature,
            input_json=input_payload,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            model_version=model_version,
            output_text=output_text,
            output_json=output_payload,
        )
        self._session.add(interaction)
        self._session.flush()
        return interaction
