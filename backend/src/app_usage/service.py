"""Chi ha quale versione dell'app e notifica di una nuova versione (release 1.4, Rosario 23/11).

- ``build_app_usage_report``: l'elenco del pannello operatore («Versione app»), versione per
  versione, poi le versioni non note, chi usa solo il sito da Android e chi non ha mai usato
  l'app.
- ``app_usage_summary``: la riga del Riepilogo («4 utenti aggiornati su 12 che usano l'app»).
- ``notify_new_app_version``: all'annuncio di una versione, una notifica (nell'elenco e push) a
  chi usa l'app Android o il sito da Android e non risulta già su quella versione o una più
  nuova; una sola volta per versionCode.
- ``notify_app_version_on_sighting``: la stessa notifica a chi compare su Android dopo
  l'annuncio (Rosario 24/11), quando il server registra il suo uso; sempre una sola volta per
  utente e versionCode.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from admin.schemas import (
    AdminAppUsageGroupResponse,
    AdminAppUsageResponse,
    AdminAppUsageSummaryResponse,
    AdminAppUsageUserResponse,
    AndroidAppVersionResponse,
)
from app_usage.models import (
    ANDROID_NOTIFY_PLATFORMS,
    APP_PLATFORMS,
    PLATFORM_ANDROID,
    PLATFORM_WEB_ANDROID,
    SOURCE_HEADER,
    SOURCE_VERSION_CHECK,
    UserAppUsage,
)
from auth.models.user import User
from auth.tester_access import TesterAccess
from database.enums import NotificationCategory, PlatformRole, UserType
from notifications.models import Notification
from notifications.service import NotificationService
from observability.logging import get_logger

#: Notifica della nuova versione (``notifications/templates.py``, evento ``sistema.versione_app``).
APP_VERSION_TEMPLATE_KEY = "sistema.versione_app"

_logger = get_logger(__name__)


def _active_humans():
    return and_(User.deleted_at.is_(None), User.user_type == UserType.HUMAN)


def _up_to_date(latest_code: int):
    """L'utente ha (su Android) la versione annunciata o una più nuova, per versione esatta."""
    return exists().where(
        UserAppUsage.user_id == User.id,
        UserAppUsage.platform == PLATFORM_ANDROID,
        UserAppUsage.source == SOURCE_HEADER,
        UserAppUsage.version_code >= latest_code,
    )


def _uses_android():
    """L'utente usa l'app Android (qualsiasi versione, anche non nota) o il sito da Android."""
    return exists().where(
        UserAppUsage.user_id == User.id,
        UserAppUsage.platform.in_(ANDROID_NOTIFY_PLATFORMS),
    )


def app_usage_summary(
    session: Session, announced: AndroidAppVersionResponse | None
) -> AdminAppUsageSummaryResponse | None:
    if announced is None:
        return None
    # Chi usa l'app: il sito da Android non conta.
    app_users = session.scalar(
        select(func.count(func.distinct(UserAppUsage.user_id)))
        .join(User, User.id == UserAppUsage.user_id)
        .where(_active_humans(), UserAppUsage.platform.in_(APP_PLATFORMS))
    )
    up_to_date = session.scalar(
        select(func.count(User.id)).where(
            _active_humans(), _up_to_date(announced.latest_version_code)
        )
    )
    return AdminAppUsageSummaryResponse(
        upToDateUsers=int(up_to_date or 0), appUsers=int(app_users or 0)
    )


def _user_item(user: User, usage: UserAppUsage | None) -> AdminAppUsageUserResponse:
    display_name = user.display_name
    profile_name = user.profile.display_name if user.profile is not None else None
    return AdminAppUsageUserResponse(
        userId=str(user.id),
        displayName=display_name,
        name=profile_name if profile_name and profile_name != display_name else None,
        email=user.email,
        firstSeenAt=usage.first_seen_at if usage is not None else None,
        lastSeenAt=usage.last_seen_at if usage is not None else None,
    )


def _sorted_by_last_seen(
    items: Iterable[tuple[User, UserAppUsage]],
) -> list[AdminAppUsageUserResponse]:
    rows = sorted(items, key=lambda pair: (-pair[1].last_seen_at.timestamp(), pair[0].email))
    return [_user_item(user, usage) for user, usage in rows]


