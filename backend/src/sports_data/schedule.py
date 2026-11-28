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
    predicted_lineups_enabled: bool = True,
    predicted_lineups_interval_seconds: int = 3600,
    market_values_enabled: bool = False,
    market_values_interval_seconds: int = 3600,
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
    if predicted_lineups_enabled:
        # Sempre un intervallo, mai un crontab: lo scheduler del pannello
        # (system_jobs.scheduler) riscrive ogni voce come intervallo con la frequenza
        # salvata, e un crontab diventava in silenzio "ogni 24 ore dall'avvio del beat"
        # (giro delle 07:00 UTC mai partito, 28/11). Il giro è orario: la guardia per
        # partita in sync_predicted_lineups (snapshot recente, aggiornamento del
        # mattino) evita chiamate inutili al fornitore, e dopo un riavvio si recupera
        # entro un'ora.
        schedule["sports-predicted-lineups"] = {
            "task": "sports_data.sync_predicted_lineups",
            "schedule": float(predicted_lineups_interval_seconds),
            "options": {"expires": float(predicted_lineups_interval_seconds)},
        }
    if market_values_enabled:
        # Medie stagionali e Valore (1.3): nessuna chiamata al fornitore, salta se nulla cambia.
        schedule["market-values-refresh"] = {
            "task": "market.refresh_market_values",
            "schedule": float(market_values_interval_seconds),
            "options": {"expires": float(market_values_interval_seconds)},
        }
    return schedule
