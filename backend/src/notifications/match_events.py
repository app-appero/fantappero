"""Notifiche live per gol, espulsioni e indisponibilità (EP09-05).

Avvisa solo chi ha il giocatore in rosa (non tutta la lega, sarebbe spam).
Mai bloccante: un errore qui non deve far fallire la sincronizzazione dei
dati partita, che è il lavoro vero. Riusa la categoria ``risultati``.

Se poi un gol o un assist già notificato viene ritirato dalla sincronizzazione (VAR,
fuorigioco), ``notify_match_event_retracted`` manda «Gol annullato» / «Assist annullato»
a chi aveva ricevuto l'originale, una volta sola per evento.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRoundHomologationStatus, NotificationCategory
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from notifications.league_context import league_params
from notifications.matchup_links import resolve_matchup_deep_link
from notifications.models import Notification
from notifications.recipients import user_ids_for_teams
from notifications.service import NotificationService
from observability.logging import get_logger
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

LIVE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"})
FINISHED_STATUSES = frozenset({"FT", "AET", "PEN"})
_GOAL_KINDS = frozenset({"goal", "penalty_scored"})
#: Oltre questo tempo dal calcio d'inizio un gol ritirato non fa più notizia: la correzione
#: tardiva del fornitore (fino a 72 ore) o una riconciliazione di partite vecchie non deve
#: mandare avvisi a distanza di giorni.
RETRACTION_NOTIFY_WINDOW = timedelta(hours=24)


def _owners(session: Session, athlete_id: UUID) -> dict[UUID, UUID]:
    """``fantasy_team_id -> user_id`` di chi ha il giocatore in rosa."""
    team_ids = session.scalars(
        select(FantasyRosterSlot.fantasy_team_id).where(FantasyRosterSlot.athlete_id == athlete_id)
    ).all()
    return dict(user_ids_for_teams(session, team_ids))


def _owners_with_original(
    session: Session, owners: dict[UUID, UUID], original_dedup_prefix: str
) -> dict[UUID, UUID]:
    """I proprietari (squadra -> utente) che hanno davvero ricevuto la notifica originale,
    riconosciuta dal suo codice anti-duplicato ``{prefisso}:{utente}:{squadra}``."""
    if not owners:
        return {}
    keys = {
        f"{original_dedup_prefix}:{user_id}:{team_id}": team_id
        for team_id, user_id in owners.items()
    }
    found = session.scalars(
        select(Notification.dedup_key).where(
            Notification.user_id.in_(set(owners.values())),
            Notification.dedup_key.in_(list(keys)),
        )
    ).all()
    return {keys[key]: owners[keys[key]] for key in found}


def _round_homologated(session: Session, *, team_id: UUID, fixture_id: UUID | None) -> bool:
    """Il turno della lega di ``team_id`` che comprende la partita è già omologato.

    Allora i punti sono definitivi e una correzione passa dal suo percorso
    (``risultati.correzione``), non da un avviso dal vivo."""
    if fixture_id is None:
        return False
    status = session.scalar(
        select(FantasyRound.homologation_status)
        .join(FantasyRoundFixture, FantasyRoundFixture.round_id == FantasyRound.id)
        .join(FantasyTeam, FantasyTeam.league_id == FantasyRoundFixture.league_id)
        .where(
            FantasyTeam.id == team_id,
            FantasyRoundFixture.fixture_id == fixture_id,
            FantasyRoundFixture.excluded_at.is_(None),
        )
    )
    return status == FantasyRoundHomologationStatus.HOMOLOGATED


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
    fixture_id: UUID | None = None,
    deep_link_fallback: str = "/turni",
    original_dedup_prefix: str | None = None,
) -> int:
    """Notifica ogni proprietario, con un deep link allo scontro H2H del
    destinatario (EP09-05 / TASK4): per squadre diverse la stessa fixture può
    cadere in scontri diversi (lega diversa, avversario diverso), quindi il
    link va calcolato per destinatario e non una volta per l'evento.

    Con ``original_dedup_prefix`` (la notifica di annullamento) si avvisa solo chi aveva
    ricevuto l'originale di quell'evento, e non chi ha il turno già omologato."""
    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        return 0
    params = {**params, "player": athlete.canonical_name}
    service = NotificationService(session)
    sent = 0
    owners = _owners(session, athlete_id)
    if original_dedup_prefix is not None:
        owners = _owners_with_original(session, owners, original_dedup_prefix)
        owners = {
            team_id: user_id
            for team_id, user_id in owners.items()
            if not _round_homologated(session, team_id=team_id, fixture_id=fixture_id)
        }
    for team_id, user_id in owners.items():
        team = session.get(FantasyTeam, team_id)
        team_name = getattr(team, "name", None)
        deep_link = resolve_matchup_deep_link(
            session, team_id=team_id, fixture_id=fixture_id, fallback=deep_link_fallback
        )
        team_league_id = getattr(team, "league_id", None)
        recipient_params = {
            **params,
            **({"team_name": team_name} if team_name else {}),
            **(league_params(session, team_league_id) if team_league_id else {}),
            "deep_link": deep_link,
        }
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
    # Serve a risalire, per destinatario, allo scontro H2H preciso (TASK4):
    # senza questo id il deep link resta sulla pagina Turni generica.
    fixture_id = getattr(event, "fixture_id", None)

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
                fixture_id=fixture_id,
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
                    fixture_id=fixture_id,
                )
        elif event_type == "card" and ("red" in detail or "second yellow" in detail):
            sent += _notify_owners(
                session,
                athlete_id=athlete_id,
                template_key="risultati.espulsione",
                template_version=2,
                params=base,
                dedup_prefix=f"match_event:{event_id}",
                fixture_id=fixture_id,
            )
        elif event_type == "card" and "yellow" in detail:
            sent += _notify_owners(
                session,
                athlete_id=athlete_id,
                template_key="risultati.ammonizione",
                template_version=1,
                params=base,
                dedup_prefix=f"match_event:{event_id}",
                fixture_id=fixture_id,
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
            # Chiave stabile per la sostituzione, non per la riga dell'evento (QA 20-21/11):
            # il provider non ha un id dell'evento e la chiave della riga cambia quando
            # corregge minuto o dettaglio («Substitution 2» → «Substitution 3»), creando una
            # riga nuova e un secondo avviso. Un calciatore esce una volta sola per partita,
            # quindi partita + chi esce identificano la sostituzione. La stessa chiave vale
            # per chi esce e per chi entra: chi li ha entrambi in rosa riceve un solo avviso.
            dedup_prefix = (
                f"match_event_subst:{fixture_id}:{athlete_id}"
                if fixture_id is not None
                else f"match_event_subst:{event_id}"
            )
            for owned_id in (athlete_id, related_id):
                if owned_id is None:
                    continue
                sent += _notify_owners(
                    session,
                    athlete_id=owned_id,
                    template_key="risultati.sostituzione",
                    template_version=1,
                    params=params,
                    dedup_prefix=dedup_prefix,
                    fixture_id=fixture_id,
                )
        return sent
    except Exception:
        logger.warning("match_event_notification_failed", exc_info=True)
        return 0


def _recent_enough_for_retraction(fixture: object, now: datetime) -> bool:
    """Partita in corso o finita da poco (``RETRACTION_NOTIFY_WINDOW`` dal calcio d'inizio)."""
    status = getattr(fixture, "status_short", None)
    if status not in LIVE_STATUSES and status not in FINISHED_STATUSES:
        return False
    kickoff = getattr(fixture, "kickoff_at", None)
    if not isinstance(kickoff, datetime):
        return False
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)
    return now - kickoff <= RETRACTION_NOTIFY_WINDOW


