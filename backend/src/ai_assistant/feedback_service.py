"""User feedback on an AI suggestion (EP10-05) — opinion only, never a game action."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from ai_assistant.exceptions import AiInteractionNotFoundError
from ai_assistant.models import AiInteraction
from database.enums import AiFeedbackRating


def record_feedback(
    session: Session,
    *,
    user_id: UUID,
    interaction_id: UUID,
    rating: AiFeedbackRating,
) -> AiInteraction:
    interaction = session.get(AiInteraction, interaction_id)
    if interaction is None or interaction.user_id != user_id:
        raise AiInteractionNotFoundError()
    interaction.feedback_rating = rating
    interaction.feedback_at = datetime.now(UTC)
    session.commit()
    return interaction
