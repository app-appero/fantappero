"""Controllo delle date usate come filtri: fuori scala diventano un errore chiaro, non un 500."""

from __future__ import annotations

from datetime import UTC, datetime

from auth.exceptions import ValidationAuthError

_MIN = datetime(1970, 1, 1, tzinfo=UTC)
_MAX = datetime(2200, 1, 1, tzinfo=UTC)


def checked_filter_date(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        utc = aware.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise ValidationAuthError("Data non valida.", code="invalid_date_filter") from exc
    if not _MIN <= utc <= _MAX:
        raise ValidationAuthError(
            "La data deve essere compresa tra il 1970 e il 2200.", code="invalid_date_filter"
        )
    return utc
