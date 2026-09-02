"""Calendario H2H adattivo sulle finestre europee eleggibili (EP13-P03).

Motore puro, senza sessione né I/O. Dalle fixture della stagione ricava le
finestre europee realmente utilizzabili, calcola quanti cicli round-robin
completi ci stanno dentro e produce una **mappatura esplicita** giornata H2H →
finestra, invece di affidarsi all'uguaglianza dei numeri progressivi
(``FantasyRound.number == LeagueCalendarSlot.round_number``).

Quel mapping MVP conta anche le finestre sotto soglia, che diventano turni
``skipped``: una giornata H2H associata a una di quelle finestre non è mai
giocabile. Qui le finestre scartate non consumano una giornata.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import ceil
from uuid import UUID

from database.enums import FantasyTurnKind
from fantasy_turns.rules import (
    DEFAULT_LEAGUE_TZ,
    EligibleFixtureRef,
    evaluate_threshold,
    is_fixture_status_eligible,
    resolve_zone,
    window_for_kind,
)
from leagues.schedule import GeneratedSlot, generate_single_round_robin

CALENDAR_ALGORITHM_VERSION = "adaptive_windows_v2"

#: Giorni locali che appartengono alla finestra weekend (Ven–Lun); i restanti
#: (Mar–Gio) alla finestra infrasettimanale. Insieme coprono la settimana
#: senza buchi né sovrapposizioni.
_WEEKEND_WEEKDAYS = frozenset({4, 5, 6, 0})

UNUSED_WINDOW_REASON = (
    "Finestra eleggibile non utilizzata: le giornate rimaste non bastano a "
    "completare un altro ciclo."
)


@dataclass(frozen=True)
class WindowCandidate:
    """Una finestra europea con il verdetto di eleggibilità e il motivo."""

    start_at: datetime
    end_at: datetime
    kind: FantasyTurnKind
    timezone: str
    fixture_count: int
    min_required: int
    eligible: bool
    reason: str | None


@dataclass(frozen=True)
class PlannedRound:
    """Associazione esplicita fra una giornata H2H e la finestra che la ospita."""

    round_number: int
    cycle_number: int
    cycle_round_number: int
    window_start_at: datetime
    window_end_at: datetime
    window_kind: FantasyTurnKind


@dataclass(frozen=True)
class CalendarPlan:
    algorithm_version: str
    participant_count: int
    cycle_length: int
    cycle_count: int
    round_count: int
    matchup_count: int
    bye_count: int
    slots: tuple[GeneratedSlot, ...]
    rounds: tuple[PlannedRound, ...]
    windows_used: tuple[WindowCandidate, ...]
    windows_discarded: tuple[WindowCandidate, ...]
    eligible_window_count: int
    windows_fingerprint: str

    @property
    def is_generatable(self) -> bool:
        """False quando non c'è nemmeno una finestra valida da usare."""
        return self.round_count > 0


def window_bounds_for_kickoff(
    kickoff_at: datetime,
    *,
    tz_name: str = str(DEFAULT_LEAGUE_TZ),
) -> tuple[datetime, datetime, FantasyTurnKind]:
    """Finestra europea che contiene un kickoff, nel fuso della lega."""
    local_date = kickoff_at.astimezone(resolve_zone(tz_name)).date()
    kind = (
        FantasyTurnKind.WEEKEND
        if local_date.weekday() in _WEEKEND_WEEKDAYS
        else FantasyTurnKind.MIDWEEK
    )
    window = window_for_kind(kind, local_date, tz_name=tz_name)
    return window.start_at, window.end_at, kind


def build_window_candidates(
    fixtures: Iterable[EligibleFixtureRef],
    *,
    min_fixtures: int,
    tz_name: str = str(DEFAULT_LEAGUE_TZ),
) -> tuple[WindowCandidate, ...]:
    """Raggruppa le fixture in finestre e applica la soglia documentata.

    Conta solo le fixture con stato eleggibile: una partita annullata non
    contribuisce a rendere utilizzabile una finestra.
    """
    buckets: dict[tuple[datetime, datetime, FantasyTurnKind], int] = {}
    for fixture in fixtures:
        if fixture.kickoff_at is None:
            continue
        if not is_fixture_status_eligible(fixture.status_short):
            continue
        key = window_bounds_for_kickoff(fixture.kickoff_at, tz_name=tz_name)
        buckets[key] = buckets.get(key, 0) + 1

    candidates: list[WindowCandidate] = []
    for (start_at, end_at, kind), count in buckets.items():
        threshold = evaluate_threshold(count, min_fixtures)
        candidates.append(
            WindowCandidate(
                start_at=start_at,
                end_at=end_at,
                kind=kind,
                timezone=tz_name,
                fixture_count=count,
                min_required=min_fixtures,
                eligible=threshold.ok,
                reason=threshold.skip_reason,
            )
        )
    candidates.sort(key=lambda candidate: (candidate.start_at, candidate.end_at))
    return tuple(candidates)


