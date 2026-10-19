"""Invia un giro di push ai dispositivi di un utente e aggiorna i token morti (EP09-05)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from notifications.expo_push_client import ExpoPushClient, ExpoPushError
from notifications.models import PushDevice
from observability.logging import get_logger

logger = get_logger(__name__)


def send_to_devices(
    session: Session,
    client: ExpoPushClient,
    devices: list[PushDevice],
    *,
    title: str,
    body: str,
    data: dict[str, Any],
) -> dict[str, int]:
    """Non rilancia mai: un fallimento dell'invio push non deve far fallire il task."""
    if not devices:
        return {"sent": 0, "revoked": 0}
    messages = [
        {"to": device.token, "title": title, "body": body, "data": data, "sound": "default"}
        for device in devices
    ]
    try:
        tickets = client.send(messages)
    except ExpoPushError:
        logger.warning("expo_push_send_failed", exc_info=True)
        return {"sent": 0, "revoked": 0}

    sent = 0
    revoked = 0
    now = datetime.now(UTC)
    for device, ticket in zip(devices, tickets, strict=False):
        status = ticket.get("status") if isinstance(ticket, dict) else None
        if status == "ok":
            sent += 1
            continue
        details = ticket.get("details") if isinstance(ticket, dict) else None
        error = details.get("error") if isinstance(details, dict) else None
        if error == "DeviceNotRegistered":
            device.revoked_at = now
            revoked += 1
    if revoked:
        session.flush()
    return {"sent": sent, "revoked": revoked}
