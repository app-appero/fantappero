"""ORM models — import all mapped classes for Alembic autogenerate."""

from ai_assistant.models import AiInteraction
from auth.models.auth_session import AuthSession
from auth.models.auth_token import AuthToken
from auth.models.privacy_audit_event import PrivacyAuditEvent
from auth.models.user import User
from auth.models.user_profile import UserProfile
from billing.models import SubscriptionPayment, UserEntitlement
from database.models.infrastructure import SystemFlag
from fantasy_lineups.models import LineupDraft, LineupPlayer, LineupSubmission, TacticalMove
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.models import (
    CreditAccount,
    CreditLedgerEntry,
    FantasyRosterSlot,
    FantasyTeam,
    RosterImportSession,
    RosterOwnershipInterval,
    RosterTurnSnapshot,
    RosterTurnSnapshotEntry,
)
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import (
    LeagueCalendar,
    LeagueCalendarRoundWindow,
    LeagueCalendarSlot,
)
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_invite import LeagueInvite
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.league_standing import LeagueStanding
from leagues.models.named_league_invite import NamedLeagueInvite
from market.models import MarketBid, MarketSession, TradeProposal
from notifications.models import Notification, NotificationPreference
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.provider.models import ProviderSnapshot
from sports_data.quality.models import SportsDataQualityIssue, SportsDataSyncRetry
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.scheduler.models import SportsPollRun

__all__ = [
    "AiInteraction",
    "Athlete",
    "AuthSession",
    "AuthToken",
    "Club",
    "Competition",
    "CompetitionSeasonClub",
    "CreditAccount",
    "CreditLedgerEntry",
    "FantasyRosterSlot",
    "FantasyRound",
    "FantasyRoundFixture",
    "FantasyTeam",
    "Fixture",
    "League",
    "LeagueAuditEvent",
    "LeagueCalendar",
    "LeagueCalendarRoundWindow",
    "LeagueCalendarSlot",
    "LeagueCompetition",
    "LeagueInvite",
    "LeagueMembership",
    "LeagueRoleOverride",
    "LeagueRules",
    "LeagueStanding",
    "LineupDraft",
    "LineupPlayer",
    "LineupSubmission",
    "TacticalMove",
    "MarketBid",
    "MarketSession",
    "MatchEvent",
    "NamedLeagueInvite",
    "Notification",
    "NotificationPreference",
    "OfficialLineup",
    "OfficialLineupEntry",
    "PlayerMatchRating",
    "PlayerMatchStat",
    "PrivacyAuditEvent",
    "ProviderSnapshot",
    "RoleAssignment",
    "RosterImportSession",
    "RosterOwnershipInterval",
    "RosterTurnSnapshot",
    "RosterTurnSnapshotEntry",
    "SportsDataQualityIssue",
    "SportsDataSyncRetry",
    "SquadMembership",
    "SportSeason",
    "SportsPollRun",
    "SubscriptionPayment",
    "SystemFlag",
    "TradeProposal",
    "Transfer",
    "User",
    "UserEntitlement",
    "UserProfile",
]