def cycle_length_for(participant_count: int) -> int:
    """``N-1`` giornate con N pari, ``N`` con N dispari (una di riposo a testa)."""
    if participant_count < 2:
        raise ValueError("Servono almeno due partecipanti per un calendario H2H.")
    if participant_count % 2 == 0:
        return participant_count - 1
    return participant_count


def windows_fingerprint(windows: Sequence[WindowCandidate]) -> str:
    """Impronta delle finestre eleggibili: cambia se il provider sposta il calendario."""
    payload = "|".join(
        f"{window.start_at.isoformat()}~{window.end_at.isoformat()}"
        for window in windows
        if window.eligible
    )
    return sha256(payload.encode("utf-8")).hexdigest()


#: Nodo fittizio usato per pareggiare i vertici di grado dispari; la stringa
#: vuota non può collidere con un UUID e ordina per prima.
_DUMMY_NODE = ""


def _next_unused_edge(
    adjacency: dict[str, list[tuple[str, int]]],
    pointer: dict[str, int],
    used: set[int],
    node: str,
) -> tuple[str, int] | None:
    edges = adjacency[node]
    while pointer[node] < len(edges):
        neighbour, edge_index = edges[pointer[node]]
        pointer[node] += 1
        if edge_index not in used:
            return neighbour, edge_index
    return None


def balance_home_away(slots: Sequence[GeneratedSlot]) -> tuple[GeneratedSlot, ...]:
    """Orientamento casa/trasferta ottimale, senza toccare gli accoppiamenti.

    Il rebalance greedy di ``leagues.schedule`` resta bloccato in un ottimo
    locale con 7 partecipanti (scarto ±2). Qui gli scontri sono archi di un
    multigrafo: aggiungendo archi fittizi sui vertici di grado dispari tutti i
    gradi diventano pari, e ogni percorrenza greedy si chiude in una
    passeggiata chiusa. In una passeggiata chiusa ogni vertice consuma tanti
    archi entranti quanti uscenti, quindi chi gioca un numero pari di partite
    resta in perfetto equilibrio e chi ne gioca un numero dispari si ferma a
    una sola partita di scarto — il minimo teorico.
    """
    matches = [
        (index, slot.home_membership_id, slot.away_membership_id)
        for index, slot in enumerate(slots)
        if not slot.is_bye and slot.away_membership_id is not None
    ]
    if not matches:
        return tuple(slots)

    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    node_of: dict[str, UUID] = {}
    degree: Counter[str] = Counter()

    for index, home, away in matches:
        home_key, away_key = str(home), str(away)
        node_of[home_key] = home
        node_of[away_key] = away
        adjacency[home_key].append((away_key, index))
        adjacency[away_key].append((home_key, index))
        degree[home_key] += 1
        degree[away_key] += 1

    # I vertici di grado dispari sono sempre in numero pari.
    dummy_index = -1
    for node in sorted(node for node, count in degree.items() if count % 2 == 1):
        adjacency[_DUMMY_NODE].append((node, dummy_index))
        adjacency[node].append((_DUMMY_NODE, dummy_index))
        dummy_index -= 1

    for edges in adjacency.values():
        edges.sort()

    used: set[int] = set()
    pointer: dict[str, int] = defaultdict(int)
    orientation: dict[int, tuple[str, str]] = {}

    for start in sorted(adjacency):
        while True:
            node = start
            progressed = False
            while True:
                step = _next_unused_edge(adjacency, pointer, used, node)
                if step is None:
                    break
                neighbour, edge_index = step
                used.add(edge_index)
                if edge_index >= 0:
                    orientation[edge_index] = (node, neighbour)
                node = neighbour
                progressed = True
            if not progressed:
                break

    result = list(slots)
    for index, (tail, head) in orientation.items():
        original = result[index]
        result[index] = GeneratedSlot(
            round_number=original.round_number,
            slot_index=original.slot_index,
            is_bye=False,
            home_membership_id=node_of[tail],
            away_membership_id=node_of[head],
        )
    return tuple(result)


