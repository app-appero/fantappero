"""PostgreSQL-backed enum types."""

from __future__ import annotations

import enum


class FlagScope(str, enum.Enum):
    """Scope for infrastructural feature flags."""

    SYSTEM = "system"
    TENANT = "tenant"


class AuthTokenType(str, enum.Enum):
    """One-time auth token purposes."""

    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class PlatformRole(str, enum.Enum):
    """Platform-wide role for a registered account."""

    USER = "user"
    OPERATOR = "operator"


class UserType(str, enum.Enum):
    """Kind of fantasy coach account."""

    HUMAN = "human"
    AI = "ai"


# Backward-compatible aliases used by auth service imports.
AuthTokenPurpose = AuthTokenType


class GlobalRole(str, enum.Enum):
    """API-facing global role (mapped from PlatformRole)."""

    MEMBER = "member"
    GLOBAL_OPERATOR = "global_operator"


def platform_role_to_global_role(role: PlatformRole) -> GlobalRole:
    if role == PlatformRole.OPERATOR:
        return GlobalRole.GLOBAL_OPERATOR
    return GlobalRole.MEMBER


class LeagueMemberRole(str, enum.Enum):
    """Role stored on ``league_memberships`` (EP02-01 schema)."""

    OWNER = "owner"
    MEMBER = "member"


class LeagueRole(str, enum.Enum):
    """API-facing league role (aligned with ``@fantappero/contracts``)."""

    MEMBER = "member"
    LEAGUE_ADMIN = "league_admin"


class LeagueState(str, enum.Enum):
    """Lifecycle state for a private league (EP03-05)."""

    DRAFT = "draft"
    CONFIGURING = "configuring"
    AUCTION = "auction"
    ACTIVE = "active"
    CONCLUDED = "concluded"
    ARCHIVED = "archived"


class FantasyRole(str, enum.Enum):
    """Official FantApperò listone roles (P–D–C–A)."""

    P = "P"
    D = "D"
    C = "C"
    A = "A"


class LeagueAuditAction(str, enum.Enum):
    """League configuration and membership audit events."""

    LEAGUE_CREATED = "league_created"
    LEAGUE_RULES_UPDATED = "league_rules_updated"
    LEAGUE_INVITE_CREATED = "league_invite_created"
    LEAGUE_INVITE_REVOKED = "league_invite_revoked"
    LEAGUE_MEMBER_JOINED = "league_member_joined"
    LEAGUE_MEMBER_REMOVED = "league_member_removed"
    LEAGUE_ADMIN_TRANSFERRED = "league_admin_transferred"
    LEAGUE_STATE_CHANGED = "league_state_changed"
    NAMED_INVITE_CREATED = "named_invite_created"
    NAMED_INVITE_ACCEPTED = "named_invite_accepted"
    NAMED_INVITE_DECLINED = "named_invite_declined"
    NAMED_INVITE_REVOKED = "named_invite_revoked"
    LEAGUE_CALENDAR_GENERATED = "league_calendar_generated"
    LEAGUE_CALENDAR_CONFIRMED = "league_calendar_confirmed"
    LEAGUE_ROLE_OVERRIDE_SET = "league_role_override_set"
    LEAGUE_ROLE_OVERRIDE_CLEARED = "league_role_override_cleared"
    LEAGUE_LISTONE_REFRESHED = "league_listone_refreshed"
    LEAGUE_DELETED = "league_deleted"
    FANTASY_TEAM_CREATED = "fantasy_team_created"
    FANTASY_ROSTER_SLOT_ASSIGNED = "fantasy_roster_slot_assigned"
    FANTASY_ROSTER_SLOT_RELEASED = "fantasy_roster_slot_released"
    FANTASY_ROSTER_CSV_IMPORTED = "fantasy_roster_csv_imported"
    FANTASY_ROSTER_COMPOSITION_VALIDATED = "fantasy_roster_composition_validated"
    FANTASY_ROSTER_OWNERSHIP_CLOSED = "fantasy_roster_ownership_closed"
    FANTASY_ROSTER_TURN_SNAPSHOT_CREATED = "fantasy_roster_turn_snapshot_created"
    FANTASY_TURN_GENERATED = "fantasy_turn_generated"
    FANTASY_TURN_OPENED = "fantasy_turn_opened"
    FANTASY_TURN_FIXTURE_EXCLUDED = "fantasy_turn_fixture_excluded"
    FANTASY_TURN_CUTOFF_RECALCULATED = "fantasy_turn_cutoff_recalculated"
    FANTASY_LINEUP_SAVED = "fantasy_lineup_saved"
    FANTASY_LINEUP_COPIED = "fantasy_lineup_copied"
    FANTASY_LINEUP_DRAFT_SAVED = "fantasy_lineup_draft_saved"
    FANTASY_TACTICAL_MOVE_APPLIED = "fantasy_tactical_move_applied"
    CREDIT_ACCOUNT_INITIALIZED = "credit_account_initialized"
    CREDIT_LEDGER_ENTRY_POSTED = "credit_ledger_entry_posted"
    FANTASY_ROUND_HOMOLOGATED = "fantasy_round_homologated"
    FANTASY_ROUND_CORRECTION_APPLIED = "fantasy_round_correction_applied"
    MARKET_SESSION_CREATED = "market_session_created"
    MARKET_SESSION_CLOSED = "market_session_closed"
    MARKET_BID_SUBMITTED = "market_bid_submitted"
    MARKET_BID_WITHDRAWN = "market_bid_withdrawn"
    MARKET_SESSION_RESOLVED = "market_session_resolved"
    MARKET_TIEBREAK_OPENED = "market_tiebreak_opened"
    MARKET_TRADE_PROPOSED = "market_trade_proposed"
    MARKET_TRADE_CANCELLED = "market_trade_cancelled"
    MARKET_TRADE_ACCEPTED = "market_trade_accepted"
    MARKET_TRADE_REJECTED = "market_trade_rejected"
    MARKET_TRADE_COUNTERED = "market_trade_countered"
    MARKET_TRADE_APPROVED = "market_trade_approved"
    MARKET_TRADE_REJECTED_BY_ADMIN = "market_trade_rejected_by_admin"


