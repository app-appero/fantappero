"""ORM models — import all mapped classes for Alembic autogenerate."""

from auth.models.auth_session import AuthSession
from auth.models.auth_token import AuthToken
from auth.models.privacy_audit_event import PrivacyAuditEvent
from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.models.infrastructure import SystemFlag
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_invite import LeagueInvite
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.named_league_invite import NamedLeagueInvite
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
    "Athlete",
    "AuthSession",
    "AuthToken",
    "Club",
    "Competition",
    "CompetitionSeasonClub",
    "Fixture",
    "League",
    "LeagueAuditEvent",
    "LeagueCalendar",
    "LeagueCalendarSlot",
    "LeagueCompetition",
    "LeagueInvite",
    "LeagueMembership",
    "LeagueRoleOverride",
    "LeagueRules",
    "MatchEvent",
    "NamedLeagueInvite",
    "OfficialLineup",
    "OfficialLineupEntry",
    "PlayerMatchStat",
    "PrivacyAuditEvent",
    "ProviderSnapshot",
    "RoleAssignment",
    "SportsDataQualityIssue",
    "SportsDataSyncRetry",
    "SquadMembership",
    "SportSeason",
    "SportsPollRun",
    "SystemFlag",
    "Transfer",
    "User",
    "UserProfile",
]
