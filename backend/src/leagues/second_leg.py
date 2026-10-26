"""Girone di ritorno di una competizione reale (TASK 9).

Oggi una lega fantacalcio può essere associata a qualunque campionato reale
selezionabile, indipendentemente da quanto sia già avanzata la stagione. La
nuova regola di business impedisce la creazione quando **almeno una** delle
competizioni selezionate ha già iniziato il girone di ritorno (seconda metà
del calendario, dopo l'andata): a quel punto entrare in una lega fantacalcio
su quel campionato non avrebbe senso competitivo (mezza stagione già giocata
senza nessuno schierato).

Il provider sportivo (API-Football) non espone un flag "andata/ritorno"
esplicito: lo deriviamo dalle fixture della stagione.

- ``Fixture.round_label`` porta etichette come ``"Regular Season - 15"``.
  L'ultimo numero nell'etichetta è la giornata; le etichette senza un numero
  finale (es. fasi a eliminazione) non partecipano al conteggio: per quei
  formati "andata/ritorno" non è un concetto applicabile, quindi non blocchiamo.
- Il numero totale di giornate è il massimo fra quelle viste: per un
  campionato a girone unico andata/ritorno (es. la stragrande maggioranza dei
  campionati nazionali) la seconda metà comincia alla giornata
  ``totale // 2 + 1``.
- Una giornata è "iniziata" se almeno una sua fixture è già iniziata: stessa
  definizione di "iniziata" già usata per il lock delle formazioni
  (``fantasy_turns.rules.STARTED_FIXTURE_STATUSES`` / kickoff già passato).

Nessun dato di calendario per la stagione richiesta (es. i 5 campionati MVP
seminati in migrazione, senza fixture) significa che la domanda non è
decidibile: per non bloccare la creazione su un'assenza di informazione,
``has_schedule_data`` è ``False`` e la competizione resta selezionabile.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy_turns.rules import INACTIVE_FIXTURE_STATUSES, STARTED_FIXTURE_STATUSES, ensure_utc
from sports_data.catalog.models import SportSeason
from sports_data.fixtures.models import Fixture

_ROUND_NUMBER_RE = re.compile(r"(\d+)\s*$")


@dataclass(frozen=True)
class SecondLegStatus:
    """Stato "girone di ritorno" di una competizione per una stagione."""

    #: False quando non abbiamo nessuna giornata numerata per la stagione
    #: richiesta: la domanda non è decidibile, non blocchiamo per difetto.
    has_schedule_data: bool
    total_rounds: int | None
    current_round: int | None
    second_leg_start_round: int | None
    second_leg_started: bool


#: Stato condiviso per ogni competizione senza dati di calendario utilizzabili.
_NO_SCHEDULE_DATA = SecondLegStatus(
    has_schedule_data=False,
    total_rounds=None,
    current_round=None,
    second_leg_start_round=None,
    second_leg_started=False,
)


def parse_round_number(round_label: str | None) -> int | None:
    """Numero di giornata dall'etichetta provider (es. ``"Regular Season - 15"`` → 15).

    ``None`` per etichette senza un numero finale (fasi a eliminazione,
    gironi, finali): per quei formati il conteggio andata/ritorno non si
    applica, quindi la giornata viene ignorata invece di rompere il calcolo.
    """
    if not round_label:
        return None
    match = _ROUND_NUMBER_RE.search(round_label.strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def fixture_has_started(
    *,
    status_short: str | None,
    kickoff_at: datetime | None,
    now: datetime,
) -> bool:
    """Stessa definizione di "iniziata" usata per il lock delle formazioni.

    Uno stato live/concluso è autoritativo di per sé. In sua assenza, una
    fixture ancora ``NS`` conta come iniziata solo se il kickoff pubblicato è
    già passato: evita falsi negativi quando il provider non ha ancora
    aggiornato lo stato in tempo reale.
    """
    status = (status_short or "").strip().upper()
    if status in STARTED_FIXTURE_STATUSES:
        return True
    if status in INACTIVE_FIXTURE_STATUSES:
        return False
    if kickoff_at is None:
        return False
    return ensure_utc(now) >= ensure_utc(kickoff_at)


def evaluate_second_leg(
    round_numbers: Iterable[int],
    started_round_numbers: Iterable[int],
) -> SecondLegStatus:
    """Motore puro: dai numeri di giornata visti/iniziati deriva lo stato.

    Separato dalla lettura DB per essere testabile senza fixture/sessione,
    sullo stesso principio di ``leagues.calendar_planning``.
    """
    rounds = set(round_numbers)
    if not rounds:
        return _NO_SCHEDULE_DATA

    total_rounds = max(rounds)
    started = set(started_round_numbers) & rounds
    current_round = max(started) if started else 0

    if total_rounds < 2:
        # Girone unico o dati insufficienti: non c'è un "ritorno" da bloccare.
        return SecondLegStatus(
            has_schedule_data=True,
            total_rounds=total_rounds,
            current_round=current_round,
            second_leg_start_round=None,
            second_leg_started=False,
        )

    second_leg_start_round = total_rounds // 2 + 1
    return SecondLegStatus(
        has_schedule_data=True,
        total_rounds=total_rounds,
        current_round=current_round,
        second_leg_start_round=second_leg_start_round,
        second_leg_started=current_round >= second_leg_start_round,
    )


def second_leg_statuses_for_competitions(
    session: Session,
    *,
    competition_ids: Sequence[UUID],
    season_year: int,
    now: datetime | None = None,
) -> dict[UUID, SecondLegStatus]:
    """Stato "ritorno" per ogni competizione, nella stagione data.

    Due query indipendenti dal numero di competizioni: prima le stagioni
    provider (``sport_seasons``) che coincidono con l'anno richiesto, poi le
    fixture di quelle stagioni. Le competizioni senza una stagione per
    ``season_year`` restano con ``_NO_SCHEDULE_DATA`` (selezionabili).
    """
    statuses: dict[UUID, SecondLegStatus] = dict.fromkeys(competition_ids, _NO_SCHEDULE_DATA)
    if not competition_ids:
        return statuses

    moment = now if now is not None else datetime.now(UTC)

    season_rows = session.execute(
        select(SportSeason.id, SportSeason.competition_id).where(
            SportSeason.competition_id.in_(competition_ids),
            SportSeason.year == season_year,
        )
    ).all()
    if not season_rows:
        return statuses

    season_id_by_competition = {row.competition_id: row.id for row in season_rows}
    season_ids = list(season_id_by_competition.values())

    fixture_rows = session.execute(
        select(
            Fixture.sport_season_id,
            Fixture.round_label,
            Fixture.status_short,
            Fixture.kickoff_at,
        ).where(Fixture.sport_season_id.in_(season_ids))
    ).all()

    rounds_by_season: dict[UUID, set[int]] = defaultdict(set)
    started_by_season: dict[UUID, set[int]] = defaultdict(set)
    for sport_season_id, round_label, status_short, kickoff_at in fixture_rows:
        round_number = parse_round_number(round_label)
        if round_number is None:
            continue
        rounds_by_season[sport_season_id].add(round_number)
        if fixture_has_started(status_short=status_short, kickoff_at=kickoff_at, now=moment):
            started_by_season[sport_season_id].add(round_number)

    for competition_id, season_id in season_id_by_competition.items():
        statuses[competition_id] = evaluate_second_leg(
            rounds_by_season.get(season_id, set()),
            started_by_season.get(season_id, set()),
        )
    return statuses


__all__ = [
    "SecondLegStatus",
    "evaluate_second_leg",
    "fixture_has_started",
    "parse_round_number",
    "second_leg_statuses_for_competitions",
]