class FantasyTurnStatus(str, enum.Enum):
    """European fantasy turn lifecycle (EP06-01 / FR-TUR-01/02 subset)."""

    SCHEDULED = "scheduled"
    OPEN = "open"
    LOCKED = "locked"
    SKIPPED = "skipped"


class FantasyRoundHomologationStatus(str, enum.Enum):
    """Provisional vs homologated results for a turn (EP07-07 / FR-OMO-01)."""

    PROVISIONAL = "provisional"
    HOMOLOGATED = "homologated"


class FantasyTurnKind(str, enum.Enum):
    """Temporal window kind for european turn generation."""

    WEEKEND = "weekend"
    MIDWEEK = "midweek"


class FantasyRoundFixtureReason(str, enum.Enum):
    """Why a fixture was linked to a fantasy turn."""

    WINDOW = "window"
    ADMIN_INCLUDE = "admin_include"


class FantasyModule(str, enum.Enum):
    """Approved FantApperò modules (EP06-02 / FR-FOR-01)."""

    M343 = "3-4-3"
    M352 = "3-5-2"
    M433 = "4-3-3"
    M442 = "4-4-2"
    M451 = "4-5-1"
    M532 = "5-3-2"
    M541 = "5-4-1"


class LineupSlotKind(str, enum.Enum):
    """Whether a lineup player is a starter or on the bench."""

    STARTER = "starter"
    BENCH = "bench"


class TacticalMoveStatus(str, enum.Enum):
    """Lifecycle of a recorded tactical move (EP06-05 / FR-FOR-02)."""

    APPLIED = "applied"


class RosterImportStatus(str, enum.Enum):
    """Lifecycle of a CSV roster import session (EP05-04)."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"


class RosterCompositionStatus(str, enum.Enum):
    """Roster composition validity (EP05-05 / FR-ROS-02)."""

    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    VALIDATED = "validated"


class RosterOwnershipSource(str, enum.Enum):
    """How a roster ownership interval was opened (EP05-06)."""

    MANUAL = "manual"
    CSV_IMPORT = "csv_import"
    ADMIN = "admin"
    MARKET = "market"


class CreditLedgerReason(str, enum.Enum):
    """Immutable credit ledger causals (EP05-02 / EP05-03)."""

    INITIAL_ALLOCATION = "initial_allocation"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    ROSTER_PURCHASE = "roster_purchase"
    ROSTER_RELEASE_REFUND = "roster_release_refund"
    MARKET_AUCTION_WIN = "market_auction_win"
    MARKET_WAIVER_ACQUISITION = "market_waiver_acquisition"
    MARKET_RELEASE_REFUND = "market_release_refund"
    MARKET_TRADE_CREDITS_SENT = "market_trade_credits_sent"
    MARKET_TRADE_CREDITS_RECEIVED = "market_trade_credits_received"


class LeagueCalendarStatus(str, enum.Enum):
    """Lifecycle of a league H2H calendar (EP03-06)."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"


