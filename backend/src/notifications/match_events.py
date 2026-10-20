"""Notifiche live per gol, espulsioni e indisponibilità (EP09-05).

Avvisa solo chi ha il giocatore in rosa (non tutta la lega, sarebbe spam).
Mai bloccante: un errore qui non deve far fallire la sincronizzazione dei
dati partita, che è il lavoro vero. Riusa la categoria ``risultati``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import NotificationCategory
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from notifications.recipients import user_ids_for_teams
from notifications.service import NotificationService
from observability.logging import get_logger
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

LIVE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"})
_GOAL_KINDS = frozenset({"goal", "penalty_scored"})


def _owners(session: Session, athlete_id: UUID) -> dict[UUID, UUID]:
    """``fantasy_team_id -> user_id`` di chi ha il giocatore in rosa."""
    team_ids = session.scalars(
        select(FantasyRosterSlot.fantasy_team_id).where(FantasyRosterSlot.athlete_id == athlete_id)
    ).all()
    return dict(user_ids_for_teams(session, team_ids))


def _fixture_context(event: object) -> dict[str, object]:
    """Squadre e risultato della partita, se disponibili (mai bloccante)."""
    fixture = getattr(event, "fixture", None)
    if fixture is None:
        return {}
    context: dict[str, object] = {}
    home = getattr(getattr(fixture, "home_club", None), "name", None)
    away = getattr(getattr(fixture, "away_club", None), "name", None)
    if isinstance(home, str) and isinstance(away, str):
        context["fixture_label"] = f"{home}–{away}"
    home_goals = getattr(fixture, "home_goals", None)
    away_goals = getattr(fixture, "away_goals", None)
    if isinstance(home_goals, int) and isinstance(away_goals, int):
        context["score_label"] = f"{home_goals}–{away_goals}"
    return context


def _notify_owners(
    session: Session,
    *,
    athlete_id: UUID,
    template_key: str,
    params: dict[str, object],
    dedup_prefix: str,
    template_version: int = 1,
) -> int:
    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        return 0
    params = {**params, "player": athlete.canonical_name}
    service = NotificationService(session)
    sent = 0
    for team_id, user_id in _owners(session, athlete_id).items():
        team = session.get(FantasyTeam, team_id)
        team_name = getattr(team, "name", None)
        recipient_params = {**params, **({"team_name": team_name} if team_name else {})}
        with session.begin_nested():
            _, created = service.create_notification(
                user_id=user_id,
                category=NotificationCategory.RISULTATI,
                template_key=template_key,
                template_version=template_version,
                params=recipient_params,
                dedup_key=f"{dedup_prefix}:{user_id}:{team_id}",
            )
        sent += 1 if created else 0
    return sent


def notify_match_event(session: Session, *, event: object, fixture_status: str | None) -> int:
    """Chiamata alla creazione di un ``MatchEvent``. Ritorna le notifiche create."""
    athlete_id = getattr(event, "athlete_id", None)
    if athlete_id is None or fixture_status not in LIVE_STATUSES:
        return 0
    scoring_kind = getattr(event, "scoring_kind", None)
    event_type = (getattr(event, "event_type", "") or "").lower()
    detail = (getattr(event, "event_detail", "") or "").lower()
    minute = getattr(event, "minute_elapsed", None)
    base: dict[str, object] = {"minute": minute, **_fixture_context(event)}
    event_id = getattr(event, "id", None)
    related_id = getattr(event, "related_athlete_id", None)

    try:
        sent = 0
        if scoring_kind in _GOAL_KINDS:
            sent += _notify_owners(
                session,
                athlete_id=athlete_id,
                template_key="risultati.gol",
                template_version=2,
                params=base,
                dedup_prefix=f"match_event:{event_id}",
            )
            if related_id is not None:
                scorer = session.get(Athlete, athlete_id)
                sent += _notify_owners(
                    session,
                    athlete_id=related_id,
                    template_key="risultati.assist",
                    template_version=1,
                    params={**base, "scorer": getattr(scorer, "canonical_name", None)},
                    dedup_prefix=f"match_event_assist:{event_id}",
                )
        elif event_type == "card" and ("red" in detail or "second yellow" in detail):
            sent += _notify_owners(
                session,
                athlete_id=athlete_id,
                template_key="risultati.espulsione",
                template_version=2,
                params=base,
                dedup_prefix=f"match_event:{event_id}",
            )
        elif event_type == "card" and "yellow" in detail:
            sent += _notify_owners(
                session,
                athlete_id=athlete_id,
                template_key="risultati.ammonizione",
                template_version=1,
                params=base,
                dedup_prefix=f"match_event:{event_id}",
            )
        elif event_type == "subst":
            # Il provider indica in «player» chi esce e in «assist» chi entra.
            entering = session.get(Athlete, related_id) if related_id is not None else None
            leaving = session.get(Athlete, athlete_id)
            params = {
                **base,
                "player_out": getattr(leaving, "canonical_name", None),
                "player_in": getattr(entering, "canonical_name", None),
            }
            for owned_id in (athlete_id, related_id):
                if owned_id is None:
                    continue
                sent += _notify_owners(
                    session,
                    athlete_id=owned_id,
                    template_key="risultati.sostituzione",
                    template_version=1,
                    params=params,
                    dedup_prefix=f"match_event_subst:{event_id}:{owned_id}",
                )
        return sent
    except Exception:
        logger.warning("match_event_notification_failed", exc_info=True)
        return 0


def notify_availability(session: Session, *, availability: object) -> int:
    """Chiamata alla creazione di una ``PlayerAvailability`` (infortunio/squalifica)."""
    athlete_id = getattr(availability, "athlete_id", None)
    category = getattr(getattr(availability, "category", None), "value", None)
    if athlete_id is None or category not in {"injury", "suspension"}:
        return 0
    template_key = "risultati.infortunio" if category == "injury" else "risultati.squalifica"
    try:
        return _notify_owners(
            session,
            athlete_id=athlete_id,
            template_key=template_key,
            template_version=2,
            params={},
            dedup_prefix=f"availability:{availability.id}",  # type: ignore[attr-defined]
        )
    except Exception:
        logger.warning("availability_notification_failed", exc_info=True)
        return 0
