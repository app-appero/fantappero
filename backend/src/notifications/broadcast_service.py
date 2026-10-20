"""Avvisi dell'operatore a un pubblico scelto: destinatari, invio, storico (EP09-06)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.enums import NotificationCategory, PlatformRole, UserType
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from notifications.models import Notification, NotificationBroadcast, PushDevice
from notifications.service import NotificationService
from observability.logging import get_logger

logger = get_logger(__name__)

BROADCAST_KINDS = frozenset({"test", "avviso", "novita", "manutenzione"})
# Destinazioni che l'app mobile sa aprire (navigation/notificationDestination.ts).
VALID_DEEP_LINK_PREFIXES = (
    # "/" da solo = home della lega (gestito a parte in validate_deep_link)
    "/inviti",
    "/formazione",
    "/classifica",
    "/turni",
    "/rosa",
    "/asta",
    "/svincolati",
    "/scambi",
    "/mercato",
    "/profilo",
)


class BroadcastError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_deep_link(deep_link: str | None) -> None:
    if deep_link is None:
        return
    path = deep_link.split("?")[0].split("#")[0]
    if path == "/":
        return  # home della lega
    if not path.startswith("/") or path.startswith("//") or "://" in deep_link:
        raise BroadcastError("invalid_deep_link", "Il link deve essere un percorso interno.")
    if not any(path == p or path.startswith(p + "/") for p in VALID_DEEP_LINK_PREFIXES):
        raise BroadcastError(
            "invalid_deep_link",
            "Destinazione non gestita dall'app: " + ", ".join(VALID_DEEP_LINK_PREFIXES),
        )


def _push_ready():
    """Utenti con push attivo: preferenza accesa e almeno un dispositivo non revocato."""
    has_device = exists().where(PushDevice.user_id == User.id, PushDevice.revoked_at.is_(None))
    return and_(UserProfile.notifications_push.is_(True), has_device)


def _human_users():
    return and_(User.deleted_at.is_(None), User.user_type == UserType.HUMAN)


@dataclass(frozen=True)
class RecipientRow:
    user: User
    leagues: list[tuple[UUID, str]]
    push_enabled: bool


def list_recipients(
    session: Session,
    *,
    search: str | None,
    league_id: UUID | None,
    push_only: bool,
    no_push: bool,
    operators_only: bool,
    page: int,
    page_size: int,
) -> tuple[list[RecipientRow], int, dict[str, int]]:
    base = (
        select(User, _push_ready().label("push"))
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(_human_users())
    )
    if search:
        like = f"%{search.strip()}%"
        base = base.where(or_(User.email.ilike(like), UserProfile.display_name.ilike(like)))
    if league_id is not None:
        base = base.where(
            exists().where(
                LeagueMembership.user_id == User.id, LeagueMembership.league_id == league_id
            )
        )

    def _count(extra: list) -> int:
        stmt = select(func.count()).select_from(base.where(*extra).subquery())
        return int(session.scalar(stmt) or 0)

    counts = {
        "all": _count([]),
        "withPush": _count([_push_ready()]),
        "withoutPush": _count([~_push_ready()]),
        "operators": _count([User.platform_role == PlatformRole.OPERATOR]),
    }
    filtered = base
    if push_only:
        filtered = filtered.where(_push_ready())
    if no_push:
        filtered = filtered.where(~_push_ready())
    if operators_only:
        filtered = filtered.where(User.platform_role == PlatformRole.OPERATOR)
    total = int(session.scalar(select(func.count()).select_from(filtered.subquery())) or 0)
    rows = session.execute(
        filtered.options(selectinload(User.profile))
        .order_by(User.email)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    user_ids = [row[0].id for row in rows]
    leagues: dict[UUID, list[tuple[UUID, str]]] = {uid: [] for uid in user_ids}
    if user_ids:
        for uid, lid, name in session.execute(
            select(LeagueMembership.user_id, League.id, League.name)
            .join(League, League.id == LeagueMembership.league_id)
            .where(LeagueMembership.user_id.in_(user_ids))
            .order_by(League.name)
        ).all():
            leagues[uid].append((lid, name))
    items = [RecipientRow(row[0], leagues[row[0].id], bool(row[1])) for row in rows]
    return items, total, counts


def resolve_audience(session: Session, audience: dict[str, object]) -> list[UUID]:
    mode = audience.get("mode")
    stmt = select(User.id).where(_human_users())
    if mode == "leagues":
        league_ids = [UUID(str(x)) for x in audience.get("leagueIds") or []]
        stmt = stmt.where(
            exists().where(
                LeagueMembership.user_id == User.id, LeagueMembership.league_id.in_(league_ids)
            )
        )
    elif mode == "users":
        stmt = stmt.where(User.id.in_([UUID(str(x)) for x in audience.get("userIds") or []]))
    elif mode != "all":
        raise BroadcastError("invalid_audience", "Pubblico non valido.")
    excluded = {UUID(str(x)) for x in audience.get("excludeUserIds") or []}
    return [uid for uid in session.scalars(stmt).all() if uid not in excluded]


def audience_label(session: Session, audience: dict[str, object], count: int) -> str:
    mode = audience.get("mode")
    if mode == "leagues":
        names = session.scalars(
            select(League.name).where(
                League.id.in_([UUID(str(x)) for x in audience.get("leagueIds") or []])
            )
        ).all()
        shown = ", ".join(sorted(names)[:3]) + ("…" if len(names) > 3 else "")
        return f"Leghe: {shown}"[:200]
    if mode == "users":
        return f"{count} utenti scelti"
    return "Tutti gli utenti"


def deliver(session: Session, broadcast: NotificationBroadcast) -> None:
    """Crea le notifiche (in-app e, se scelto, push) e aggiorna i conteggi."""
    recipients = resolve_audience(session, broadcast.audience)
    service = NotificationService(session)
    want_push = bool(broadcast.channels.get("push"))
    for user_id in recipients:
        with session.begin_nested():
            service.create_notification(
                user_id=user_id,
                category=NotificationCategory(broadcast.category),
                template_key="sistema.generico",
                template_version=1,
                params={
                    "title": broadcast.title,
                    "body": broadcast.body,
                    "deep_link": broadcast.deep_link,
                },
                dedup_key=f"broadcast:{broadcast.id}:{user_id}",
                push=want_push,
                email=False,
            )
    broadcast.recipient_count = len(recipients)
    push_count = 0
    if want_push and recipients:
        push_count = int(
            session.scalar(
                select(func.count())
                .select_from(User)
                .outerjoin(UserProfile, UserProfile.user_id == User.id)
                .where(User.id.in_(recipients), _push_ready())
            )
            or 0
        )
    broadcast.push_count = push_count
    broadcast.status = "sent"
    broadcast.sent_at = datetime.now(UTC)
    session.flush()


def create_broadcast(
    session: Session,
    *,
    created_by: UUID,
    kind: str,
    title: str,
    body: str,
    category: str,
    deep_link: str | None,
    channels: dict[str, bool],
    audience: dict[str, object],
    scheduled_at: datetime | None,
) -> NotificationBroadcast:
    if kind not in BROADCAST_KINDS:
        raise BroadcastError("invalid_kind", "Tipo di avviso non valido.")
    if category not in {c.value for c in NotificationCategory}:
        raise BroadcastError("invalid_category", "Categoria non valida.")
    if channels.get("email"):
        raise BroadcastError("email_unavailable", "Invio email non disponibile.")
    validate_deep_link(deep_link)
    recipients = resolve_audience(session, audience)
    if not recipients:
        raise BroadcastError("empty_audience", "Nessun destinatario per questo pubblico.")
    now = datetime.now(UTC)
    later = scheduled_at is not None and scheduled_at > now
    broadcast = NotificationBroadcast(
        kind=kind,
        title=title.strip(),
        body=body.strip(),
        category=category,
        deep_link=deep_link,
        channels={"inApp": True, "push": bool(channels.get("push")), "email": False},
        audience=audience,
        audience_label=audience_label(session, audience, len(recipients)),
        status="scheduled" if later else "sending",
        scheduled_at=scheduled_at if later else None,
        recipient_count=len(recipients),
        created_by_user_id=created_by,
    )
    session.add(broadcast)
    session.flush()
    if not later:
        deliver(session, broadcast)
    return broadcast


def dispatch_due(session: Session, *, now: datetime) -> int:
    """Invia gli avvisi programmati scaduti. Il lock evita doppi invii tra worker."""
    due = session.scalars(
        select(NotificationBroadcast)
        .where(
            NotificationBroadcast.status == "scheduled",
            NotificationBroadcast.scheduled_at <= now,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for broadcast in due:
        broadcast.status = "sending"
        try:
            deliver(session, broadcast)
        except Exception:
            logger.warning("broadcast_delivery_failed", exc_info=True)
            broadcast.status = "scheduled"
    return len(due)


def cancel_scheduled(session: Session, broadcast_id: UUID) -> bool:
    broadcast = session.get(NotificationBroadcast, broadcast_id)
    if broadcast is None or broadcast.status != "scheduled":
        return False
    broadcast.status = "cancelled"
    session.flush()
    return True


def list_history(
    session: Session, *, page: int, page_size: int
) -> tuple[list[tuple[NotificationBroadcast, int, int]], int]:
    visible = NotificationBroadcast.status != "cancelled"
    total = int(
        session.scalar(select(func.count()).select_from(NotificationBroadcast).where(visible))
        or 0
    )
    when = func.coalesce(NotificationBroadcast.sent_at, NotificationBroadcast.scheduled_at)
    rows = session.scalars(
        select(NotificationBroadcast)
        .where(visible)
        .order_by(when.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    out: list[tuple[NotificationBroadcast, int, int]] = []
    for row in rows:
        delivered, read = session.execute(
            select(func.count(), func.count(Notification.read_at)).where(
                Notification.dedup_key.like(f"broadcast:{row.id}:%")
            )
        ).one()
        out.append((row, int(delivered), int(read)))
    return out, total
