"""Lo scheduler dinamico toglie ciò che non è nel catalogo: ogni job del beat deve esserci."""

from notifications.schedule import notifications_beat_schedule
from system_jobs.catalog import SYSTEM_JOBS_BY_KEY


def test_every_notification_beat_job_is_in_the_catalog() -> None:
    schedule = notifications_beat_schedule(
        enabled=True, broadcast_enabled=True, lock_reminder_enabled=True
    )
    missing = [key for key in schedule if key not in SYSTEM_JOBS_BY_KEY]
    assert missing == []
