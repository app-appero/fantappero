"""ORM models for entitlements and subscription payments (EP11-01/02)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import SubscriptionPaymentStatus, SubscriptionPlan
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User


class UserEntitlement(Base, TimestampMixin):
    """Current platform plan for a user. One row per user, updated in place."""

    __tablename__ = "user_entitlements"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(
            SubscriptionPlan,
            name="subscription_plan",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'free'"),
    )
    # Null for FREE. For PRO, the plan reverts to FREE server-side once this
    # instant passes — checked on every read (EP11-01 "downgrade sicuro").
    active_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship()


class SubscriptionPayment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One recorded subscription payment event (EP11-02), idempotent by provider event id."""

    __tablename__ = "subscription_payments"
    __table_args__ = (
        UniqueConstraint("external_event_id", name="uq_subscription_payments_external_event_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_code: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    external_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SubscriptionPaymentStatus] = mapped_column(
        Enum(
            SubscriptionPaymentStatus,
            name="subscription_payment_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'completed'"),
    )

    user: Mapped[User] = relationship()
