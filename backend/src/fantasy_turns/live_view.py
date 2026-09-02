"""Presentazione live di una partita del turno europeo (EP13-P04).

Motore puro, senza sessione né I/O: ordina la timeline degli eventi e deriva
la freschezza del feed provider.

Il progetto non registra l'esito di ogni sincronizzazione, quindi lo stato del
feed è **derivato** dall'ultimo aggiornamento normalizzato di ciascuna fixture
(`Fixture.updated_at`) confrontato con lo stato della partita. È un'inferenza,
non un fatto registrato: serve a dire all'utente quanto può fidarsi di ciò che
vede, non a diagnosticare il provider.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

#: Stati partita in cui ci si aspetta un flusso di aggiornamenti continuo.
LIVE_FIXTURE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"})
#: Stati terminali: dopo questi il feed non deve più aggiornarsi.
FINISHED_FIXTURE_STATUSES = frozenset({"FT", "AET", "PEN"})
#: Stati in cui la partita non si gioca: l'assenza di aggiornamenti è normale.
INACTIVE_FIXTURE_STATUSES = frozenset({"PST", "CANC", "ABD", "AWD", "WO"})

#: Oltre questa distanza dall'ultimo aggiornamento, una partita live è in ritardo.
DELAYED_AFTER = timedelta(minutes=2)
#: Oltre questa, il dato è da considerarsi fermo.
STALE_AFTER = timedelta(minutes=10)


class ProviderFeedState(StrEnum):
    """Quanto è affidabile ciò che stiamo mostrando."""

    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


PROVIDER_FEED_LABELS: dict[ProviderFeedState, str] = {
    ProviderFeedState.FRESH: "Aggiornato",
    ProviderFeedState.DELAYED: "Aggiornamento in ritardo",
    ProviderFeedState.STALE: "Dati fermi",
    ProviderFeedState.DEGRADED: "Aggiornamento parziale",
    ProviderFeedState.UNAVAILABLE: "Dati non disponibili",
}


@dataclass(frozen=True)
class FixtureFreshness:
    """Input minimo per valutare la freschezza di una singola partita."""

    status_short: str
    updated_at: datetime | None


def fixture_feed_state(
    fixture: FixtureFreshness,
    *,
    now: datetime,
) -> ProviderFeedState:
    """Stato del feed per una singola partita.

    Una partita non ancora iniziata, conclusa o non giocata non deve
    aggiornarsi: l'assenza di aggiornamenti recenti non è un problema e non
    va segnalata come ritardo.
    """
    status = (fixture.status_short or "").upper()
    if fixture.updated_at is None:
        return ProviderFeedState.UNAVAILABLE
    if status not in LIVE_FIXTURE_STATUSES:
        return ProviderFeedState.FRESH

    age = now - fixture.updated_at
    if age >= STALE_AFTER:
        return ProviderFeedState.STALE
    if age >= DELAYED_AFTER:
        return ProviderFeedState.DELAYED
    return ProviderFeedState.FRESH


def turn_feed_state(
    fixtures: Sequence[FixtureFreshness],
    *,
    now: datetime,
) -> ProviderFeedState:
    """Stato aggregato del turno.

    Se tutte le partite condividono lo stesso stato, quello è anche lo stato
    del turno. Se invece solo una parte è in ritardo o ferma, il turno è
    `degraded`: dirlo `stale` sarebbe più allarmante del vero, dirlo `fresh`
    nasconderebbe il problema.
    """
    if not fixtures:
        return ProviderFeedState.UNAVAILABLE

    states = {fixture_feed_state(fixture, now=now) for fixture in fixtures}
    if len(states) == 1:
        return states.pop()
    return ProviderFeedState.DEGRADED


@dataclass(frozen=True)
class TimelineEvent:
    """Evento normalizzato pronto per la vista."""

    id: str
    minute_elapsed: int | None
    minute_extra: int | None
    event_type: str
    event_detail: str | None
    scoring_kind: str | None
    club_id: str | None
    club_name: str | None
    athlete_id: str | None
    athlete_name: str | None
    related_athlete_id: str | None
    related_athlete_name: str | None
    comments: str | None


@dataclass(frozen=True)
class RawTimelineEvent:
    """Riga grezza da `match_events`, già filtrata per fixture."""

    id: str
    minute_elapsed: int | None
    minute_extra: int | None
    event_type: str
    event_detail: str | None
    scoring_kind: str | None
    club_id: str | None
    club_name: str | None
    athlete_id: str | None
    athlete_name: str | None
    related_athlete_id: str | None
    related_athlete_name: str | None
    comments: str | None
    is_active: bool
    retracted_at: datetime | None
    sources: tuple[str, ...] = ()


def minute_label(minute_elapsed: int | None, minute_extra: int | None) -> str:
    """`45+2'` per i recuperi, `—` quando il minuto non è noto."""
    if minute_elapsed is None:
        return "—"
    if minute_extra:
        return f"{minute_elapsed}+{minute_extra}'"
    return f"{minute_elapsed}'"


def build_timeline(events: Iterable[RawTimelineEvent]) -> tuple[TimelineEvent, ...]:
    """Timeline ordinata, senza eventi ritrattati né duplicati sintetici.

    Un evento ritirato dal provider (correzione tardiva) sparisce invece di
    restare a schermo: mostrarlo significherebbe raccontare una partita che
    non è avvenuta. Gli eventi senza minuto finiscono in coda, perché non
    possono essere collocati con certezza.

    Ogni evento di punteggio (gol, autogol, assist, rigore...) esiste in
    doppio: la riga grezza del provider (`scoring_kind` assente) e una copia
    normalizzata (`scoring_kind` valorizzato) usata internamente per il
    fantavoto. Quando la copia normalizzata ha ``sources`` che include
    ``"events"`` significa che una riga grezza equivalente è già presente in
    timeline: mostrarla di nuovo duplicherebbe lo stesso momento di gioco. Le
    normalizzazioni senza controparte grezza (es. un rigore parato dedotto
    solo dalle statistiche giocatore) restano, perché sono l'unica traccia di
    quel momento.
    """
    active = [
        event
        for event in events
        if event.is_active
        and event.retracted_at is None
        and not (event.scoring_kind is not None and "events" in event.sources)
    ]
    active.sort(
        key=lambda event: (
            event.minute_elapsed is None,
            event.minute_elapsed or 0,
            event.minute_extra or 0,
            event.id,
        )
    )
    return tuple(
        TimelineEvent(
            id=event.id,
            minute_elapsed=event.minute_elapsed,
            minute_extra=event.minute_extra,
            event_type=event.event_type,
            event_detail=event.event_detail,
            scoring_kind=event.scoring_kind,
            club_id=event.club_id,
            club_name=event.club_name,
            athlete_id=event.athlete_id,
            athlete_name=event.athlete_name,
            related_athlete_id=event.related_athlete_id,
            related_athlete_name=event.related_athlete_name,
            comments=event.comments,
        )
        for event in active
    )
