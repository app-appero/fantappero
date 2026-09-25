"""Classifica il campo ``reason`` di ``/injuries`` in categoria interna (OQ-11).

Il provider espone solo ``type`` (``Missing Fixture`` / ``Questionable``), che
NON distingue infortunio da squalifica. La distinzione reale è nel campo
``reason``: una stringa a bassa cardinalità (41 valori osservati su un
campione reale di 3168 voci, lega Premier League 2024), non testo libero.
Per questo la classificazione è una tabella fissa esplicita — mai un parser
NLP — con un fallback a poche regole deterministiche per valori non ancora
osservati.
"""

from __future__ import annotations

from database.enums import PlayerAvailabilityCategory

#: Valori di ``reason`` osservati su un campione reale (Premier League 2024,
#: 3168 voci) più i casi aggiuntivi trovati controllando la Lazio 2026.
#: Aggiornare questa tabella quando si osservano nuovi valori reali, non
#: indovinare varianti non viste.
KNOWN_REASONS: dict[str, PlayerAvailabilityCategory] = {
    "knee injury": PlayerAvailabilityCategory.INJURY,
    "thigh injury": PlayerAvailabilityCategory.INJURY,
    "ankle injury": PlayerAvailabilityCategory.INJURY,
    "muscle injury": PlayerAvailabilityCategory.INJURY,
    "injury": PlayerAvailabilityCategory.INJURY,
    "calf injury": PlayerAvailabilityCategory.INJURY,
    "hamstring injury": PlayerAvailabilityCategory.INJURY,
    "groin injury": PlayerAvailabilityCategory.INJURY,
    "leg injury": PlayerAvailabilityCategory.INJURY,
    "shoulder injury": PlayerAvailabilityCategory.INJURY,
    "knock": PlayerAvailabilityCategory.INJURY,
    "foot injury": PlayerAvailabilityCategory.INJURY,
    "achilles tendon injury": PlayerAvailabilityCategory.INJURY,
    "back injury": PlayerAvailabilityCategory.INJURY,
    "broken leg": PlayerAvailabilityCategory.INJURY,
    "hand injury": PlayerAvailabilityCategory.INJURY,
    "red card": PlayerAvailabilityCategory.SUSPENSION,
    "yellow cards": PlayerAvailabilityCategory.SUSPENSION,
    "lacking match fitness": PlayerAvailabilityCategory.OTHER,
    "illness": PlayerAvailabilityCategory.ILLNESS,
    "coach's decision": PlayerAvailabilityCategory.OTHER,
    "inactive": PlayerAvailabilityCategory.OTHER,
    "personal reasons": PlayerAvailabilityCategory.OTHER,
    "not in squad": PlayerAvailabilityCategory.OTHER,
    "suspended": PlayerAvailabilityCategory.SUSPENSION,
    "national duty": PlayerAvailabilityCategory.OTHER,
}


def classify_availability_reason(reason: str | None) -> PlayerAvailabilityCategory:
    """Deriva la categoria interna da un ``reason`` grezzo del provider.

    Ordine: tabella fissa (case-insensitive) → regole deterministiche di
    fallback su poche parole chiave → ``OTHER`` se nulla corrisponde.
    """
    if not reason:
        return PlayerAvailabilityCategory.OTHER
    key = reason.strip().lower()
    if key in KNOWN_REASONS:
        return KNOWN_REASONS[key]
    if "card" in key or "suspen" in key or "ban" in key:
        return PlayerAvailabilityCategory.SUSPENSION
    if "illness" in key or "sick" in key or "covid" in key or "flu" in key:
        return PlayerAvailabilityCategory.ILLNESS
    if "injury" in key or "injured" in key or "surgery" in key or "operation" in key:
        return PlayerAvailabilityCategory.INJURY
    return PlayerAvailabilityCategory.OTHER
