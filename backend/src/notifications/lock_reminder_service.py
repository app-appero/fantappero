"""Avvisi per ogni prossimo istante di blocco formazione (EP-turni-automazione).

Diverso da ``LineupReminderService`` (un unico avviso per turno: "salva
prima che il turno chiuda", legato a ``round.cutoff_at``). Qui si avvisa
per **ogni** prossimo istante in cui scatta il lock progressivo
per-calciatore — lo stesso calcolo del countdown "Prossimo blocco" mostrato
in UI (``FantasyLineupService.get_lock_countdown`` /
``fantasy_lineups.rules.next_unlocked_kickoff``) — perché un turno con più
fixture a orari diversi ha più istanti di blocco in sequenza, ciascuno dei
quali può bloccare da 1 a N calciatori della rosa (chi gioca in quel
preciso kickoff, o in kickoff simultanei).

Deduplicato per ``(round, team, istante di blocco)``: lo stesso istante non
genera mai un secondo avviso; un istante successivo (prossimo blocco del
turno) ne genera uno nuovo quando entra nella finestra di preavviso.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user_profile import UserProfile
from database.enums import FantasyTurnStatus, NotificationCategory
from fantasy_lineups.kickoffs import athlete_kickoffs
from fantasy_lineups.rules import DEFAULT_LINEUP_LOCK_MARGIN_MINUTES, next_unlocked_kickoff
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from notifications.reminder_service import _format_local
from notifications.service import NotificationService


class LineupLockReminderService:
    """Manda un avviso FORMAZIONE per ogni prossimo istante di blocco in arrivo."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._notifications = NotificationService(session)

    def send_due_reminders(self, *, now: datetime, window_minutes: int) -> dict[str, int]:
        rounds = self._session.scalars(
            select(FantasyRound).where(FantasyRound.status == FantasyTurnStatus.OPEN)
        ).all()

        teams_checked = 0
        reminders_sent = 0
        for round_ in rounds:
            league = self._session.get(League, round_.league_id)
            if league is None:
                continue
            margin = self._lock_margin(round_.league_id)
            teams = self._session.execute(
                select(FantasyTeam.id, LeagueMembership.user_id, UserProfile.timezone)
                .join(LeagueMembership, FantasyTeam.membership_id == LeagueMembership.id)
                .outerjoin(UserProfile, UserProfile.user_id == LeagueMembership.user_id)
                .where(FantasyTeam.league_id == round_.league_id)
            ).all()

            for team_id, user_id, tz_name in teams:
                roster_ids = list(
                    self._session.scalars(
                        select(FantasyRosterSlot.athlete_id).where(
                            FantasyRosterSlot.fantasy_team_id == team_id,
                            FantasyRosterSlot.athlete_id.is_not(None),
                        )
                    )
                )
                if not roster_ids:
                    continue
                teams_checked += 1

                kickoffs = athlete_kickoffs(
                    self._session,
                    round_id=round_.id,
                    season_year=league.season_year,
                    athlete_ids=roster_ids,
                )
                if not kickoffs:
                    continue
                next_lock = next_unlocked_kickoff(
                    (
                        (ref.kickoff_at, ref.status_short, ref.lock_latched)
                        for ref in kickoffs.values()
                    ),
                    now=now,
                    margin_minutes=margin,
                )
                if next_lock is None:
                    continue
                # L'istante di blocco vero è anticipato dal margine di lega
                # rispetto al kickoff (stessa soglia di
                # `is_athlete_kickoff_locked`): avvisare quando SI avvicina
                # quello, non il fischio d'inizio.
                lock_instant = next_lock - timedelta(minutes=margin)
                if lock_instant > now + timedelta(minutes=window_minutes):
                    continue

                player_count = sum(
                    1 for ref in kickoffs.values() if ref.kickoff_at == next_lock
                )
                if player_count == 0:
                    continue

                _, created = self._notifications.create_notification(
                    user_id=user_id,
                    category=NotificationCategory.FORMAZIONE,
                    template_key="formazione.blocco_imminente",
                    template_version=1,
                    params={
                        "round_number": round_.number,
                        "kickoff_local": _format_local(next_lock, tz_name),
                        "player_count": player_count,
                    },
                    dedup_key=f"lineup_lock_reminder:{round_.id}:{team_id}:{next_lock.isoformat()}",
                )
                if created:
                    reminders_sent += 1

        return {
            "rounds_checked": len(rounds),
            "teams_checked": teams_checked,
            "reminders_sent": reminders_sent,
        }

    def _lock_margin(self, league_id: UUID) -> int:
        margin = self._session.execute(
            select(LeagueRules.lineup_lock_margin_minutes).where(
                LeagueRules.league_id == league_id
            )
        ).scalar_one_or_none()
        return margin if margin is not None else DEFAULT_LINEUP_LOCK_MARGIN_MINUTES


__all__ = ["LineupLockReminderService"]
