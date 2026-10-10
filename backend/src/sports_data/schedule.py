"""Celery beat entries for season-wide sports data sync (catalog + fixtures).

Keeps `sport_seasons`/`fixtures` populated ahead of time so league creation
and "Genera calendario" only ever read the local DB — no admin has to
remember to sync data by hand before a league can get its Turni Europei.
"""

from __future__ import annotations


def sports_data_beat_schedule(
    *,
    catalog_enabled: bool,
    catalog_interval_seconds: int = 86_400,
    fixtures_enabled: bool,
    fixtures_interval_seconds: int = 259_200,
) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    if catalog_enabled:
        schedule["sports-data-sync-catalog"] = {
            "task": "sports_data.sync_mvp_catalog",
            "schedule": float(catalog_interval_seconds),
            "options": {"expires": float(catalog_interval_seconds)},
        }
    if fixtures_enabled:
        schedule["sports-data-sync-fixtures"] = {
            "task": "sports_data.sync_mvp_fixtures",
            # No per-fixture event/lineup/stat detail calls here: that's
            # already covered close to matchday by the pre/live/post poll
            # windows (sports_data.scheduler). This job only needs to keep
            # the season's fixture list and kickoff times current.
            "kwargs": {"include_details": False},
            "schedule": float(fixtures_interval_seconds),
            "options": {"expires": float(fixtures_interval_seconds)},
        }
    return schedule