class LeagueCalendarFormat(str, enum.Enum):
    """Supported H2H calendar formats for the Standard preset."""

    SINGLE_ROUND_ROBIN = "single_round_robin"


class NamedInviteStatus(str, enum.Enum):
    """Lifecycle of an invitation addressed to one user."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PrivacyAuditAction(str, enum.Enum):
    """Privacy-related audit events (EP02-04 / EP11-03)."""

    DATA_EXPORT = "data_export"
    ACCOUNT_DELETE = "account_delete"


class MarketSessionKind(str, enum.Enum):
    """Kind of sealed-bid market window (EP08-01 / FR-AST-01, FR-MKT-01)."""

    INITIAL_AUCTION = "initial_auction"
    WAIVER = "waiver"


class MarketSessionStatus(str, enum.Enum):
    """Lifecycle of a sealed-bid market session window (EP08-01)."""

    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED = "resolved"


class TradeStatus(str, enum.Enum):
    """Trade proposal lifecycle (EP08-05/06/07, Doc §17 'Scambio').

    Only the states written by EP08-05 are defined here; ACCEPTED, REJECTED and
    COUNTERED are added by EP08-06's migration, PENDING_APPROVAL/EXECUTED/
    REJECTED_BY_ADMIN by EP08-07's, each as an ``ALTER TYPE ... ADD VALUE``.
    """

    PROPOSED = "proposed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTERED = "countered"
    PENDING_APPROVAL = "pending_approval"
    EXECUTED = "executed"
    REJECTED_BY_ADMIN = "rejected_by_admin"


class MarketBidStatus(str, enum.Enum):
    """Sealed offer lifecycle, shared by auction and waiver bids (Doc §17 'Offerta mercato')."""

    SUBMITTED = "submitted"
    EXPIRED = "expired"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"


class MarketReleaseReason(str, enum.Enum):
    """Cause of a voluntary roster release, driving the refund percentage (FR-MKT-02)."""

    VOLUNTARY = "voluntary"
    LEAGUE_EXIT = "league_exit"


class NotificationCategory(str, enum.Enum):
    """In-app notification category (EP09-01). Producers land in EP09-02/03/04."""

    SISTEMA = "sistema"
    FORMAZIONE = "formazione"
    MERCATO = "mercato"
    RISULTATI = "risultati"


class NotificationStatus(str, enum.Enum):
    """Outbox delivery lifecycle for a notification (EP09-01)."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class AiAssistantFeature(str, enum.Enum):
    """AI-assisted advisory surfaces (EP10) — advice only, never auto-applied."""

    VICEALLENATORE = "viceallenatore"
    OSSERVATORE = "osservatore"
    ANALISTA = "analista"


class AiFeedbackRating(str, enum.Enum):
    """User feedback on an AI suggestion (EP10-05) — never changes game state."""

    UP = "up"
    DOWN = "down"


class Permission(str, enum.Enum):
    """Fine-grained permissions mirrored from client contracts (EP02-03)."""

    LEAGUE_VIEW = "league:view"
    LEAGUE_ADMIN = "league:admin"
    ROSTER_VIEW = "roster:view"
    ROSTER_EDIT = "roster:edit"
    MARKET_VIEW = "market:view"
    MARKET_MANAGE = "market:manage"
    MATCHDAY_VIEW = "matchday:view"
    PROFILE_VIEW = "profile:view"
    GLOBAL_OPERATE = "global:operate"


def league_member_role_to_league_role(role: LeagueMemberRole) -> LeagueRole:
    if role == LeagueMemberRole.OWNER:
        return LeagueRole.LEAGUE_ADMIN
    return LeagueRole.MEMBER
