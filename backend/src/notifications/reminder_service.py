"""Lineup deadline reminders: at-risk-of-missing-cutoff teams (EP09-02).

Reminds every fantasy team that has not yet submitted a lineup for a round
whose cutoff is approaching, or whose lineup has lost a starter since (a player
who left the roster is removed and leaves an empty slot, see
``fantasy_lineups.departures``). Never fires once the round has locked (the
query only ever looks at ``cutoff_at > now``), and is deduplicated per
``(round, team)`` so re-running the periodic task cannot double-send.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.models.user_profile import UserProfile
from database.enums import FantasyTurnStatus, LineupSlotKind, NotificationCategory
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.rules import STARTER_COUNT
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.league_membership import LeagueMembership
from notifications.league_context import league_params
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
            # Una formazione a cui manca un titolare (chi è uscito dalla rosa viene tolto e il
            # suo posto resta vuoto, fantasy_lineups.departures) non è schierata: va ricordata
            # come una formazione mancante. Una formazione senza nessun giocatore conta come
            # prima (es. quella vuota creata a fine turno).
            starters = func.count(LineupPlayer.id).filter(
                LineupPlayer.slot_kind == LineupSlotKind.STARTER
            )
            submitted_team_ids = {
                team_id
                for team_id, starter_count, player_count in self._session.execute(
                    select(
                        LineupSubmission.fantasy_team_id,
                        starters,
                        func.count(LineupPlayer.id),
                    )
                    .outerjoin(LineupPlayer, LineupPlayer.submission_id == LineupSubmission.id)
                    .where(
                        LineupSubmission.round_id == round_.id,
                        LineupSubmission.fantasy_team_id.in_(team_ids),
                    )
                    .group_by(LineupSubmission.fantasy_team_id)
                ).all()
                if player_count == 0 or starter_count >= STARTER_COUNT
            }

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
                        **league_params(self._session, round_.league_id),
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
