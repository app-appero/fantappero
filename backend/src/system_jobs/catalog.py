"""Catalogo dei job periodici del beat.

La frequenza e l'accensione di partenza arrivano dalle variabili d'ambiente.
Il pannello operatore le sovrascrive a runtime: il beat rilegge questa
tabella senza un nuovo deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SystemJobSpec:
    key: str
    task: str
    title: str
    description: str
    enabled_attr: str
    interval_attr: str
    default_interval_seconds: int
    min_interval_seconds: int
    max_interval_seconds: int
    default_enabled: bool = True
    kwargs: dict[str, object] = field(default_factory=dict)


SYSTEM_JOBS: tuple[SystemJobSpec, ...] = (
    SystemJobSpec(
        key="sports-poll-live",
        task="sports_data.poll_live_window",
        title="Risultati live",
        description=(
            "Durante le partite in corso chiede al provider punteggio, eventi e "
            "statistiche giocatore, poi ricalcola i turni fantasy aperti."
        ),
        enabled_attr="sports_scheduler_enabled",
        interval_attr="sports_poll_live_interval_seconds",
        default_interval_seconds=60,
        min_interval_seconds=15,
        max_interval_seconds=3600,
        default_enabled=False,
    ),
    SystemJobSpec(
        key="sports-poll-pre",
        task="sports_data.poll_pre_match_window",
        title="Pre-partita",
        description=(
            "Nelle ore prima del calcio d'inizio aggiorna orario e formazioni "
            "ufficiali delle partite ancora non iniziate."
        ),
        enabled_attr="sports_scheduler_enabled",
        interval_attr="sports_poll_pre_interval_seconds",
        default_interval_seconds=900,
        min_interval_seconds=60,
        max_interval_seconds=7200,
        default_enabled=False,
    ),
    SystemJobSpec(
        key="sports-poll-post",
        task="sports_data.poll_post_match_window",
        title="Dopo la partita",
        description=(
            "A partita finita (o ancora segnata come non iniziata nonostante "
            "l'orario sia passato) aggiorna stato e statistiche di tutti i "
            "campionati e omologa il turno fantasy quando i dati sono completi."
        ),
        enabled_attr="sports_scheduler_enabled",
        interval_attr="sports_poll_post_interval_seconds",
        default_interval_seconds=600,
        min_interval_seconds=60,
        max_interval_seconds=7200,
        default_enabled=False,
    ),
    SystemJobSpec(
        key="sports-poll-late",
        task="sports_data.poll_late_corrections_window",
        title="Correzioni tardive",
        description=(
            "Nelle 72 ore dopo la fine corregge risultati e statistiche già "
            "pubblicati e ricalcola i turni ancora provvisori."
        ),
        enabled_attr="sports_scheduler_enabled",
        interval_attr="sports_poll_late_interval_seconds",
        default_interval_seconds=3600,
        min_interval_seconds=300,
        max_interval_seconds=86400,
        default_enabled=False,
    ),
    SystemJobSpec(
        key="fantasy-turns-ensure-upcoming",
        task="fantasy_turns.ensure_upcoming",
        title="Turni in arrivo",
        description=(
            "Crea i turni europei della finestra vicina, ricalcola i cutoff e "
            "apre un turno programmato se il cutoff non è ancora passato."
        ),
        enabled_attr="fantasy_turns_auto_generate_enabled",
        interval_attr="fantasy_turns_auto_generate_interval_seconds",
        default_interval_seconds=3600,
        min_interval_seconds=300,
        max_interval_seconds=86400,
    ),
    SystemJobSpec(
        key="fantasy-turns-refresh-full-calendar",
        task="fantasy_turns.refresh_full_calendar_active_leagues",
        title="Calendario stagione",
        description=(
            "Riallinea l'intera stagione di ogni lega attiva: partite, turni "
            "europei e calendario fantallenatori, non solo la finestra vicina."
        ),
        enabled_attr="fantasy_turns_full_refresh_enabled",
        interval_attr="fantasy_turns_full_refresh_interval_seconds",
        default_interval_seconds=21_600,
        min_interval_seconds=3600,
        max_interval_seconds=604_800,
    ),
    SystemJobSpec(
        key="fantasy-lineups-generate-ai",
        task="fantasy_lineups.generate_ai",
        title="Formazioni IA",
        description=(
            "Schiera le squadre gestite dall'IA sui turni aperti. Non tocca "
            "le formazioni confermate dai fantallenatori umani."
        ),
        enabled_attr="ai_lineups_auto_generate_enabled",
        interval_attr="ai_lineups_auto_generate_interval_seconds",
        default_interval_seconds=1800,
        min_interval_seconds=300,
        max_interval_seconds=86400,
    ),
    SystemJobSpec(
        key="notifications-lineup-reminders",
        task="notifications.send_lineup_reminders",
        title="Promemoria formazione",
        description=(
            "Avvisa in app i fantallenatori che non hanno ancora una formazione "
            "quando il blocco del turno si avvicina."
        ),
        enabled_attr="notifications_lineup_reminder_enabled",
        interval_attr="notifications_lineup_reminder_interval_seconds",
        default_interval_seconds=900,
        min_interval_seconds=60,
        max_interval_seconds=86400,
    ),
    SystemJobSpec(
        key="sports-data-sync-catalog",
        task="sports_data.sync_mvp_catalog",
        title="Catalogo campionati",
        description=(
            "Aggiorna competizioni, stagione corrente e club dei campionati "
            "ufficiali, indipendentemente dalle leghe già create."
        ),
        enabled_attr="sports_data_catalog_sync_enabled",
        interval_attr="sports_data_catalog_sync_interval_seconds",
        default_interval_seconds=86_400,
        min_interval_seconds=3600,
        max_interval_seconds=604_800,
    ),
    SystemJobSpec(
        key="sports-data-sync-fixtures",
        task="sports_data.sync_mvp_fixtures",
        title="Calendario partite",
        description=(
            "Scarica date, orari e stati di tutte le partite della stagione. "
            "Non chiede eventi e voti: quelli restano ai giri live e post-partita."
        ),
        enabled_attr="sports_data_fixtures_sync_enabled",
        interval_attr="sports_data_fixtures_sync_interval_seconds",
        default_interval_seconds=259_200,
        min_interval_seconds=3600,
        max_interval_seconds=604_800,
        kwargs={"include_details": False},
    ),
)

SYSTEM_JOBS_BY_KEY: dict[str, SystemJobSpec] = {spec.key: spec for spec in SYSTEM_JOBS}
