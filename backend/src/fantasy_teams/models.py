"""ORM models for fantasy teams, roster slots and credit ledger (EP05-01/02/06)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import (
    CreditLedgerReason,
    RosterCompositionStatus,
    RosterImportStatus,
    RosterOwnershipSource,
)
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League
    from leagues.models.league_membership import LeagueMembership
    from sports_data.roster.models import Athlete


class FantasyTeam(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One fantasy squad per league membership."""

    __tablename__ = "fantasy_teams"
    __table_args__ = (
        UniqueConstraint("membership_id", name="uq_fantasy_teams_membership_id"),
        UniqueConstraint(
            "league_id",
            "membership_id",
            name="uq_fantasy_teams_league_id_membership_id",
        ),
        Index("ix_fantasy_teams_league_id", "league_id"),
        Index("ix_fantasy_teams_composition_status", "composition_status"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("league_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    composition_status: Mapped[RosterCompositionStatus] = mapped_column(
        Enum(
            RosterCompositionStatus,
            name="roster_composition_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'incomplete'"),
    )
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    league: Mapped[League] = relationship()
    membership: Mapped[LeagueMembership] = relationship()
    slots: Mapped[list[FantasyRosterSlot]] = relationship(
        back_populates="fantasy_team",
        cascade="all, delete-orphan",
        order_by="FantasyRosterSlot.slot_index",
    )
    credit_account: Mapped[CreditAccount | None] = relationship(
        back_populates="fantasy_team",
        cascade="all, delete-orphan",
        uselist=False,
    )


class FantasyRosterSlot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Fixed roster slot; exclusivity is league-scoped on assigned athletes."""

    __tablename__ = "fantasy_roster_slots"
    __table_args__ = (
        UniqueConstraint(
            "fantasy_team_id",
            "slot_index",
            name="uq_fantasy_roster_slots_team_slot",
        ),
        Index("ix_fantasy_roster_slots_fantasy_team_id", "fantasy_team_id"),
        Index("ix_fantasy_roster_slots_league_id", "league_id"),
        Index(
            "uq_fantasy_roster_slots_league_athlete",
            "league_id",
            "athlete_id",
            unique=True,
            postgresql_where=text("athlete_id IS NOT NULL"),
        ),
        CheckConstraint("slot_index >= 0", name="ck_fantasy_roster_slots_slot_index"),
        CheckConstraint(
            "purchase_credits IS NULL OR purchase_credits >= 0",
            name="ck_fantasy_roster_slots_purchase_credits",
        ),
    )

    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    purchase_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    fantasy_team: Mapped[FantasyTeam] = relationship(back_populates="slots")
    athlete: Mapped[Athlete | None] = relationship()


class CreditAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Mutable credit balance for a fantasy team; updates only via ledger (EP05-02)."""

    __tablename__ = "credit_accounts"
    __table_args__ = (
        UniqueConstraint("fantasy_team_id", name="uq_credit_accounts_fantasy_team_id"),
        CheckConstraint("balance >= 0", name="ck_credit_accounts_balance"),
        CheckConstraint("version >= 0", name="ck_credit_accounts_version"),
    )

    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    fantasy_team: Mapped[FantasyTeam] = relationship(back_populates="credit_account")
    ledger_entries: Mapped[list[CreditLedgerEntry]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="CreditLedgerEntry.created_at",
    )


class CreditLedgerEntry(Base, UUIDPrimaryKeyMixin):
    """Append-only credit movement with causal (EP05-02)."""

    __tablename__ = "credit_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "transaction_id",
            name="uq_credit_ledger_entries_account_transaction",
        ),
        Index("ix_credit_ledger_entries_account_id", "account_id"),
        Index("ix_credit_ledger_entries_created_at", "created_at"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[CreditLedgerReason] = mapped_column(
        Enum(
            CreditLedgerReason,
            name="credit_ledger_reason",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )

    account: Mapped[CreditAccount] = relationship(back_populates="ledger_entries")
    actor: Mapped[User | None] = relationship()


class RosterImportSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Draft/confirmed CSV import session; preview never mutates roster (EP05-04)."""

    __tablename__ = "roster_import_sessions"
    __table_args__ = (
        Index("ix_roster_import_sessions_league_id", "league_id"),
        Index("ix_roster_import_sessions_status", "status"),
        CheckConstraint("row_count >= 0", name="ck_roster_import_sessions_row_count"),
        CheckConstraint("error_count >= 0", name="ck_roster_import_sessions_error_count"),
        CheckConstraint("warning_count >= 0", name="ck_roster_import_sessions_warning_count"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[RosterImportStatus] = mapped_column(
        Enum(
            RosterImportStatus,
            name="roster_import_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'draft'"),
    )
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preview_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    league: Mapped[League] = relationship()
    actor: Mapped[User | None] = relationship()


class RosterOwnershipInterval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only athlete possession interval for historical reconstruction (EP05-06)."""

    __tablename__ = "roster_ownership_intervals"
    __table_args__ = (
        Index("ix_roster_ownership_intervals_league_id", "league_id"),
        Index("ix_roster_ownership_intervals_fantasy_team_id", "fantasy_team_id"),
        Index("ix_roster_ownership_intervals_athlete_id", "athlete_id"),
        Index("ix_roster_ownership_intervals_acquired_at", "acquired_at"),
        Index(
            "uq_roster_ownership_intervals_active_athlete",
            "league_id",
            "athlete_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
        Index(
            "uq_roster_ownership_intervals_active_slot",
            "fantasy_team_id",
            "slot_index",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
        CheckConstraint("slot_index >= 0", name="ck_roster_ownership_intervals_slot_index"),
        CheckConstraint(
            "purchase_credits >= 0",
            name="ck_roster_ownership_intervals_purchase_credits",
        ),
        CheckConstraint(
            "released_at IS NULL OR released_at >= acquired_at",
            name="ck_roster_ownership_intervals_release_order",
        ),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )
    released_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source: Mapped[RosterOwnershipSource] = mapped_column(
        Enum(
            RosterOwnershipSource,
            name="roster_ownership_source",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'manual'"),
    )

    fantasy_team: Mapped[FantasyTeam] = relationship()
    athlete: Mapped[Athlete] = relationship()


class RosterTurnSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable league-wide roster snapshot for a fantasy round number (EP05-06)."""

    __tablename__ = "roster_turn_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "round_number",
            name="uq_roster_turn_snapshots_league_round",
        ),
        Index("ix_roster_turn_snapshots_league_id", "league_id"),
        CheckConstraint("round_number >= 1", name="ck_roster_turn_snapshots_round_number"),
        CheckConstraint("entry_count >= 0", name="ck_roster_turn_snapshots_entry_count"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    league: Mapped[League] = relationship()
    actor: Mapped[User | None] = relationship()
    entries: Mapped[list[RosterTurnSnapshotEntry]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="RosterTurnSnapshotEntry.fantasy_team_id, RosterTurnSnapshotEntry.slot_index",
    )


class RosterTurnSnapshotEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One filled roster slot captured inside a turn snapshot (EP05-06)."""

    __tablename__ = "roster_turn_snapshot_entries"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "fantasy_team_id",
            "slot_index",
            name="uq_roster_turn_snapshot_entries_snapshot_team_slot",
        ),
        Index("ix_roster_turn_snapshot_entries_snapshot_id", "snapshot_id"),
        Index("ix_roster_turn_snapshot_entries_fantasy_team_id", "fantasy_team_id"),
        Index("ix_roster_turn_snapshot_entries_athlete_id", "athlete_id"),
        CheckConstraint("slot_index >= 0", name="ck_roster_turn_snapshot_entries_slot_index"),
        CheckConstraint(
            "purchase_credits >= 0",
            name="ck_roster_turn_snapshot_entries_purchase_credits",
        ),
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("roster_turn_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str | None] = mapped_column(String(1), nullable=True)

    snapshot: Mapped[RosterTurnSnapshot] = relationship(back_populates="entries")
    fantasy_team: Mapped[FantasyTeam] = relationship()
    athlete: Mapped[Athlete] = relationship()
