"""Tipi e codici del pannello qualità dati sportivi (EP04-07)."""

from __future__ import annotations

from enum import StrEnum


class QualityIssueKind(StrEnum):
    """Categorie mostrate all’operatore."""

    MISSING = "missing"
    DELAY = "delay"
    CONFLICT = "conflict"
    CORRECTION = "correction"


class QualitySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class QualityIssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class QualityIssueCode(StrEnum):
    """Codici macchina stabili (i18n-ready: i messaggi restano in IT)."""

    MISSING_EVENTS = "missing_events"
    MISSING_LINEUPS = "missing_lineups"
    MISSING_STATS = "missing_stats"
    POSTPONED = "postponed"
    KICKOFF_OVERDUE = "kickoff_overdue"
    EVENT_CONFLICT = "event_conflict"
    EVENT_RETRACTED = "event_retracted"
    STATS_HASH_CHANGED = "stats_hash_changed"


class SyncRetryStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"


# Messaggi operatore in italiano (chiave = codice; predisposti a i18n futura).
ISSUE_MESSAGES_IT: dict[QualityIssueCode, str] = {
    QualityIssueCode.MISSING_EVENTS: "Fixture terminata senza eventi timeline attivi.",
    QualityIssueCode.MISSING_LINEUPS: "Fixture terminata senza lineup ufficiali.",
    QualityIssueCode.MISSING_STATS: "Fixture terminata senza statistiche giocatore.",
    QualityIssueCode.POSTPONED: "Partita rinviata (stato PST).",
    QualityIssueCode.KICKOFF_OVERDUE: "Kickoff scaduto ma stato ancora non iniziato.",
    QualityIssueCode.EVENT_CONFLICT: "Conflitto o anomalia su evento di scoring.",
    QualityIssueCode.EVENT_RETRACTED: "Evento ritirato dopo correzione provider.",
    QualityIssueCode.STATS_HASH_CHANGED: "Statistiche aggiornate (correzione hash).",
}

ISSUE_TITLES_IT: dict[QualityIssueCode, str] = {
    QualityIssueCode.MISSING_EVENTS: "Eventi mancanti",
    QualityIssueCode.MISSING_LINEUPS: "Lineup mancanti",
    QualityIssueCode.MISSING_STATS: "Statistiche mancanti",
    QualityIssueCode.POSTPONED: "Rinvio",
    QualityIssueCode.KICKOFF_OVERDUE: "Ritardo kickoff",
    QualityIssueCode.EVENT_CONFLICT: "Conflitto eventi",
    QualityIssueCode.EVENT_RETRACTED: "Correzione evento",
    QualityIssueCode.STATS_HASH_CHANGED: "Correzione statistiche",
}

FINISHED_STATUSES = frozenset({"FT", "AET", "PEN"})
PRE_STATUSES = frozenset({"NS", "TBD"})
