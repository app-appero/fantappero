"""Email delivery for external-channel notifications (EP09-05).

Opt-in via the existing profile toggle (``UserProfile.notifications_email``,
EP02-02), gated by quiet hours. Reuses the mail outbox task from EP01/EP02
rather than a parallel delivery path. Never raises: a failure here must not
block the in-app notification that already succeeded.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from auth.models.user import User
from auth.models.user_profile import UserProfile
from notifications.models import Notification
from notifications.quiet_hours import is_within_quiet_hours
from observability.logging import get_logger
from observability.metrics import get_metrics
from observability.propagation import celery_task_headers

logger = get_logger(__name__)


def dispatch_notification_email(
    *,
    notification: Notification,
    user: User,
    profile: UserProfile | None,
) -> None:
    if profile is None or not profile.notifications_email:
        return
    if is_within_quiet_hours(
        now=datetime.now(UTC),
        timezone_name=profile.timezone,
        start_hour=profile.quiet_hours_start_hour,
        end_hour=profile.quiet_hours_end_hour,
    ):
        get_metrics().incr(
            "notifications_email_skipped_total",
            labels={"reason": "quiet_hours", "category": notification.category.value},
        )
        return

    # Deferred import: mail.tasks pulls in app.worker, which registers
    # notifications.tasks (and transitively this module) at import time —
    # importing send_message_task at module scope here would cycle back.
    from mail.tasks import send_message_task

    kwargs = {
        "to_email": user.email,
        "subject": notification.title,
        "text_body": notification.body,
        "html_body": f"<p>{notification.body}</p>",
        "template": f"notification.{notification.category.value}",
    }
    try:
        if os.environ.get("FANTAPPERO_ENV", "").lower() == "test":
            send_message_task.apply(kwargs=kwargs)
        else:
            send_message_task.apply_async(kwargs=kwargs, headers=celery_task_headers())
        get_metrics().incr(
            "notifications_email_enqueued_total", labels={"category": notification.category.value}
        )
    except Exception:
        # External delivery must never take down the domain operation that
        # already succeeded (the in-app notification is already committed).
        logger.warning(
            "notification_email_dispatch_failed",
            extra={"notification_id": str(notification.id)},
        )
        get_metrics().incr(
            "notifications_email_failed_total", labels={"category": notification.category.value}
        )
