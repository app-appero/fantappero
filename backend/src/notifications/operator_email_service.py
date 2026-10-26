"""Operator-composed emails: compose, pick recipients, send, keep history (Task 6c).

Reuses the broadcast audience selection (``notifications.broadcast_service``)
so operators pick recipients the same way for notification broadcasts and
for a direct email: everyone, a set of leagues, or hand-picked users (same
``audience`` shape, same ``/admin/notifications/recipients`` listing).

Unlike the in-app broadcast (EP09-06) — which can never email (see
``broadcast_service.create_broadcast``) — this *is* an email, sent on an
explicit operator action. It intentionally bypasses the per-category
notification gates (``UserProfile.notifications_email``,
``NOTIFICATIONS_ROUTINE_EMAIL_ENABLED``): those gate *automatic* game-event
notifications (Task 6b), not a one-off message an operator decided to send.
See docs/operations/email_notifications.md.
"""

from __future__ import annotations

import html
import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.models.user import User
from mail.templates import EmailMessage
from notifications.broadcast_service import audience_label, resolve_audience
from notifications.models import OperatorEmailLog
from observability.logging import get_logger
from observability.metrics import get_metrics
from observability.propagation import celery_task_headers

logger = get_logger(__name__)


class OperatorEmailError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _build_message(subject: str, body: str) -> EmailMessage:
    escaped = html.escape(body).replace("\n", "<br>")
    return EmailMessage(subject=subject, text_body=body, html_body=f"<p>{escaped}</p>")


def _enqueue_to_all(recipients: list[User], message: EmailMessage) -> None:
    # Deferred import: mail.tasks pulls in app.worker, which registers
    # notifications.tasks (and transitively modules that import this one) at
    # import time — importing send_message_task at module scope would cycle,
    # same reasoning as notifications/email_dispatch.py.
    from mail.tasks import send_message_task

    is_test_env = os.environ.get("FANTAPPERO_ENV", "").lower() == "test"
    for user in recipients:
        kwargs = {
            "to_email": user.email,
            "subject": message.subject,
            "text_body": message.text_body,
            "html_body": message.html_body,
            "template": "operator_email",
        }
        try:
            if is_test_env:
                send_message_task.apply(kwargs=kwargs)
            else:
                send_message_task.apply_async(kwargs=kwargs, headers=celery_task_headers())
        except Exception:
            # One recipient's delivery failure must not block the others or
            # the already-recorded history entry.
            logger.warning(
                "operator_email_dispatch_failed",
                extra={"user_id": str(user.id)},
            )
            get_metrics().incr("operator_email_failed_total")


def send_operator_email(
    session: Session,
    *,
    created_by: UUID,
    subject: str,
    body: str,
    audience: dict[str, object],
) -> OperatorEmailLog:
    """Resolve recipients, enqueue the email to each, and record history."""
    subject = subject.strip()
    body = body.strip()
    if not subject or not body:
        raise OperatorEmailError("empty_message", "Oggetto e testo sono obbligatori.")

    recipient_ids = resolve_audience(session, audience)
    if not recipient_ids:
        raise OperatorEmailError("empty_audience", "Nessun destinatario per questo pubblico.")

    recipients = list(session.scalars(select(User).where(User.id.in_(recipient_ids))).all())

    message = _build_message(subject, body)
    _enqueue_to_all(recipients, message)
    get_metrics().incr("operator_email_sent_total", amount=len(recipients))

    log = OperatorEmailLog(
        subject=subject,
        body=body,
        audience=audience,
        audience_label=audience_label(session, audience, len(recipients)),
        recipient_count=len(recipients),
        created_by_user_id=created_by,
        sent_at=datetime.now(UTC),
    )
    session.add(log)
    session.flush()
    return log


def list_history(
    session: Session, *, page: int, page_size: int
) -> tuple[list[OperatorEmailLog], int]:
    total = int(session.scalar(select(func.count()).select_from(OperatorEmailLog)) or 0)
    rows = session.scalars(
        select(OperatorEmailLog)
        .order_by(OperatorEmailLog.sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rows), total