def notify_match_event_retracted(
    session: Session,
    *,
    event: object,
    fixture: object,
    reason: str | None = None,
    goal_still_valid: bool = False,
    assist_still_valid: bool = False,
    now: datetime | None = None,
) -> int:
    """Chiamata quando la sincronizzazione ritira un gol già salvato (VAR, fuorigioco, il
    fornitore lo toglie). Manda «Gol annullato» a chi aveva ricevuto «Gol di…» e «Assist
    annullato» a chi aveva ricevuto «Assist di…» di quello stesso gol; ritorna le notifiche
    create.

    Solo per le righe gol/rigore segnato (le righe ``assist`` non hanno notifica propria:
    quella dell'assist è legata al gol). Non manda nulla se la partita non è in corso o
    finita da poco, se il destinatario non aveva ricevuto l'originale (anche perché la
    partita era già finita quando il gol è arrivato) o se il suo turno è già omologato.
    ``goal_still_valid`` / ``assist_still_valid``: lo stesso gol (o assist) c'è ancora con una
    chiave nuova del fornitore, cioè è stato solo corretto (minuto, assist), non annullato.

    Un solo avviso per evento e destinatario (``match_event_retracted:{evento}:{utente}:
    {squadra}``, e ``…_assist``): se il gol torna valido e viene annullato di nuovo, non si
    rimanda. Mai bloccante, come ``notify_match_event``.
    """
    athlete_id = getattr(event, "athlete_id", None)
    event_id = getattr(event, "id", None)
    if (
        athlete_id is None
        or event_id is None
        or getattr(event, "scoring_kind", None) not in _GOAL_KINDS
        or not _recent_enough_for_retraction(fixture, now or datetime.now(UTC))
    ):
        return 0
    related_id = getattr(event, "related_athlete_id", None)
    fixture_id = getattr(event, "fixture_id", None)
    club_name = getattr(getattr(event, "club", None), "name", None)
    base: dict[str, object] = {
        "minute": getattr(event, "minute_elapsed", None),
        **({"club_name": club_name} if isinstance(club_name, str) and club_name else {}),
        **({"reason": reason} if reason else {}),
    }

    try:
        sent = 0
        if not goal_still_valid:
            sent += _notify_owners(
                session,
                athlete_id=athlete_id,
                template_key="risultati.gol_annullato",
                template_version=1,
                params=base,
                dedup_prefix=f"match_event_retracted:{event_id}",
                fixture_id=fixture_id,
                original_dedup_prefix=f"match_event:{event_id}",
            )
        if related_id is not None and not assist_still_valid:
            scorer = session.get(Athlete, athlete_id)
            sent += _notify_owners(
                session,
                athlete_id=related_id,
                template_key="risultati.assist_annullato",
                template_version=1,
                params={**base, "scorer": getattr(scorer, "canonical_name", None)},
                dedup_prefix=f"match_event_retracted_assist:{event_id}",
                fixture_id=fixture_id,
                original_dedup_prefix=f"match_event_assist:{event_id}",
            )
        return sent
    except Exception:
        logger.warning("match_event_retraction_notification_failed", exc_info=True)
        return 0


def notify_availability(session: Session, *, availability: object) -> int:
    """Chiamata alla creazione di una ``PlayerAvailability`` (infortunio/squalifica)."""
    athlete_id = getattr(availability, "athlete_id", None)
    category = getattr(getattr(availability, "category", None), "value", None)
    if athlete_id is None or category not in {"injury", "suspension"}:
        return 0
    template_key = "risultati.infortunio" if category == "injury" else "risultati.squalifica"
    # Se l'indisponibilità è legata a una fixture precisa, punta allo scontro
    # H2H di quella giornata (TASK4); altrimenti resta su «/formazione»
    # (fallback di default dei template v2), che è comunque il posto giusto
    # da cui togliere il giocatore infortunato/squalificato.
    fixture_id = getattr(availability, "fixture_id", None)
    try:
        return _notify_owners(
            session,
            athlete_id=athlete_id,
            template_key=template_key,
            template_version=2,
            params={},
            dedup_prefix=f"availability:{availability.id}",  # type: ignore[attr-defined]
            fixture_id=fixture_id,
            deep_link_fallback="/formazione",
        )
    except Exception:
        logger.warning("availability_notification_failed", exc_info=True)
        return 0
