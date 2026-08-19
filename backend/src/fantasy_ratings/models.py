"""ORM: voto statistico persistito con formula, input e componenti (EP07-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import FantasyRole

if TYPE_CHECKING:
    from sports_data.fixtures.models import Fixture
    from sports_data.roster.models import Athlete


class PlayerMatchRating(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Voto statistico per calciatore-partita, ricostruibile da snapshot."""

    __tablename__ = "player_match_ratings"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "athlete_provider_id",
            "formula_version",
            name="uq_player_match_ratings_fixture_athlete_formula",
        ),
        CheckConstraint(
            "raw >= 3 AND raw <= 10",
            name="ck_player_match_ratings_raw_range",
        ),
        CheckConstraint(
            "display IS NULL OR (display >= 3 AND display <= 10)",
            name="ck_player_match_ratings_display_range",
        ),
    )

    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    athlete_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    role: Mapped[FantasyRole | None] = mapped_column(
        Enum(
            FantasyRole,
            name="fantasy_role",
            native_enum=True,
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    eligibility_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    base: Mapped[float] = mapped_column(Float, nullable=False)
    raw_before_clamp: Mapped[float] = mapped_column(Float, nullable=False)
    raw: Mapped[float] = mapped_column(Float, nullable=False)
    display: Mapped[float | None] = mapped_column(Float, nullable=True)
    stats_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    input_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    components_json: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    bonus_config_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bonus_malus_json: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    bonus_malus_total: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0"),
    )
    fantasy_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    fixture: Mapped[Fixture] = relationship()
    athlete: Mapped[Athlete | None] = relationship()
