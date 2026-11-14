"""Notifiche di lega e di turno: nuovo membro, lega attivata, turno aperto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import LeagueMemberRole, NotificationCategory
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from notifications.service import NotificationService

# Un turno si notifica solo se il blocco è vicino: la sincronizzazione può aprire mesi di turni
# in un colpo solo e non deve riempire di avvisi.
TURN_NOTIFY_WINDOW = timedelta(days=10)


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


def notify_turn_opened(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    number: int,
    cutoff_at: datetime | None,
    now: datetime | None = None,
) -> None:
    """Un turno si è aperto: ci si può schierare la formazione (solo se il blocco è vicino)."""
    moment = now or datetime.now(UTC)
    if cutoff_at is not None and cutoff_at > moment + TURN_NOTIFY_WINDOW:
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
                "cutoff_iso": cutoff_at.isoformat() if cutoff_at is not None else None,
            },
            dedup_key=f"turn_opened:{round_id}:{user_id}",
        )