def generate_cycles(
    membership_ids: list[UUID],
    *,
    cycle_count: int,
) -> tuple[GeneratedSlot, ...]:
    """Ripete il round-robin di base alternando casa/trasferta a ogni ciclo.

    Il ciclo base viene prima riequilibrato: con un numero dispari di cicli
    l'alternanza non si annulla e lo squilibrio residuo è esattamente quello
    del ciclo base.
    """
    if cycle_count <= 0:
        return ()
    base = generate_single_round_robin(membership_ids)
    base_slots = balance_home_away(base.slots)
    cycle_length = base.round_count

    slots: list[GeneratedSlot] = []
    for cycle_index in range(cycle_count):
        swap = cycle_index % 2 == 1
        offset = cycle_index * cycle_length
        for slot in base_slots:
            if slot.is_bye or slot.away_membership_id is None:
                slots.append(
                    GeneratedSlot(
                        round_number=slot.round_number + offset,
                        slot_index=slot.slot_index,
                        is_bye=True,
                        home_membership_id=slot.home_membership_id,
                        away_membership_id=None,
                    )
                )
                continue
            home = slot.away_membership_id if swap else slot.home_membership_id
            away = slot.home_membership_id if swap else slot.away_membership_id
            slots.append(
                GeneratedSlot(
                    round_number=slot.round_number + offset,
                    slot_index=slot.slot_index,
                    is_bye=False,
                    home_membership_id=home,
                    away_membership_id=away,
                )
            )
    return tuple(slots)


def plan_calendar(
    membership_ids: list[UUID],
    windows: Sequence[WindowCandidate],
    *,
    max_cycles: int | None = None,
) -> CalendarPlan:
    """Massimo numero di cicli completi che entra nelle finestre eleggibili.

    Nessun ciclo parziale: le giornate residue resterebbero non equilibrate,
    quindi le finestre in eccesso vengono dichiarate inutilizzate con motivo.
    """
    participant_count = len(membership_ids)
    if participant_count < 2:
        # La preview è raggiungibile anche in `configuring`, quando la lega
        # può avere il solo owner: nessun calendario è possibile, ma la
        # diagnostica deve rispondere invece di sollevare.
        return CalendarPlan(
            algorithm_version=CALENDAR_ALGORITHM_VERSION,
            participant_count=participant_count,
            cycle_length=0,
            cycle_count=0,
            round_count=0,
            matchup_count=0,
            bye_count=0,
            slots=(),
            rounds=(),
            windows_used=(),
            windows_discarded=tuple(windows),
            eligible_window_count=sum(1 for window in windows if window.eligible),
            windows_fingerprint=windows_fingerprint(windows),
        )

    cycle_length = cycle_length_for(participant_count)
    eligible = [window for window in windows if window.eligible]

    # Corrispondenza 1:1 con i Turni Europei: ogni finestra valida genera una
    # giornata H2H. L'ultimo ciclo può restare parziale — meglio un girone
    # incompleto in coda che turni europei senza la loro giornata fantasy.
    rounds_needed = len(eligible)
    if max_cycles is not None:
        rounds_needed = min(rounds_needed, max(max_cycles, 0) * cycle_length)
    cycle_count = ceil(rounds_needed / cycle_length) if cycle_length else 0

    slots = tuple(
        slot
        for slot in generate_cycles(membership_ids, cycle_count=cycle_count)
        if slot.round_number <= rounds_needed
    )

    rounds: list[PlannedRound] = []
    for index in range(rounds_needed):
        window = eligible[index]
        rounds.append(
            PlannedRound(
                round_number=index + 1,
                cycle_number=index // cycle_length + 1,
                cycle_round_number=index % cycle_length + 1,
                window_start_at=window.start_at,
                window_end_at=window.end_at,
                window_kind=window.kind,
            )
        )

    used = eligible[:rounds_needed]
    used_keys = {(window.start_at, window.end_at) for window in used}
    discarded: list[WindowCandidate] = []
    for window in windows:
        if (window.start_at, window.end_at) in used_keys:
            continue
        if window.eligible:
            # Eleggibile ma avanzata: il motivo non è la soglia.
            discarded.append(
                WindowCandidate(
                    start_at=window.start_at,
                    end_at=window.end_at,
                    kind=window.kind,
                    timezone=window.timezone,
                    fixture_count=window.fixture_count,
                    min_required=window.min_required,
                    eligible=True,
                    reason=UNUSED_WINDOW_REASON,
                )
            )
        else:
            discarded.append(window)

    matchup_count = sum(1 for slot in slots if not slot.is_bye)
    bye_count = sum(1 for slot in slots if slot.is_bye)

    return CalendarPlan(
        algorithm_version=CALENDAR_ALGORITHM_VERSION,
        participant_count=participant_count,
        cycle_length=cycle_length,
        cycle_count=cycle_count,
        round_count=rounds_needed,
        matchup_count=matchup_count,
        bye_count=bye_count,
        slots=slots,
        rounds=tuple(rounds),
        windows_used=tuple(used),
        windows_discarded=tuple(discarded),
        eligible_window_count=len(eligible),
        windows_fingerprint=windows_fingerprint(windows),
    )