def build_app_usage_report(
    session: Session, *, announced: AndroidAppVersionResponse | None, now: datetime
) -> AdminAppUsageResponse:
    users = list(
        session.scalars(
            select(User).options(selectinload(User.profile)).where(_active_humans())
        ).all()
    )
    by_id = {user.id: user for user in users}
    usages = (
        [
            usage
            for usage in session.scalars(
                select(UserAppUsage).where(UserAppUsage.user_id.in_(list(by_id)))
            ).all()
            if usage.user_id in by_id
        ]
        if by_id
        else []
    )

    latest_code = announced.latest_version_code if announced is not None else None
    versions: dict[tuple[str, int, str | None], list[tuple[User, UserAppUsage]]] = {}
    unknown_recent: list[tuple[User, UserAppUsage]] = []
    unknown: list[tuple[User, UserAppUsage]] = []
    web_android: dict[UUID, UserAppUsage] = {}
    seen: set[UUID] = set()
    for usage in usages:
        user = by_id[usage.user_id]
        if usage.platform == PLATFORM_WEB_ANDROID:
            # Il sito da Android: un gruppo a parte, solo per chi non ha mai usato l'app.
            web_android[user.id] = usage
            continue
        seen.add(user.id)
        if usage.source == SOURCE_HEADER and usage.version_code is not None:
            key = (usage.platform, usage.version_code, usage.version_name)
            versions.setdefault(key, []).append((user, usage))
        elif usage.source == SOURCE_VERSION_CHECK:
            unknown_recent.append((user, usage))
        else:
            unknown.append((user, usage))

    groups: list[AdminAppUsageGroupResponse] = []

    def _version_order(key: tuple[str, int, str | None]) -> tuple[bool, str, int, str]:
        platform, code, name = key
        return (platform != PLATFORM_ANDROID, platform, -code, name or "")

    # Prima Android, poi le versioni più nuove (versionCode più alto in cima).
    for (platform, code, name), members in sorted(
        versions.items(), key=lambda item: _version_order(item[0])
    ):
        groups.append(
            AdminAppUsageGroupResponse(
                kind="version",
                platform=platform,
                versionName=name,
                versionCode=code,
                upToDate=latest_code is not None
                and platform == PLATFORM_ANDROID
                and code >= latest_code,
                users=_sorted_by_last_seen(members),
            )
        )
    if unknown_recent:
        groups.append(
            AdminAppUsageGroupResponse(
                kind="unknown_recent",
                platform=PLATFORM_ANDROID,
                users=_sorted_by_last_seen(unknown_recent),
            )
        )
    if unknown:
        groups.append(
            AdminAppUsageGroupResponse(
                kind="unknown", platform=PLATFORM_ANDROID, users=_sorted_by_last_seen(unknown)
            )
        )
    site_only = [
        (by_id[user_id], usage) for user_id, usage in web_android.items() if user_id not in seen
    ]
    if site_only:
        groups.append(
            AdminAppUsageGroupResponse(
                kind="web_android",
                platform=PLATFORM_WEB_ANDROID,
                users=_sorted_by_last_seen(site_only),
            )
        )
    never = sorted(
        (user for user in users if user.id not in seen and user.id not in web_android),
        key=lambda user: (user.display_name.lower(), user.email),
    )
    if never:
        groups.append(
            AdminAppUsageGroupResponse(
                kind="never", users=[_user_item(user, None) for user in never]
            )
        )

    up_to_date_ids = {
        usage.user_id
        for usage in usages
        if latest_code is not None
        and usage.platform == PLATFORM_ANDROID
        and usage.source == SOURCE_HEADER
        and usage.version_code is not None
        and usage.version_code >= latest_code
    }
    return AdminAppUsageResponse(
        generatedAt=now,
        announced=announced,
        totalUsers=len(users),
        appUsers=len(seen),
        upToDateUsers=len(up_to_date_ids),
        groups=groups,
    )


