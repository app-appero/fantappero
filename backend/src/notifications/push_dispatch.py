"""Push delivery for external-channel notifications (EP09-05).

Opt-in via the existing profile toggle (``UserProfile.notifications_push``,
already present but previously unused), gated by quiet hours and by the
global ``NOTIFICATIONS_PUSH_ENABLED`` kill switch. Mirrors
``email_dispatch.py``: never raises, a failure here must not block the
in-app notification that already succeeded.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from auth.models.user import User
from auth.models.user_profile import UserProfile
from config.settings.loader import get_api_settings
from notifications.models import Notification
from notifications.quiet_hours import is_within_quiet_hours
from observability.logging import get_logger
from observability.metrics import get_metrics
from observability.propagation import celery_task_headers

logger = get_logger(__name__)


def dispatch_notification_push(
    *,
    notification: Notification,
    user: User,
    profile: UserProfile | None,
) -> None:
    if profile is None or not profile.notifications_push:
        return
    if not get_api_settings().notifications_push_enabled:
        return
    if is_within_quiet_hours(
        now=datetime.now(UTC),
        timezone_name=profile.timezone,
        start_hour=profile.quiet_hours_start_hour,
        end_hour=profile.quiet_hours_end_hour,
    ):
        get_metrics().incr(
            "notifications_push_skipped_total",
            labels={"reason": "quiet_hours", "category": notification.category.value},
        )
        return

    # Deferred import: notifications.tasks pulls in app.worker, which
    # registers notifications.tasks itself (and transitively this module) at
    # import time — importing send_push_task at module scope here would cycle.
    from notifications.tasks import send_push_task

    kwargs = {
        "user_id": str(user.id),
        "notification_id": str(notification.id),
        "title": notification.title,
        "body": notification.body,
        "deep_link": notification.deep_link,
        "category": notification.category.value,
    }
    try:
        if os.environ.get("FANTAPPERO_ENV", "").lower() == "test":
            send_push_task.apply(kwargs=kwargs)
        else:
            send_push_task.apply_async(kwargs=kwargs, headers=celery_task_headers())
        get_metrics().incr(
            "notifications_push_enqueued_total", labels={"category": notification.category.value}
        )
    except Exception:
        logger.warning(
            "notification_push_dispatch_failed",
            extra={"notification_id": str(notification.id)},
        )
        get_metrics().incr(
            "notifications_push_failed_total", labels={"category": notification.category.value}
        )
