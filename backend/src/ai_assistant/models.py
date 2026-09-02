"""ORM model for the AI assistant audit trail (EP10-01)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import AiAssistantFeature, AiFeedbackRating
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League


class AiInteraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One AI-assisted suggestion: input, prompt/model version, output, feedback.

    Every advisory feature (EP10-02..04) writes exactly one row per call —
    the technical audit trail required across all EP10 cards. Never records
    or triggers a game action; ``feedback_rating`` is opinion only.
    """

    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_interactions_user_id", "user_id"),
        Index("ix_ai_interactions_league_id", "league_id"),
        Index("ix_ai_interactions_feature", "feature"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    league_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=True,
    )
    feature: Mapped[AiAssistantFeature] = mapped_column(
        Enum(
            AiAssistantFeature,
            name="ai_assistant_feature",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    input_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    prompt_key: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    feedback_rating: Mapped[AiFeedbackRating | None] = mapped_column(
        Enum(
            AiFeedbackRating,
            name="ai_feedback_rating",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    feedback_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship()
    league: Mapped[League | None] = relationship()