def notification_recipients(
    session: Session, latest_code: int, *, user_id: UUID | None = None
) -> list[UUID]:
    """Chi riceve la notifica: utenti attivi non già su quella versione (o una più nuova) che
    usano l'app Android (qualsiasi versione, anche non nota) o il sito da Android.

    Decisione di Rosario del 23/11: non chi usa il sito solo da computer o da iPhone (per iOS
    quando ci sarà l'app), né chi da quando il server registra l'uso non si è visto né
    nell'app né sul sito da Android.
    Con la modalità test accesa, solo chi può usare l'app (tester in lista e operatori), come
    ``GET /app/version`` che agli altri non mostra la versione.
    Con ``user_id`` si guarda solo quell'utente (notifica a chi compare dopo l'annuncio).
    """
    stmt = select(User.id).where(_active_humans(), _uses_android(), ~_up_to_date(latest_code))
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    access = TesterAccess(session)
    if access.is_test_mode():
        listed = access.listed_emails()
        stmt = stmt.where(
            or_(User.platform_role == PlatformRole.OPERATOR, func.lower(User.email).in_(listed))
        )
    return list(session.scalars(stmt.order_by(User.created_at.asc(), User.id.asc())).all())


def _dedup_key(latest_code: int) -> str:
    """Una notifica per utente e versionCode, all'annuncio o quando l'utente compare dopo."""
    return f"app_version:android:{latest_code}"


def _notify(
    session: Session, version: AndroidAppVersionResponse, recipients: Iterable[UUID]
) -> int:
    service = NotificationService(session)
    created = 0
    dedup_key = _dedup_key(version.latest_version_code)
    params: dict[str, object] = {
        "version_name": version.latest_version_name,
        "version_code": version.latest_version_code,
        "download_url": version.download_url,
        "message": version.message,
    }
    for user_id in recipients:
        with session.begin_nested():
            _notification, was_created = service.create_notification(
                user_id=user_id,
                category=NotificationCategory.SISTEMA,
                template_key=APP_VERSION_TEMPLATE_KEY,
                template_version=1,
                params=params,
                dedup_key=dedup_key,
                push=True,
                email=False,
            )
        if was_created:
            created += 1
    return created


def notify_new_app_version(session: Session, version: AndroidAppVersionResponse) -> int:
    """Crea le notifiche della nuova versione; restituisce quante sono nuove.

    Idempotente: una notifica per utente e versionCode (``dedup_key``), quindi salvare di nuovo
    lo stesso versionCode (es. per correggere il link) non la rimanda. Preferenze (categoria
    «sistema» ed evento «Nuova versione dell'app», in-app e push) e ore di silenzio della push
    si rispettano come per ogni altra notifica (``NotificationService.create_notification``).
    """
    created = _notify(
        session, version, notification_recipients(session, version.latest_version_code)
    )
    _logger.info(
        "app_version_notified",
        extra={"version_code": version.latest_version_code, "created": created},
    )
    return created


def notify_app_version_on_sighting(session: Session, user_id: UUID) -> bool:
    """La notifica della versione annunciata a chi compare su Android dopo l'annuncio.

    Decisione di Rosario del 24/11: chi usa l'app Android (o il sito da Android) per la prima
    volta dopo l'annuncio, o comunque non l'ha ancora ricevuta, la riceve quando il server
    registra il suo uso (``app_usage.recorder``), con le stesse regole dell'annuncio
    (``notification_recipients`` per un solo utente: non a chi ha già quella versione o una più
    nuova, modalità test, poi preferenze e ore di silenzio). «Già notificato» è la notifica con
    la stessa ``dedup_key`` dell'annuncio (utente e versionCode), quindi annuncio e
    registrazione non la mandano mai due volte. Restituisce se ne ha creata una. Niente commit.
    """
    from admin.app_version import AppVersionStore

    version = AppVersionStore(session).get().android
    if version is None:
        return False
    already = session.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.dedup_key == _dedup_key(version.latest_version_code),
        )
    )
    if already is not None:
        return False
    recipients = notification_recipients(session, version.latest_version_code, user_id=user_id)
    if not recipients or not _notify(session, version, recipients):
        return False
    _logger.info(
        "app_version_notified_on_sighting",
        extra={"version_code": version.latest_version_code, "user_id": str(user_id)},
    )
    return True
