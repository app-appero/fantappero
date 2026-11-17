"""Notifiche di lega e di turno: nuovo membro, lega attivata, turno aperto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import LeagueMemberRole, NotificationCategory
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from notifications.service import NotificationService

# Un turno si notifica solo se il blocco è vicino: la sincronizzazione può aprire mesi di turni
# in un colpo solo e non deve riempire di avvisi.
# "Turno aperto" arriva un giorno prima del blocco reale (calcio d'inizio meno il margine).
TURN_NOTIFY_WINDOW = timedelta(days=1)


def _member_user_ids(session: Session, league_id: UUID) -> list[UUID]:
    return list(
        session.scalars(
            select(LeagueMembership.user_id).where(LeagueMembership.league_id == league_id)
        ).all()
    )


def notify_member_joined(
    session: Session, *, league: League, membership_id: UUID, member_name: str, member_user_id: UUID
) -> None:
    """Avvisa i proprietari che qualcuno è entrato in lega."""
    owner_ids = session.scalars(
        select(LeagueMembership.user_id).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.role == LeagueMemberRole.OWNER,
        )
    ).all()
    service = NotificationService(session)
    for owner_id in owner_ids:
        if owner_id == member_user_id:
            continue
        service.create_notification(
            user_id=owner_id,
            category=NotificationCategory.SISTEMA,
            template_key="lega.nuovo_membro",
            template_version=1,
            params={
                "member_name": member_name,
                "league_name": league.name,
                "league_id": str(league.id),
            },
            dedup_key=f"league_joined:{membership_id}:{owner_id}",
        )


def notify_league_activated(session: Session, *, league: League) -> None:
    """La stagione è partita: avvisa tutti i partecipanti."""
    service = NotificationService(session)
    for user_id in _member_user_ids(session, league.id):
        service.create_notification(
            user_id=user_id,
            category=NotificationCategory.SISTEMA,
            template_key="lega.attivata",
            template_version=1,
            params={"league_name": league.name, "league_id": str(league.id)},
            dedup_key=f"league_activated:{league.id}:{user_id}",
        )


def notify_league_deleted(session: Session, *, league: League) -> None:
    """Un operatore ha eliminato la lega: avvisa tutti i partecipanti."""
    service = NotificationService(session)
    for user_id in _member_user_ids(session, league.id):
        service.create_notification(
            user_id=user_id,
            category=NotificationCategory.SISTEMA,
            template_key="lega.eliminata",
            template_version=1,
            params={"league_name": league.name},
            dedup_key=f"league_deleted:{league.id}:{user_id}",
        )


def notify_turn_opened(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    number: int,
    cutoff_at: datetime | None,
    now: datetime | None = None,
) -> None:
    """Turno aperto: avvisa quando manca al più un giorno al blocco reale.

    Chiamata all'apertura e dal batch orario (``notify_turns_locking_soon``): il dedup
    garantisce un solo avviso per turno e partecipante.
    """
    moment = now or datetime.now(UTC)
    margin = session.scalar(
        select(LeagueRules.lineup_lock_margin_minutes).where(LeagueRules.league_id == league_id)
    )
    lock_at = cutoff_at - timedelta(minutes=margin or 0) if cutoff_at is not None else None
    if lock_at is None or lock_at > moment + TURN_NOTIFY_WINDOW or lock_at <= moment:
        return
    league = session.get(League, league_id)
    if league is None:
        return
    service = NotificationService(session)
    for user_id in _member_user_ids(session, league_id):
        service.create_notification(
            user_id=user_id,
            category=NotificationCategory.FORMAZIONE,
            template_key="turni.aperto",
            template_version=1,
            params={
                "league_name": league.name,
                "league_id": str(league.id),
                "number": number,
                # Il blocco vero arriva prima del calcio d'inizio, del margine scelto dalla lega.
                "cutoff_iso": lock_at.isoformat() if lock_at is not None else None,
            },
            dedup_key=f"turn_opened:{round_id}:{user_id}",
        )


def notify_turns_locking_soon(session: Session, *, now: datetime | None = None) -> int:
    """Batch: avvisa "Turno aperto" per i turni aperti il cui blocco è entro un giorno."""
    from database.enums import FantasyTurnStatus
    from fantasy_turns.models import FantasyRound

    moment = now or datetime.now(UTC)
    # Il margine di lega anticipa il blocco: si guarda un po' oltre e si filtra in notify.
    rounds = session.scalars(
        select(FantasyRound).where(
            FantasyRound.status == FantasyTurnStatus.OPEN,
            FantasyRound.cutoff_at.is_not(None),
            FantasyRound.cutoff_at > moment,
            FantasyRound.cutoff_at <= moment + TURN_NOTIFY_WINDOW + timedelta(days=1),
        )
    ).all()
    for fantasy_round in rounds:
        notify_turn_opened(
            session,
            league_id=fantasy_round.league_id,
            round_id=fantasy_round.id,
            number=fantasy_round.number,
            cutoff_at=fantasy_round.cutoff_at,
            now=moment,
        )
    return len(rounds)