def assert_plan_invariants(plan: CalendarPlan, membership_ids: list[UUID]) -> None:
    """Verifica le regole FR-LEG-04 estese ai cicli multipli (EP13-P03).

    Dalla corrispondenza 1:1 con i Turni Europei l'ultimo ciclo può essere
    parziale: le invarianti *per giornata* (ogni squadra gioca una volta sola,
    nessuno scontro senza avversario, finestre distinte e cronologiche)
    restano assolute, quelle *per ciclo* (copertura completa degli
    accoppiamenti, riposi equi) valgono solo sui cicli interi.
    """
    if plan.round_count == 0:
        if plan.slots or plan.rounds:
            raise AssertionError("piano vuoto con slot o giornate")
        return

    ids = set(membership_ids)
    participant_count = len(membership_ids)
    pairs_per_cycle = participant_count * (participant_count - 1) // 2
    full_cycles = plan.round_count // plan.cycle_length

    if plan.cycle_count != ceil(plan.round_count / plan.cycle_length):
        raise AssertionError("numero di cicli incoerente con le giornate")
    if plan.matchup_count != sum(1 for slot in plan.slots if not slot.is_bye):
        raise AssertionError("numero di scontri incoerente")
    if len(plan.rounds) != plan.round_count:
        raise AssertionError("mappatura giornate incompleta")

    # Ogni giornata è associata a una finestra distinta e cronologica.
    seen_windows: set[tuple[datetime, datetime]] = set()
    previous_start: datetime | None = None
    for planned in plan.rounds:
        key = (planned.window_start_at, planned.window_end_at)
        if key in seen_windows:
            raise AssertionError("due giornate sulla stessa finestra")
        seen_windows.add(key)
        if previous_start is not None and planned.window_start_at <= previous_start:
            raise AssertionError("finestre non in ordine cronologico")
        previous_start = planned.window_start_at

    by_round: dict[int, list[GeneratedSlot]] = {}
    for slot in plan.slots:
        by_round.setdefault(slot.round_number, []).append(slot)
    if len(by_round) != plan.round_count:
        raise AssertionError("giornate mancanti negli slot")

    pair_counts: dict[frozenset[UUID], int] = {}
    byes_per_cycle: dict[int, list[UUID]] = {}

    for round_number, round_slots in sorted(by_round.items()):
        cycle_number = (round_number - 1) // plan.cycle_length + 1
        appearing: list[UUID] = []
        for slot in round_slots:
            appearing.append(slot.home_membership_id)
            if slot.is_bye:
                if slot.away_membership_id is not None:
                    raise AssertionError(f"riposo con avversario alla giornata {round_number}")
                byes_per_cycle.setdefault(cycle_number, []).append(slot.home_membership_id)
                continue
            if slot.away_membership_id is None:
                raise AssertionError(f"scontro senza avversario alla giornata {round_number}")
            appearing.append(slot.away_membership_id)
            pair = frozenset((slot.home_membership_id, slot.away_membership_id))
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        if len(appearing) != len(set(appearing)):
            raise AssertionError(f"una squadra gioca due volte alla giornata {round_number}")
        if not set(appearing).issubset(ids):
            raise AssertionError("membership sconosciuta nel calendario")
        if ids - set(appearing):
            raise AssertionError(f"squadra assente alla giornata {round_number}")

    # Copertura accoppiamenti: garantita solo sui cicli interi. Nel ciclo
    # parziale finale una coppia può essersi incontrata una volta in più.
    if full_cycles >= 1 and len(pair_counts) != pairs_per_cycle:
        raise AssertionError("copertura degli accoppiamenti incompleta")
    if any(count not in (full_cycles, full_cycles + 1) for count in pair_counts.values()):
        raise AssertionError("una coppia si incontra troppe volte")

    if participant_count % 2 == 1:
        for cycle_number in range(1, full_cycles + 1):
            resting = byes_per_cycle.get(cycle_number, [])
            if sorted(resting, key=str) != sorted(ids, key=str):
                raise AssertionError(
                    f"riposi non equi nel ciclo {cycle_number}: attesa una volta per squadra"
                )
        # Ciclo parziale: nessuna squadra può riposare due volte.
        trailing = byes_per_cycle.get(full_cycles + 1, [])
        if len(trailing) != len(set(trailing)):
            raise AssertionError("una squadra riposa due volte nel ciclo parziale")
    elif byes_per_cycle:
        raise AssertionError("riposi presenti con numero pari di partecipanti")
