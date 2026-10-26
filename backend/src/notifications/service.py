"""Notification center service: create (idempotent), list, read state, preferences (EP09-01)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.enums import NotificationCategory, NotificationStatus
from notifications.email_dispatch import dispatch_notification_email
from notifications.event_catalog import (
    EVENT_DEFINITION_BY_KEY,
    EVENT_DEFINITIONS,
    EVENT_KEYS,
    event_key_for_template,
)
from notifications.exceptions import NotificationNotFoundError
from notifications.models import (
    Notification,
    NotificationEventPreference,
    NotificationPreference,
    PushDevice,
)
from notifications.push_dispatch import dispatch_notification_push
from notifications.schemas import (
    MarkAllReadResponse,
    NotificationEventPreferenceItemResponse,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationPreferenceItemResponse,
    NotificationPreferenceListResponse,
    PushDeviceResponse,
)
from notifications.templates import render_notification
from observability.logging import get_logger
from observability.metrics import get_metrics
from realtime.publisher import publish_after_commit, user_channel

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

logger = get_logger(__name__)


def _to_item(notification: Notification) -> NotificationItemResponse:
    return NotificationItemResponse(
        id=str(notification.id),
        category=notification.category.value,
        title=notification.title,
        body=notification.body,
        deepLink=notification.deep_link,
        read=notification.read_at is not None,
        readAt=notification.read_at.isoformat() if notification.read_at else None,
        createdAt=notification.created_at.isoformat(),
    )


class NotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _in_app_enabled(self, user_id: UUID, category: NotificationCategory) -> bool:
        preference = self._session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category,
            )
        )
        return preference is None or preference.in_app_enabled

    def _event_preference(
        self, user_id: UUID, event_key: str
    ) -> NotificationEventPreference | None:
        return self._session.scalar(
            select(NotificationEventPreference).where(
                NotificationEventPreference.user_id == user_id,
                NotificationEventPreference.event_key == event_key,
            )
        )

    def create_notification(
        self,
        *,
        user_id: UUID,
        category: NotificationCategory,
        template_key: str,
        template_version: int,
        params: dict[str, object],
        dedup_key: str,
        push: bool = True,
        email: bool = True,
    ) -> tuple[Notification | None, bool]:
        """Create an in-app notification, or return the existing one for ``dedup_key``.

        Returns ``(notification, created)``. ``notification`` is ``None`` (no
        row involved) only when the user has disabled the category — or,
        more granularly (TASK5), the specific event — in their preferences;
        ``created`` is ``False`` whenever an existing row for ``dedup_key``
        was returned instead of a new one (idempotent replay).

        The granular per-event preference (``notifications/event_catalog.py``)
        only applies when ``template_key`` is mapped to an event: unmapped
        template keys keep behaving exactly as before, governed solely by the
        category preference. A granular ``push_enabled=False`` does not drop
        the in-app row — it only suppresses the push for *this* notification,
        the same way the category-level switch never touched push/email: it
        only ever gated whether the row (and therefore every channel hanging
        off it) got created at all.
        """
        existing = self._session.scalar(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.dedup_key == dedup_key,
            )
        )
        if existing is not None:
            get_metrics().incr("notifications_deduped_total", labels={"category": category.value})
            return existing, False

        if not self._in_app_enabled(user_id, category):
            get_metrics().incr("notifications_skipped_total", labels={"category": category.value})
            return None, False

        event_key = event_key_for_template(template_key)
        event_preference = self._event_preference(user_id, event_key) if event_key else None
        if event_preference is not None and not event_preference.in_app_enabled:
            get_metrics().incr(
                "notifications_skipped_total",
                labels={"category": category.value, "event_key": event_key or ""},
            )
            return None, False
        if event_preference is not None and not event_preference.push_enabled:
            push = False

        content = render_notification(template_key, template_version, params)
        notification = Notification(
            user_id=user_id,
            category=category,
            status=NotificationStatus.DELIVERED,
            template_key=template_key,
            template_version=template_version,
            dedup_key=dedup_key,
            title=content.title,
            body=content.body,
            deep_link=content.deep_link,
        )
        try:
            with self._session.begin_nested():
                self._session.add(notification)
                self._session.flush()
        except IntegrityError:
            # Concurrent create with the same dedup_key — idempotent replay.
            replayed = self._session.scalar(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.dedup_key == dedup_key,
                )
            )
            if replayed is not None:
                get_metrics().incr(
                    "notifications_deduped_total", labels={"category": category.value}
                )
                return replayed, False
            raise

        get_metrics().incr("notifications_created_total", labels={"category": category.value})
        logger.info(
            "notification_created",
            extra={"category": category.value, "template_key": template_key},
        )
        publish_after_commit(
            self._session,
            user_channel(user_id),
            {
                "type": "notification.created",
                "notificationId": str(notification.id),
                "category": category.value,
            },
        )
        if email:
            self._dispatch_email(notification)
        if push:
            self._dispatch_push(notification)
        return notification, True

    def _dispatch_email(self, notification: Notification) -> None:
        user = self._session.get(User, notification.user_id)
        if user is None:
            return
        profile = self._session.get(UserProfile, notification.user_id)
        dispatch_notification_email(notification=notification, user=user, profile=profile)

    def _dispatch_push(self, notification: Notification) -> None:
        user = self._session.get(User, notification.user_id)
        if user is None:
            return
        profile = self._session.get(UserProfile, notification.user_id)
        dispatch_notification_push(notification=notification, user=user, profile=profile)

    def list_notifications(
        self,
        *,
        user_id: UUID,
        category: NotificationCategory | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> NotificationListResponse:
        filters = [Notification.user_id == user_id]
        if category is not None:
            filters.append(Notification.category == category)
        if unread_only:
            filters.append(Notification.read_at.is_(None))

        total = self._session.scalar(select(func.count()).select_from(Notification).where(*filters))
        total = total or 0
        total_pages = math.ceil(total / page_size) if total else 0

        rows = self._session.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        unread_count = self._session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )

        return NotificationListResponse(
            items=[_to_item(row) for row in rows],
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
            unreadCount=unread_count or 0,
        )

    def mark_read(self, *, user_id: UUID, notification_id: UUID) -> NotificationItemResponse:
        notification = self._session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        if notification is None:
            raise NotificationNotFoundError()

        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            self._session.flush()
            get_metrics().incr(
                "notifications_read_total", labels={"category": notification.category.value}
            )
        return _to_item(notification)

    def mark_all_read(self, *, user_id: UUID) -> MarkAllReadResponse:
        result = self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        marked = result.rowcount or 0
        if marked:
            get_metrics().incr(
                "notifications_read_total", labels={"category": "all"}, amount=marked
            )
        return MarkAllReadResponse(markedCount=marked)

    def get_preferences(self, *, user_id: UUID) -> NotificationPreferenceListResponse:
        rows = {
            row.category: row
            for row in self._session.scalars(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            ).all()
        }
        items = [
            NotificationPreferenceItemResponse(
                category=category.value,
                inAppEnabled=rows[category].in_app_enabled if category in rows else True,
            )
            for category in NotificationCategory
        ]
        event_rows = {
            row.event_key: row
            for row in self._session.scalars(
                select(NotificationEventPreference).where(
                    NotificationEventPreference.user_id == user_id
                )
            ).all()
        }
        events = [
            NotificationEventPreferenceItemResponse(
                eventKey=definition.event_key,
                category=definition.category,
                label=definition.label,
                inAppEnabled=(
                    event_rows[definition.event_key].in_app_enabled
                    if definition.event_key in event_rows
                    else True
                ),
                pushEnabled=(
                    event_rows[definition.event_key].push_enabled
                    if definition.event_key in event_rows
                    else True
                ),
            )
            for definition in EVENT_DEFINITIONS
        ]
        return NotificationPreferenceListResponse(items=items, events=events)

    def update_preference(
        self, *, user_id: UUID, category: NotificationCategory, in_app_enabled: bool
    ) -> NotificationPreferenceItemResponse:
        preference = self._session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category,
            )
        )
        if preference is None:
            preference = NotificationPreference(
                user_id=user_id,
                category=category,
                in_app_enabled=in_app_enabled,
            )
            self._session.add(preference)
        else:
            preference.in_app_enabled = in_app_enabled
        self._session.flush()
        return NotificationPreferenceItemResponse(
            category=category.value,
            inAppEnabled=preference.in_app_enabled,
        )

    def update_event_preference(
        self,
        *,
        user_id: UUID,
        event_key: str,
        in_app_enabled: bool | None,
        push_enabled: bool | None,
    ) -> NotificationEventPreferenceItemResponse:
        """Aggiorna uno o entrambi i canali di un evento granulare (TASK5).

        ``None`` lascia il canale com'era (o sul default "attivo" se la riga
        non esisteva ancora): permette al chiamante di toccare solo in-app o
        solo push senza dover rileggere lo stato attuale.
        """
        if event_key not in EVENT_KEYS:
            msg = f"Evento non valido: {event_key}"
            raise ValueError(msg)
        definition = EVENT_DEFINITION_BY_KEY[event_key]
        preference = self._event_preference(user_id, event_key)
        if preference is None:
            preference = NotificationEventPreference(
                user_id=user_id,
                event_key=event_key,
                in_app_enabled=in_app_enabled if in_app_enabled is not None else True,
                push_enabled=push_enabled if push_enabled is not None else True,
            )
            self._session.add(preference)
        else:
            if in_app_enabled is not None:
                preference.in_app_enabled = in_app_enabled
            if push_enabled is not None:
                preference.push_enabled = push_enabled
        self._session.flush()
        return NotificationEventPreferenceItemResponse(
            eventKey=event_key,
            category=definition.category,
            label=definition.label,
            inAppEnabled=preference.in_app_enabled,
            pushEnabled=preference.push_enabled,
        )

    def register_push_device(
        self, *, user_id: UUID, token: str, platform: str
    ) -> PushDeviceResponse:
        """Upsert per ``token``: un reinstall o un altro utente sullo stesso
        dispositivo deve spostare il token, non duplicarlo."""
        now = datetime.now(UTC)
        existing = self._session.scalar(select(PushDevice).where(PushDevice.token == token))
        if existing is not None:
            existing.user_id = user_id
            existing.platform = platform
            existing.last_seen_at = now
            existing.revoked_at = None
            self._session.flush()
            return PushDeviceResponse(id=str(existing.id), platform=existing.platform)

        device = PushDevice(user_id=user_id, token=token, platform=platform, last_seen_at=now)
        try:
            with self._session.begin_nested():
                self._session.add(device)
                self._session.flush()
        except IntegrityError:
            # Registrazione concorrente dello stesso token — rileggi e aggiorna.
            replayed = self._session.scalar(select(PushDevice).where(PushDevice.token == token))
            if replayed is None:
                raise
            replayed.user_id = user_id
            replayed.platform = platform
            replayed.last_seen_at = now
            replayed.revoked_at = None
            self._session.flush()
            return PushDeviceResponse(id=str(replayed.id), platform=replayed.platform)
        return PushDeviceResponse(id=str(device.id), platform=device.platform)

    def unregister_push_device(self, *, user_id: UUID, token: str) -> None:
        device = self._session.scalar(
            select(PushDevice).where(PushDevice.token == token, PushDevice.user_id == user_id)
        )
        if device is not None:
            self._session.delete(device)
            self._session.flush()
