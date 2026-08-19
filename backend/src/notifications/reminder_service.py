"""Lineup deadline reminders: at-risk-of-missing-cutoff teams (EP09-02).

Reminds every fantasy team that has not yet submitted a lineup for a round
whose cutoff is approaching. Never fires once the round has locked (the
query only ever looks at ``cutoff_at > now``), and is deduplicated per
``(round, team)`` so re-running the periodic task cannot double-send.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user_profile import UserProfile
from database.enums import FantasyTurnStatus, NotificationCategory
from fantasy_lineups.models import LineupSubmission
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.league_membership import LeagueMembership
from notifications.service import NotificationService

DEFAULT_TIMEZONE = "Europe/Rome"


def _format_local(moment: datetime, timezone_name: str | None) -> str:
    try:
        tz = ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return moment.astimezone(tz).strftime("%d/%m/%Y %H:%M")


class LineupReminderService:
    """Sends a single FORMAZIONE reminder per (round, team) before cutoff."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._notifications = NotificationService(session)

    def send_due_reminders(self, *, now: datetime, window_hours: int) -> dict[str, int]:
        window_end = now + timedelta(hours=window_hours)
        rounds = self._session.scalars(
            select(FantasyRound).where(
                FantasyRound.status == FantasyTurnStatus.OPEN,
                FantasyRound.cutoff_at.is_not(None),
                FantasyRound.cutoff_at > now,
                FantasyRound.cutoff_at <= window_end,
            )
        ).all()

        rounds_with_pending = 0
        sent = 0
        for round_ in rounds:
            teams = self._session.execute(
                select(FantasyTeam.id, LeagueMembership.user_id, UserProfile.timezone)
                .join(LeagueMembership, FantasyTeam.membership_id == LeagueMembership.id)
                .outerjoin(UserProfile, UserProfile.user_id == LeagueMembership.user_id)
                .where(FantasyTeam.league_id == round_.league_id)
            ).all()
            if not teams:
                continue

            team_ids = [team_id for team_id, _, _ in teams]
            submitted_team_ids = set(
                self._session.scalars(
                    select(LineupSubmission.fantasy_team_id).where(
                        LineupSubmission.round_id == round_.id,
                        LineupSubmission.fantasy_team_id.in_(team_ids),
                    )
                ).all()
            )

            pending = [row for row in teams if row[0] not in submitted_team_ids]
            if pending:
                rounds_with_pending += 1

            for team_id, user_id, tz_name in pending:
                _, created = self._notifications.create_notification(
                    user_id=user_id,
                    category=NotificationCategory.FORMAZIONE,
                    template_key="formazione.scadenza_turno",
                    template_version=1,
                    params={
                        "round_number": round_.number,
                        "cutoff_local": _format_local(round_.cutoff_at, tz_name),
                    },
                    dedup_key=f"lineup_reminder:{round_.id}:{team_id}",
                )
                if created:
                    sent += 1

        return {
            "rounds_checked": len(rounds),
            "rounds_with_pending_teams": rounds_with_pending,
            "reminders_sent": sent,
        }
