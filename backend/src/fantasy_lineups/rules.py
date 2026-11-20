"""Approved modules, substitutions, copy/draft and tactical moves."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from database.enums import FantasyModule, FantasyRole, FantasyTurnStatus, LineupSlotKind
from fantasy_turns.rules import (
    INACTIVE_FIXTURE_STATUSES,
    STARTED_FIXTURE_STATUSES,
    ensure_utc,
)

APPROVED_MODULES: tuple[FantasyModule, ...] = tuple(FantasyModule)

MODULE_OUTFIELD: dict[FantasyModule, tuple[int, int, int]] = {
    FantasyModule.M343: (3, 4, 3),
    FantasyModule.M352: (3, 5, 2),
    FantasyModule.M433: (4, 3, 3),
    FantasyModule.M442: (4, 4, 2),
    FantasyModule.M451: (4, 5, 1),
    FantasyModule.M532: (5, 3, 2),
    FantasyModule.M541: (5, 4, 1),
}

STARTER_COUNT = 11
GOALKEEPER_STARTERS = 1
MIN_AUTOMATIC_SUBSTITUTIONS = 0
MAX_AUTOMATIC_SUBSTITUTIONS = 5
STANDARD_AUTOMATIC_SUBSTITUTIONS = 5
MAX_TACTICAL_MOVES = 3
#: Dimensione della "panchina attiva" (regola di gioco, non il numero di
#: cambi automatici: ``MAX_AUTOMATIC_SUBSTITUTIONS`` resta un parametro
#: indipendente). I primi ``BENCH_ACTIVE_SIZE`` posti della panchina ordinata
#: devono garantire una copertura minima per ruolo (``BENCH_ACTIVE_ROLE_QUOTA``);
#: dall'11° posto in poi ("tribuna") qualunque ruolo è libero.
BENCH_ACTIVE_SIZE = 10
BENCH_ACTIVE_ROLE_QUOTA: dict[FantasyRole, int] = {
    FantasyRole.P: 1,
    FantasyRole.D: 3,
    FantasyRole.C: 3,
    FantasyRole.A: 3,
}
_BENCH_ROLE_LABELS: dict[FantasyRole, tuple[str, str]] = {
    FantasyRole.P: ("portiere", "portieri"),
    FantasyRole.D: ("difensore", "difensori"),
    FantasyRole.C: ("centrocampista", "centrocampisti"),
    FantasyRole.A: ("attaccante", "attaccanti"),
}
BENCH_ACTIVE_ROLE_QUOTA_MESSAGE = (
    f"Nei primi {BENCH_ACTIVE_SIZE} della panchina servono "
    f"{BENCH_ACTIVE_ROLE_QUOTA[FantasyRole.P]} portiere, "
    f"{BENCH_ACTIVE_ROLE_QUOTA[FantasyRole.D]} difensori, "
    f"{BENCH_ACTIVE_ROLE_QUOTA[FantasyRole.C]} centrocampisti e "
    f"{BENCH_ACTIVE_ROLE_QUOTA[FantasyRole.A]} attaccanti"
)
#: Margine di preavviso del lock per-giocatore quando la lega non ne ha uno
#: configurato (EP-turni-automazione), editabile per lega in `LeagueRules`.
DEFAULT_LINEUP_LOCK_MARGIN_MINUTES = 15
BENCH_ORDER_LOCKED_MESSAGE = (
    "Non puoi cambiare l'ordine di panchina di un calciatore la cui partita è già iniziata."
)
TACTICAL_MOVES_EXHAUSTED_MESSAGE = (
    "Hai già usato le 3 mosse tattiche di questo turno. "
    "Non puoi più modificare i calciatori ancora sbloccati."
)
COPIED_NOT_IN_ROSTER_MESSAGE = (
    "Uno o più calciatori della formazione precedente non sono più in rosa e sono stati esclusi."
)
COPIED_UNAVAILABLE_MESSAGE = (
    "Uno o più calciatori non sono disponibili: la loro partita è già iniziata."
)
ATHLETE_NOT_IN_ROSTER_MESSAGE = "Uno o più calciatori schierati non appartengono alla rosa."
#: Avviso del contesto formazione (QA 19/11): chi non è più in rosa è stato tolto dalla
#: formazione salvata o dalla bozza di un turno ancora modificabile.
LINEUP_ATHLETE_LEFT_ROSTER_CODE = "lineup_athlete_left_roster"
#: Titolare o nei primi ``BENCH_ACTIVE_SIZE`` della panchina un calciatore in esubero di ruolo
#: (``exceeds_role_quota``): è in rosa ma non si schiera finché la rosa non torna in regola.
ATHLETE_EXCEEDS_ROLE_QUOTA_CODE = "athlete_exceeds_role_quota"
COPIED_EXCEEDS_ROLE_QUOTA_CODE = "copied_athlete_exceeds_role_quota"
#: Titolare o nei primi ``BENCH_ACTIVE_SIZE`` della panchina un calciatore che non ha un ruolo
#: nemmeno con i ripieghi del risolutore (``role_unresolved`` nella rosa, es. uscito dal listone
#: perché passato a un campionato che non copriamo). Decisione di Rosario del 20/11: vale come
#: chi è in esubero di ruolo, resta in rosa ma non si schiera finché non riceve un ruolo.
ATHLETE_ROLE_UNRESOLVED_CODE = "athlete_role_unresolved"
COPIED_ROLE_UNRESOLVED_CODE = "copied_athlete_role_unresolved"


@dataclass(frozen=True)
class ModuleCounts:
    code: FantasyModule
    goalkeepers: int
    defenders: int
    midfielders: int
    forwards: int

    def for_role(self, role: FantasyRole) -> int:
        if role == FantasyRole.P:
            return self.goalkeepers
        if role == FantasyRole.D:
            return self.defenders
        if role == FantasyRole.C:
            return self.midfielders
        return self.forwards


@dataclass(frozen=True)
class LineupIssue:
    code: str
    message: str


@dataclass(frozen=True)
class LineupPlayerRef:
    athlete_id: object
    role: FantasyRole | None


@dataclass(frozen=True)
class LineupEvaluation:
    valid: bool
    issues: tuple[LineupIssue, ...]
    starter_counts: dict[str, int]


@dataclass(frozen=True)
class AutomaticSubstitution:
    out_athlete_id: object
    in_athlete_id: object
    role: FantasyRole
    order: int


@dataclass(frozen=True)
class SkippedBenchCandidate:
    """Panchinaro non utilizzato e motivo (FR-SUB-01: spiegazione dell'esito)."""

    athlete_id: object
    role: FantasyRole | None
    reason: str


@dataclass(frozen=True)
class SubstitutionResolution:
    substitutions: tuple[AutomaticSubstitution, ...]
    effective_starter_ids: tuple[object, ...]
    module_valid: bool
    skipped: tuple[SkippedBenchCandidate, ...] = ()


@dataclass(frozen=True)
class TacticalMoveEvaluation:
    would_consume: bool
    remaining_after: int
    issues: tuple[LineupIssue, ...]


@dataclass(frozen=True)
class DepartedLineupCleanup:
    """Formazione senza chi non è più in rosa (vedi `drop_departed_athletes`)."""

    #: Stessi posti di prima: ``""`` dove c'era chi è uscito, così gli altri non scalano.
    starter_ids: tuple[object, ...]
    #: Panchina senza chi è uscito, gli altri nello stesso ordine.
    bench_ids: tuple[object, ...]
    #: Chi è stato tolto, nell'ordine in cui compariva (titolari, poi panchina).
    removed_ids: tuple[object, ...]


@dataclass(frozen=True)
class CopyLineupResult:
    module: str
    starter_ids: tuple[object, ...]
    bench_ids: tuple[object, ...]
    dropped_athlete_ids: tuple[object, ...]
    unavailable_athlete_ids: tuple[object, ...]
    issues: tuple[LineupIssue, ...]
    blocked: bool
    can_confirm: bool


def coerce_max_automatic_substitutions(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("max_automatic_substitutions must be an integer")
    if value < MIN_AUTOMATIC_SUBSTITUTIONS or value > MAX_AUTOMATIC_SUBSTITUTIONS:
        raise ValueError(
            "max_automatic_substitutions must be between "
            f"{MIN_AUTOMATIC_SUBSTITUTIONS} and {MAX_AUTOMATIC_SUBSTITUTIONS}"
        )
    return value


def parse_module(value: str) -> FantasyModule | None:
    try:
        return FantasyModule(value)
    except ValueError:
        return None


def module_counts(code: FantasyModule) -> ModuleCounts:
    defenders, midfielders, forwards = MODULE_OUTFIELD[code]
    return ModuleCounts(
        code=code,
        goalkeepers=GOALKEEPER_STARTERS,
        defenders=defenders,
        midfielders=midfielders,
        forwards=forwards,
    )


def approved_module_catalog() -> list[ModuleCounts]:
    return [module_counts(code) for code in APPROVED_MODULES]


def starter_template(code: FantasyModule) -> list[FantasyRole]:
    counts = module_counts(code)
    return (
        [FantasyRole.P] * counts.goalkeepers
        + [FantasyRole.D] * counts.defenders
        + [FantasyRole.C] * counts.midfielders
        + [FantasyRole.A] * counts.forwards
    )


def count_roles(players: Sequence[LineupPlayerRef]) -> dict[FantasyRole, int]:
    counter: Counter[FantasyRole] = Counter()
    for player in players:
        if player.role is not None:
            counter[player.role] += 1
    return {role: int(counter.get(role, 0)) for role in FantasyRole}


def bench_active_role_requirements(
    bench: Sequence[LineupPlayerRef],
) -> dict[FantasyRole, int]:
    """Quota minima per ruolo nei primi ``BENCH_ACTIVE_SIZE`` posti di panchina.

    ``required[r] = min(quota[r], giocatori di ruolo r in panchina)``: una
    rosa sbilanciata (es. solo 2 attaccanti rimasti fuori dagli undici
    titolari) non può essere bloccata da una quota che richiede più
    giocatori di quel ruolo di quanti ce ne siano in tutta la panchina.
    """
    bench_role_counts = count_roles(bench)
    return {
        role: min(BENCH_ACTIVE_ROLE_QUOTA.get(role, 0), bench_role_counts.get(role, 0))
        for role in FantasyRole
    }


def reorder_bench_for_active_roles(
    bench: Sequence[LineupPlayerRef],
) -> list[LineupPlayerRef]:
    """Riordina (stabile, senza punteggio) per soddisfare la regola
    "panchina attiva" quando la rosa lo permette.

    Usata da `copy_previous_lineup`: una copia che violerebbe la regola
    solo per l'ORDINE ereditato dal turno precedente si auto-corregge,
    invece di bloccare un'azione altrimenti valida. Non inventa né rimuove
    giocatori — sposta solo l'ordine di quelli già in panchina, scegliendo
    per ciascun ruolo chi compare prima (nessuna sorpresa su chi finisce
    nei primi 10, solo l'ordine). Una rosa che non ha proprio abbastanza
    giocatori di un ruolo resta non sistemabile: `bench_roles_invalid`
    scatterà comunque in `evaluate_lineup`, qui non c'è nulla da spostare.

    Esito a blocchi di ruolo P→D→C→A sia nella panchina attiva sia in
    tribuna (11°+), ordine relativo dentro lo stesso ruolo invariato
    (stabile). Eventuali posti liberi nella panchina attiva (somma
    `required` < `active_size`) restano nell'ordine di bench originale,
    qualunque ruolo — sono per definizione senza un ruolo da garantire.
    """
    if not bench:
        return []
    required = bench_active_role_requirements(bench)
    active_size = min(BENCH_ACTIVE_SIZE, len(bench))

    by_role: dict[FantasyRole | None, list[LineupPlayerRef]] = defaultdict(list)
    for player in bench:
        by_role[player.role].append(player)

    active: list[LineupPlayerRef] = []
    used_ids: set[object] = set()
    for role, needed in required.items():
        chosen = by_role.get(role, [])[: max(0, needed)]
        active.extend(chosen)
        used_ids.update(player.athlete_id for player in chosen)

    fill = max(0, active_size - len(active))
    if fill:
        free_candidates = [player for player in bench if player.athlete_id not in used_ids]
        picked = free_candidates[:fill]
        active.extend(picked)
        used_ids.update(player.athlete_id for player in picked)

    tail = [
        player
        for role in (FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A)
        for player in by_role.get(role, ())
        if player.athlete_id not in used_ids
    ]
    return active + tail


@dataclass(frozen=True)
class BenchRoleRepair:
    """Panchina dopo ``restore_bench_active_roles``."""

    #: Panchina completa (panchina attiva e tribuna) nel nuovo ordine.
    bench: tuple[LineupPlayerRef, ...]
    #: ``(chi è salito, chi è sceso)`` per ogni scambio, nell'ordine in cui sono stati fatti.
    moves: tuple[tuple[object, object], ...]
    #: Ruoli che mancano ancora nei primi ``BENCH_ACTIVE_SIZE`` (vuoto: panchina in regola).
    missing: dict[FantasyRole, int]

    @property
    def changed(self) -> bool:
        return bool(self.moves)


def bench_active_role_shortfall(
    bench: Sequence[LineupPlayerRef],
    *,
    unavailable_athlete_ids: Iterable[object] = (),
    unfieldable_athlete_ids: Iterable[object] = (),
) -> dict[FantasyRole, int]:
    """Quanti ne mancano per ruolo nei primi ``BENCH_ACTIVE_SIZE``, come ``evaluate_lineup``.

    Chi è in ``unavailable_athlete_ids`` (esubero di ruolo, ruolo non risolto) dall'11° posto in
    poi non conta, come nella validazione (``drop_role_quota_excess_from_tribuna``); chi è in
    ``unfieldable_athlete_ids`` (nessun voto possibile nel turno) non alza la quota, come
    ``evaluate_lineup(unfieldable_athlete_ids=...)``. Senza, la quota si conta come web e app
    già installati: su tutta la panchina.
    """
    filled = [ref for ref in bench if ref.athlete_id not in {None, ""}]
    counted = drop_role_quota_excess_from_tribuna(
        filled, unavailable_athlete_ids, key=lambda ref: ref.athlete_id
    )
    if not counted:
        return {}
    unfieldable = {item for item in unfieldable_athlete_ids if item not in {None, ""}}
    required = bench_active_role_requirements(
        [ref for ref in counted if ref.athlete_id not in unfieldable]
    )
    active = count_roles(counted[:BENCH_ACTIVE_SIZE])
    return {
        role: needed - active.get(role, 0)
        for role, needed in required.items()
        if active.get(role, 0) < needed
    }


def restore_bench_active_roles(
    bench: Sequence[LineupPlayerRef],
    *,
    locked_athlete_ids: Iterable[object] = (),
    unavailable_athlete_ids: Iterable[object] = (),
    unfieldable_athlete_ids: Iterable[object] = (),
    overtake_locked_in_tribuna: bool = False,
) -> BenchRoleRepair:
    """Rimette in regola la quota per ruolo dei primi ``BENCH_ACTIVE_SIZE`` con il minimo di
    spostamenti (Rosario, 20/11: un portiere in panchina al posto dell'attaccante).

    Quando il sistema riscrive una panchina senza il fantallenatore (chi esce dalla rosa, la
    regola di inizio turno) gli altri scalano di un posto e il primo della tribuna entra al 10°
    posto qualunque ruolo abbia: con la tribuna in ordine P→D→C→A, uscito un attaccante, saliva
    un portiere e la formazione non era più salvabile (``bench_roles_invalid``).

    Per ogni ruolo che manca, finché la rosa lo permette:

    - scende l'ultimo dei primi ``BENCH_ACTIVE_SIZE`` che è in più per il suo ruolo (di solito
      proprio chi era appena salito dalla tribuna) e diventa il primo della tribuna;
    - chi era dopo di lui sale di un posto e il primo della tribuna con il ruolo che manca
      diventa il ``BENCH_ACTIVE_SIZE``-esimo.

    Nessun altro si sposta e l'ordine dentro ogni ruolo resta quello scelto dal fantallenatore
    (conta per i cambi automatici, che vanno solo a parità di ruolo). Chi ha la partita già
    iniziata (``locked_athlete_ids``) non si sposta e non si scavalca; chi è in
    ``unavailable_athlete_ids`` (esubero di ruolo, ruolo non risolto) non sale; chi è in
    ``unfieldable_athlete_ids`` (nessun voto nel turno) non alza la quota e non sale, come nella
    validazione. Senza, la quota si conta come web e app già installati. Se il ruolo che
    manca non si può far salire la panchina resta com'è (``missing``): la validazione lo dirà.
    Con ``overtake_locked_in_tribuna`` (regola di inizio turno, del sistema) chi ha la partita
    iniziata ed è in tribuna si può scavalcare: scala di un posto in tribuna, che non entra mai
    nei cambi automatici; nei primi ``BENCH_ACTIVE_SIZE`` resta un limite. Il fantallenatore
    invece non può (``evaluate_bench_order_lock``), quindi web e app non lo fanno.
    Funzione pura; la stessa regola è ``restoreBenchActiveRoles`` in
    ``packages/contracts`` (tasto «Sistema la panchina» di web e app).
    """
    locked = {item for item in locked_athlete_ids if item not in {None, ""}}
    unavailable = {item for item in unavailable_athlete_ids if item not in {None, ""}}
    unfieldable = {item for item in unfieldable_athlete_ids if item not in {None, ""}}
    empty = [ref for ref in bench if ref.athlete_id in {None, ""}]
    items = [ref for ref in bench if ref.athlete_id not in {None, ""}]
    moves: list[tuple[object, object]] = []
    while True:
        missing = bench_active_role_shortfall(
            items, unavailable_athlete_ids=unavailable, unfieldable_athlete_ids=unfieldable
        )
        if not missing:
            break
        counted = drop_role_quota_excess_from_tribuna(
            items, unavailable, key=lambda ref: ref.athlete_id
        )
        required = bench_active_role_requirements(
            [ref for ref in counted if ref.athlete_id not in unfieldable]
        )
        active = count_roles(items[:BENCH_ACTIVE_SIZE])

        def surplus(ref: LineupPlayerRef, active=active, required=required) -> bool:
            return ref.role is None or active.get(ref.role, 0) > required.get(ref.role, 0)

        demotable = [
            index
            for index in range(min(BENCH_ACTIVE_SIZE, len(items)) - 1, -1, -1)
            if items[index].athlete_id not in locked and surplus(items[index])
        ]
        pair: tuple[int, int] | None = None
        for role in FantasyRole:
            if role not in missing:
                continue
            promotable = [
                index
                for index in range(BENCH_ACTIVE_SIZE, len(items))
                if items[index].role == role
                and items[index].athlete_id not in locked
                and items[index].athlete_id not in unavailable
                and items[index].athlete_id not in unfieldable
            ]
            for down in demotable:
                up = next(
                    (
                        candidate
                        for candidate in promotable
                        if not any(
                            items[index].athlete_id in locked
                            and (index < BENCH_ACTIVE_SIZE or not overtake_locked_in_tribuna)
                            for index in range(down + 1, candidate)
                        )
                    ),
                    None,
                )
                if up is not None:
                    pair = (down, up)
                    break
            if pair is not None:
                break
        if pair is None:
            break
        down, up = pair
        promoted, demoted = items[up], items[down]
        items = [
            *(ref for index, ref in enumerate(items[:BENCH_ACTIVE_SIZE]) if index != down),
            promoted,
            demoted,
            *(ref for index, ref in enumerate(items) if index >= BENCH_ACTIVE_SIZE and index != up),
        ]
        moves.append((promoted.athlete_id, demoted.athlete_id))
    return BenchRoleRepair(
        bench=(*items, *empty),
        moves=tuple(moves),
        missing=bench_active_role_shortfall(
            items, unavailable_athlete_ids=unavailable, unfieldable_athlete_ids=unfieldable
        ),
    )


def _bench_role_shortfall_message(missing: Mapping[FantasyRole, int]) -> str:
    parts = []
    for role in FantasyRole:
        count = missing.get(role, 0)
        if count <= 0:
            continue
        singular, plural = _BENCH_ROLE_LABELS[role]
        parts.append(f"{count} {singular if count == 1 else plural}")
    shortfall = " e ".join(parts) if len(parts) <= 2 else f"{', '.join(parts[:-1])} e {parts[-1]}"
    return f"{BENCH_ACTIVE_ROLE_QUOTA_MESSAGE} (mancano: {shortfall})."


def join_names(names: Sequence[str]) -> str:
    """«A», «A e B», «A, B e C»."""
    items = [name for name in names if name]
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} e {items[-1]}"


def athlete_not_in_roster_message(names: Sequence[str], *, left_roster: bool = False) -> str:
    """Formazione rifiutata perché schiera chi non è in rosa: il messaggio dice chi.

    «non è più nella tua rosa» solo con ``left_roster``, cioè se tutti i nominati in questa
    rosa ci sono stati davvero (ceduti, svincolati, tolti dall'admin). Per chi non c'è mai
    stato, es. un calciatore di un'altra squadra, il testo resta neutro: «non è nella tua
    rosa» (QA 19-20/11). Senza nomi (calciatore sconosciuto, o in rosa ma in esubero di
    ruolo) resta il messaggio generico.
    """
    unique = list(dict.fromkeys(name for name in names if name))
    if not unique:
        return ATHLETE_NOT_IN_ROSTER_MESSAGE
    if left_roster:
        verb = "non è più" if len(unique) == 1 else "non sono più"
    else:
        verb = "non è" if len(unique) == 1 else "non sono"
    return f"{join_names(unique)} {verb} nella tua rosa."


def lineup_athlete_left_roster_message(names: Sequence[str]) -> str:
    """Avviso per chi è stato tolto dalla formazione perché non è più in rosa."""
    unique = list(dict.fromkeys(name for name in names if name))
    if not unique:
        return (
            "Uno o più calciatori non sono più nella tua rosa: sono stati tolti dalla "
            "formazione, scegli chi mettere al loro posto."
        )
    if len(unique) == 1:
        return (
            f"{unique[0]} non è più nella tua rosa: è stato tolto dalla formazione, "
            "scegli chi mettere al suo posto."
        )
    return (
        f"{join_names(unique)} non sono più nella tua rosa: sono stati tolti dalla "
        "formazione, scegli chi mettere al loro posto."
    )


@dataclass(frozen=True)
class LeftRosterRemoval:
    """Chi è stato tolto dalla formazione perché non è più in rosa, per l'avviso di GET formazione.

    ``bench_replacements``: chi è salito nei primi ``BENCH_ACTIVE_SIZE`` della panchina al suo
    posto (la pulizia all'uscita, ``fantasy_lineups.departures``): il posto è già coperto. Vuoto
    per un titolare, per una panchina senza nessuno in tribuna da far salire, o quando non si sa.
    ``from_tribuna``: era oltre i primi ``BENCH_ACTIVE_SIZE``, non c'è un posto da coprire.
    """

    name: str
    bench_replacements: tuple[str, ...] = ()
    from_tribuna: bool = False


def lineup_athlete_left_roster_messages(removals: Sequence[LeftRosterRemoval]) -> list[str]:
    """Gli avvisi per chi è stato tolto dalla formazione perché non è più in rosa.

    Rosario, 20/11: quando il posto in panchina l'ha già coperto il sistema, l'avviso dice chi è
    salito, una frase per calciatore («X non è più nella tua rosa: al suo posto in panchina è
    salito Y.»). Chi lascia un posto da coprire (titolare, o nessuno da far salire in panchina)
    resta in una sola frase, «… scegli chi mettere al suo posto»
    (``lineup_athlete_left_roster_message``), e viene per prima: è l'unica che chiede qualcosa.
    Chi era in tribuna non lascia posti da coprire. Ogni calciatore compare una volta sola.
    """
    unique: list[LeftRosterRemoval] = []
    seen: set[str] = set()
    for removal in removals:
        if removal.name and removal.name in seen:
            continue
        seen.add(removal.name)
        # Senza nome (calciatore sconosciuto) l'avviso resta quello generico, da coprire.
        replacements = tuple(name for name in removal.bench_replacements if name)
        unique.append(
            LeftRosterRemoval(
                name=removal.name,
                bench_replacements=replacements if removal.name else (),
                from_tribuna=removal.from_tribuna and bool(removal.name),
            )
        )
    open_places = [
        removal.name
        for removal in unique
        if not removal.bench_replacements and not removal.from_tribuna
    ]
    messages = [lineup_athlete_left_roster_message(open_places)] if open_places else []
    for removal in unique:
        if not removal.bench_replacements:
            continue
        verb = "è salito" if len(removal.bench_replacements) == 1 else "sono saliti"
        messages.append(
            f"{removal.name} non è più nella tua rosa: al suo posto in panchina {verb} "
            f"{join_names(removal.bench_replacements)}."
        )
    tribuna = [
        removal.name
        for removal in unique
        if removal.from_tribuna and not removal.bench_replacements
    ]
    if len(tribuna) == 1:
        messages.append(f"{tribuna[0]} non è più nella tua rosa: è stato tolto dalla tribuna.")
    elif tribuna:
        messages.append(
            f"{join_names(tribuna)} non sono più nella tua rosa: sono stati tolti dalla tribuna."
        )
    return messages


def athlete_exceeds_role_quota_message(names: Sequence[str]) -> str:
    """Formazione rifiutata perché schiera chi è in esubero di ruolo: il messaggio dice chi."""
    unique = list(dict.fromkeys(name for name in names if name))
    if not unique:
        return (
            "Uno o più calciatori sono in esubero di ruolo: non possono essere schierati "
            "finché la rosa non torna in regola."
        )
    if len(unique) == 1:
        return (
            f"{unique[0]} è in esubero di ruolo: non può essere schierato finché la rosa "
            "non torna in regola."
        )
    return (
        f"{join_names(unique)} sono in esubero di ruolo: non possono essere schierati "
        "finché la rosa non torna in regola."
    )


def copied_athlete_exceeds_role_quota_message(names: Sequence[str]) -> str:
    """Avviso della copia: chi era schierato nel turno precedente ed è in esubero di ruolo."""
    unique = list(dict.fromkeys(name for name in names if name))
    if not unique:
        return (
            "Uno o più calciatori della formazione precedente sono in esubero di ruolo e sono "
            "stati esclusi."
        )
    if len(unique) == 1:
        return f"{unique[0]} è in esubero di ruolo ed è stato escluso dalla formazione copiata."
    return (
        f"{join_names(unique)} sono in esubero di ruolo e sono stati esclusi dalla formazione "
        "copiata."
    )


def athlete_role_unresolved_message(names: Sequence[str]) -> str:
    """Formazione rifiutata perché schiera chi non ha un ruolo nel listone: dice chi."""
    unique = list(dict.fromkeys(name for name in names if name))
    if not unique:
        return (
            "Uno o più calciatori non hanno un ruolo nel listone: non possono essere schierati "
            "finché non lo ricevono."
        )
    if len(unique) == 1:
        return (
            f"{unique[0]} non ha un ruolo nel listone: non può essere schierato finché non "
            "lo riceve."
        )
    return (
        f"{join_names(unique)} non hanno un ruolo nel listone: non possono essere schierati "
        "finché non lo ricevono."
    )


def copied_athlete_role_unresolved_message(names: Sequence[str]) -> str:
    """Avviso della copia: chi era schierato nel turno precedente e ora non ha un ruolo."""
    unique = list(dict.fromkeys(name for name in names if name))
    if not unique:
        return (
            "Uno o più calciatori della formazione precedente non hanno un ruolo nel listone e "
            "sono stati esclusi."
        )
    if len(unique) == 1:
        return (
            f"{unique[0]} non ha un ruolo nel listone ed è stato escluso dalla formazione copiata."
        )
    return (
        f"{join_names(unique)} non hanno un ruolo nel listone e sono stati esclusi dalla "
        "formazione copiata."
    )


def drop_role_quota_excess_from_tribuna[T](
    bench: Sequence[T],
    excess_athlete_ids: Iterable[object],
    *,
    key: Callable[[T], object] | None = None,
) -> list[T]:
    """Panchina senza chi è in esubero di ruolo dall'11° posto in poi (la tribuna).

    Web e app, anche le versioni già installate, mettono in coda alla panchina tutta la rosa,
    compreso chi è in esubero (``exceeds_role_quota``). In tribuna non entra mai nei cambi
    automatici: lo si toglie senza errore e non si salva (QA 19/11). Nei primi
    ``BENCH_ACTIVE_SIZE`` posti resta, e la validazione lo rifiuta con il nome
    (``athlete_exceeds_role_quota``). I posti si contano su quelli occupati, come la regola
    della panchina attiva; quelli vuoti di una bozza (``""``) restano dove sono. ``key`` dà
    l'id da confrontare con ``excess_athlete_ids`` (es. ``str`` per gli UUID).

    Stessa regola per chi non ha un ruolo nel listone (``athlete_role_unresolved``, 20/11): i
    chiamanti passano in ``excess_athlete_ids`` gli uni e gli altri.
    """
    excess = {item for item in excess_athlete_ids if item not in {None, ""}}
    if not excess:
        return list(bench)
    kept: list[T] = []
    filled = 0
    for item in bench:
        athlete_id = key(item) if key is not None else item
        if athlete_id in {None, ""}:
            kept.append(item)
            continue
        if filled >= BENCH_ACTIVE_SIZE and athlete_id in excess:
            continue
        filled += 1
        kept.append(item)
    return kept


def drop_departed_athletes(
    *,
    starter_ids: Sequence[object],
    bench_ids: Sequence[object],
    roster_athlete_ids: Iterable[object],
    locked_athlete_ids: Iterable[object] = (),
) -> DepartedLineupCleanup:
    """Toglie da titolari e panchina chi non è più in rosa (scambio, svincolo, asta, admin).

    Il posto di un titolare resta vuoto (``""``) invece di far scalare gli altri: i titolari
    sono posizionali sul modulo. In panchina chi resta mantiene l'ordine. Chi ha la partita
    già iniziata (``locked_athlete_ids``) resta dov'è: quella formazione conta già per il
    punteggio e non si cambia a posteriori. Funzione pura: decidere se e quando applicarla
    (solo turni ancora modificabili) spetta al chiamante.
    """
    roster = {item for item in roster_athlete_ids if item not in {None, ""}}
    locked = {item for item in locked_athlete_ids if item not in {None, ""}}

    def departed(athlete_id: object) -> bool:
        return (
            athlete_id not in {None, ""} and athlete_id not in roster and athlete_id not in locked
        )

    removed: list[object] = []
    starters: list[object] = []
    for athlete_id in starter_ids:
        if departed(athlete_id):
            removed.append(athlete_id)
            starters.append("")
        else:
            starters.append(athlete_id)
    bench: list[object] = []
    for athlete_id in bench_ids:
        if departed(athlete_id):
            removed.append(athlete_id)
        else:
            bench.append(athlete_id)
    return DepartedLineupCleanup(
        starter_ids=tuple(starters),
        bench_ids=tuple(bench),
        removed_ids=tuple(dict.fromkeys(removed)),
    )


def fill_starter_holes(
    *,
    module: str,
    starters: Sequence[tuple[int, LineupPlayerRef]],
) -> list[LineupPlayerRef]:
    """Titolari nell'ordine dei loro posti, con un riferimento vuoto dove il posto è libero.

    Chi esce dalla rosa viene tolto dalla formazione salvata dei turni non ancora iniziati e il
    suo posto resta vuoto: gli altri titolari tengono il loro ``sort_order`` (vedi
    ``fantasy_lineups.departures``). Il posto vuoto prende il ruolo che manca al modulo, così
    la validazione segnala lo slot da riempire (``missing_athlete``) e non un modulo sbagliato.
    Senza posti liberi restituisce i titolari così come sono, in ordine di posto.
    """
    ordered = sorted(starters, key=lambda item: item[0])
    by_position = dict(ordered)
    if len(by_position) != len(ordered) or not ordered:
        return [ref for _, ref in ordered]
    size = max(STARTER_COUNT, ordered[-1][0] + 1)
    if len(ordered) >= size:
        return [ref for _, ref in ordered]
    missing: list[FantasyRole] = []
    parsed = parse_module(module)
    if parsed is not None:
        expected = module_counts(parsed)
        present = count_roles([ref for _, ref in ordered])
        for role, wanted in (
            (FantasyRole.P, expected.goalkeepers),
            (FantasyRole.D, expected.defenders),
            (FantasyRole.C, expected.midfielders),
            (FantasyRole.A, expected.forwards),
        ):
            missing.extend([role] * max(0, wanted - present[role]))
    filled: list[LineupPlayerRef] = []
    for position in range(size):
        ref = by_position.get(position)
        if ref is None:
            ref = LineupPlayerRef(athlete_id="", role=missing.pop(0) if missing else None)
        filled.append(ref)
    return filled


#: Da dove arriva chi copre un posto vuoto all'inizio del turno.
TURN_START_FROM_BENCH = "bench"
TURN_START_FROM_TRIBUNA = "tribuna"


@dataclass(frozen=True)
class TurnStartHoleFill:
    """Un posto da titolare vuoto all'inizio del turno e come è stato coperto."""

    #: ``sort_order`` del posto tra i titolari.
    starter_position: int
    #: Il ruolo che manca al modulo in quel posto (``None``: modulo non leggibile).
    role: FantasyRole | None
    #: Chi è entrato tra i titolari; ``None`` se il posto resta vuoto.
    starter_athlete_id: object | None = None
    #: ``TURN_START_FROM_BENCH`` o ``TURN_START_FROM_TRIBUNA``; ``None`` se il posto resta vuoto.
    source: str | None = None
    #: Posizione in panchina (0-based, prima del cambio) di chi è entrato.
    from_bench_position: int | None = None
    #: Chi dalla tribuna ha preso in panchina il posto di chi è entrato.
    bench_athlete_id: object | None = None
    #: Il posto in panchina preso da ``bench_athlete_id`` (quello lasciato da chi è entrato).
    bench_position: int | None = None
    #: Posizione in panchina (0-based, prima del cambio) di ``bench_athlete_id``; ``None`` se
    #: non era nella formazione (in rosa ma non schierato).
    bench_from_position: int | None = None


@dataclass(frozen=True)
class TurnStartLineup:
    """Formazione dopo la regola di inizio turno (``fill_lineup_holes_at_turn_start``)."""

    #: Titolari come ``(sort_order, calciatore)``: gli altri tengono il loro posto.
    starters: tuple[tuple[int, LineupPlayerRef], ...]
    #: Panchina completa (panchina attiva e tribuna) nel nuovo ordine.
    bench: tuple[LineupPlayerRef, ...]
    #: Un elemento per ogni posto vuoto, in ordine di posto.
    fills: tuple[TurnStartHoleFill, ...]

    @property
    def changed(self) -> bool:
        return any(item.starter_athlete_id is not None for item in self.fills)


def fill_lineup_holes_at_turn_start(
    *,
    module: str,
    starters: Sequence[tuple[int, LineupPlayerRef]],
    bench: Sequence[LineupPlayerRef],
    outside: Sequence[LineupPlayerRef] = (),
    unavailable_ids: Iterable[object] = (),
) -> TurnStartLineup:
    """Copre i posti vuoti tra i titolari all'inizio del turno (decisione di Rosario del 19/11).

    Ogni posto vuoto ha il ruolo che manca al modulo (``fill_starter_holes``). In due passi:

    1. per ogni posto vuoto, in ordine di posto, entra il primo della panchina attiva (i primi
       ``BENCH_ACTIVE_SIZE``, in ordine di panchina) con quel ruolo; senza nessuno in panchina
       entra direttamente il primo della tribuna con quel ruolo; senza nessuno di quel ruolo il
       posto resta vuoto;
    2. poi, per ogni panchinaro entrato, il primo della tribuna con lo stesso ruolo prende il
       suo posto in panchina. Stesso ruolo nello stesso posto: la quota per ruolo della
       panchina attiva non cambia e gli altri non si spostano, quindi non serve mai metterlo in
       coda. Senza nessuno in tribuna la panchina si ricompatta.

    Con due posti vuoti dello stesso ruolo entrano i primi due panchinari di quel ruolo, e i
    primi due della tribuna salgono ai loro posti: l'ordine scelto dal fantallenatore conta.

    La tribuna è nell'ordine mostrato da web e app («Altri N in tribuna»): prima la panchina
    salvata dall'11° posto in poi, poi chi è in rosa ma non è nella formazione (``outside``,
    nell'ordine degli slot della rosa). Non entra chi è in ``unavailable_ids`` (esubero di
    ruolo, ruolo non risolto, nessun voto possibile in questo turno), né chi non ha un ruolo.

    Funzione pura e deterministica: niente blocchi per partita, così l'esito non dipende da
    quando gira; decidere se e quando applicarla spetta al chiamante
    (``fantasy_lineups.turn_start``).
    """
    unavailable = {item for item in unavailable_ids if item not in {None, ""}}
    present = [(position, ref) for position, ref in starters if ref.athlete_id not in {None, ""}]
    slots = fill_starter_holes(module=module, starters=present)
    holes = [(position, ref.role) for position, ref in enumerate(slots) if ref.athlete_id == ""]
    final_starters: dict[int, LineupPlayerRef] = dict(present)
    if not holes:
        return TurnStartLineup(
            starters=tuple(sorted(final_starters.items(), key=lambda item: item[0])),
            bench=tuple(bench),
            fills=(),
        )
    original_position = {ref.athlete_id: index for index, ref in enumerate(bench)}
    # Le prime ``BENCH_ACTIVE_SIZE`` posizioni non cambiano durante i due passi (chi entra resta
    # al suo posto fino alla fine); la tribuna è tutto il resto, nel suo ordine.
    active = list(bench[:BENCH_ACTIVE_SIZE])
    tribuna = list(bench[BENCH_ACTIVE_SIZE:])
    spare = [ref for ref in outside if ref.athlete_id not in {None, ""}]
    used: set[object] = set()

    def usable(ref: LineupPlayerRef, role: FantasyRole) -> bool:
        return (
            ref.athlete_id not in {None, ""}
            and ref.athlete_id not in unavailable
            and ref.athlete_id not in used
            and ref.role is not None
            and ref.role == role
        )

    def take_from_tribuna(role: FantasyRole) -> LineupPlayerRef | None:
        for pool in (tribuna, spare):
            index = next((i for i, ref in enumerate(pool) if usable(ref, role)), None)
            if index is not None:
                ref = pool.pop(index)
                used.add(ref.athlete_id)
                return ref
        return None

    # 1. I posti vuoti: prima la panchina attiva, poi la tribuna.
    entered: dict[int, tuple[LineupPlayerRef, str | None, int | None]] = {}
    for position, role in holes:
        if role is None:
            continue
        bench_index = next((i for i, ref in enumerate(active) if usable(ref, role)), None)
        if bench_index is not None:
            promoted = active[bench_index]
            used.add(promoted.athlete_id)
            final_starters[position] = promoted
            entered[position] = (promoted, TURN_START_FROM_BENCH, bench_index)
            continue
        direct = take_from_tribuna(role)
        if direct is not None:
            final_starters[position] = direct
            entered[position] = (direct, TURN_START_FROM_TRIBUNA, None)

    # 2. In panchina, al posto di ogni panchinaro entrato, il primo della tribuna dello stesso
    # ruolo; dove non c'è nessuno il posto si libera e la panchina si ricompatta.
    refills: dict[int, LineupPlayerRef] = {}
    for position, _ in holes:
        item = entered.get(position)
        if item is None or item[1] != TURN_START_FROM_BENCH:
            continue
        promoted, _, bench_index = item
        assert bench_index is not None and promoted.role is not None
        refill = take_from_tribuna(promoted.role)
        if refill is not None:
            refills[position] = refill
            active[bench_index] = refill
    promoted_ids = {
        item[0].athlete_id for item in entered.values() if item[1] == TURN_START_FROM_BENCH
    }
    final_bench = [ref for ref in active if ref.athlete_id not in promoted_ids] + tribuna
    final_position = {ref.athlete_id: index for index, ref in enumerate(final_bench)}

    fills: list[TurnStartHoleFill] = []
    for position, role in holes:
        item = entered.get(position)
        if item is None:
            fills.append(TurnStartHoleFill(starter_position=position, role=role))
            continue
        ref, source, _ = item
        refill = refills.get(position)
        fills.append(
            TurnStartHoleFill(
                starter_position=position,
                role=role,
                starter_athlete_id=ref.athlete_id,
                source=source,
                from_bench_position=original_position.get(ref.athlete_id),
                bench_athlete_id=refill.athlete_id if refill is not None else None,
                bench_position=final_position[refill.athlete_id] if refill is not None else None,
                bench_from_position=(
                    original_position.get(refill.athlete_id) if refill is not None else None
                ),
            )
        )
    return TurnStartLineup(
        starters=tuple(sorted(final_starters.items(), key=lambda item: item[0])),
        bench=tuple(final_bench),
        fills=tuple(fills),
    )


def turn_start_role_label(role: FantasyRole | None) -> str:
    """«difensore», «portiere»…: il ruolo al singolare per gli avvisi."""
    if role is None:
        return "titolare"
    return _BENCH_ROLE_LABELS[role][0]


def evaluate_lineup(
    *,
    module: str,
    starters: Sequence[LineupPlayerRef],
    bench: Sequence[LineupPlayerRef],
    roster_athlete_ids: Sequence[object],
    strict: bool = True,
    athlete_names: Mapping[object, str] | None = None,
    excess_athlete_ids: Iterable[object] = (),
    left_roster_athlete_ids: Iterable[object] = (),
    role_unresolved_athlete_ids: Iterable[object] = (),
    unfieldable_athlete_ids: Iterable[object] = (),
) -> LineupEvaluation:
    """Validate 7 modules, 1 GK, 11 starters, P–D–C–A counts and roster membership.

    Drafts may pass ``strict=False`` to allow incomplete XI/panchina (EP06-06).

    ``unfieldable_athlete_ids``: chi di sicuro non prende il voto in questo turno (nessuna
    partita, partita rinviata, indisponibilità confermata: ``selectionBlocked`` di web e app).
    Non alza la quota per ruolo dei primi ``BENCH_ACTIVE_SIZE`` della panchina: la quota chiede
    ``min(quota, panchinari schierabili di quel ruolo)`` (Rosario, 20/11: con l'unico terzo
    attaccante senza partita la quota chiedeva 3 attaccanti nei primi 10, e web e app, che lo
    tengono in coda, non riuscivano mai a soddisfarla). Nei primi 10 conta comunque: la regola
    può solo diventare meno severa.
    ``athlete_names`` (stesse chiavi degli id passati) serve solo ai messaggi di
    ``athlete_not_in_roster``, ``athlete_exceeds_role_quota`` e ``athlete_role_unresolved``:
    chi non è in rosa, è in esubero di ruolo o non ha un ruolo viene nominato.
    ``left_roster_athlete_ids``: chi, tra quelli fuori rosa, in questa rosa c'è stato davvero;
    solo se lo sono tutti il messaggio dice «non è più».

    ``excess_athlete_ids``: chi è in rosa ma in esubero di ruolo (fuori da
    ``roster_athlete_ids``). In tribuna non conta (vedi `drop_role_quota_excess_from_tribuna`),
    titolare o nei primi ``BENCH_ACTIVE_SIZE`` della panchina dà ``athlete_exceeds_role_quota``.
    ``role_unresolved_athlete_ids``: chi è in rosa ma senza ruolo nel listone (anche lui fuori
    da ``roster_athlete_ids``), stessa regola con ``athlete_role_unresolved``.
    """
    issues: list[LineupIssue] = []
    parsed = parse_module(module)
    excess = {item for item in excess_athlete_ids if item not in {None, ""}}
    unresolved = {item for item in role_unresolved_athlete_ids if item not in {None, ""}}
    bench = drop_role_quota_excess_from_tribuna(
        bench, excess | unresolved, key=lambda ref: ref.athlete_id
    )
    starter_role_counts = count_roles(starters)

    if parsed is None:
        issues.append(
            LineupIssue(
                code="invalid_module",
                message="Modulo non ammesso. Scegli uno dei sette moduli validi.",
            )
        )

    starter_ids = [player.athlete_id for player in starters]
    bench_ids = [player.athlete_id for player in bench]
    all_ids = [*starter_ids, *bench_ids]
    seen: set[object] = set()
    missing_slot = False
    duplicate = False
    for athlete_id in all_ids:
        if athlete_id is None or athlete_id == "":
            missing_slot = True
            continue
        if athlete_id in seen:
            duplicate = True
        seen.add(athlete_id)
    if missing_slot and strict:
        issues.append(
            LineupIssue(
                code="missing_athlete",
                message="Ogni slot della formazione deve contenere un calciatore.",
            )
        )
    if duplicate:
        issues.append(
            LineupIssue(
                code="duplicate_athlete",
                message="Lo stesso calciatore non può comparire più di una volta in formazione.",
            )
        )

    names = athlete_names or {}
    # Tolto chi è in tribuna, chi resta in esubero è titolare o nei primi 10 della panchina.
    fielded_excess = [athlete_id for athlete_id in all_ids if athlete_id in excess]
    if fielded_excess:
        issues.append(
            LineupIssue(
                code=ATHLETE_EXCEEDS_ROLE_QUOTA_CODE,
                message=athlete_exceeds_role_quota_message(
                    [names[athlete_id] for athlete_id in fielded_excess if athlete_id in names]
                ),
            )
        )
    # Lo stesso per chi non ha un ruolo nel listone: tolto dalla tribuna, altrove si nomina.
    fielded_unresolved = [athlete_id for athlete_id in all_ids if athlete_id in unresolved]
    if fielded_unresolved:
        issues.append(
            LineupIssue(
                code=ATHLETE_ROLE_UNRESOLVED_CODE,
                message=athlete_role_unresolved_message(
                    [names[athlete_id] for athlete_id in fielded_unresolved if athlete_id in names]
                ),
            )
        )

    roster_set = {item for item in roster_athlete_ids if item not in {None, ""}}
    outside_roster = [
        athlete_id
        for athlete_id in all_ids
        if athlete_id not in {None, ""}
        and athlete_id not in roster_set
        and athlete_id not in excess
        and athlete_id not in unresolved
    ]
    if outside_roster:
        left_roster = {item for item in left_roster_athlete_ids if item not in {None, ""}}
        issues.append(
            LineupIssue(
                code="athlete_not_in_roster",
                message=athlete_not_in_roster_message(
                    [names[athlete_id] for athlete_id in outside_roster if athlete_id in names],
                    left_roster=all(athlete_id in left_roster for athlete_id in outside_roster),
                ),
            )
        )

    filled_starters = (
        starters
        if strict
        else [player for player in starters if player.athlete_id not in {None, ""}]
    )
    filled_bench = (
        bench if strict else [player for player in bench if player.athlete_id not in {None, ""}]
    )
    # Chi è già nominato da ``athlete_role_unresolved`` non si ripete nel messaggio generico.
    if any(
        player.role is None and player.athlete_id not in unresolved
        for player in (*filled_starters, *filled_bench)
    ):
        issues.append(
            LineupIssue(
                code="unresolved_role",
                message="Uno o più calciatori non hanno un ruolo listone risolvibile (P–D–C–A).",
            )
        )

    if strict and len(starters) != STARTER_COUNT:
        issues.append(
            LineupIssue(
                code="starter_count_invalid",
                message=(
                    f"La formazione deve avere esattamente {STARTER_COUNT} titolari "
                    f"(attuali: {len(starters)})."
                ),
            )
        )

    if strict and starter_role_counts[FantasyRole.P] != GOALKEEPER_STARTERS:
        issues.append(
            LineupIssue(
                code="goalkeeper_count_invalid",
                message=(
                    f"Serve esattamente {GOALKEEPER_STARTERS} portiere titolare "
                    f"(attuali: {starter_role_counts[FantasyRole.P]})."
                ),
            )
        )

    if strict and parsed is not None:
        expected = module_counts(parsed)
        if (
            starter_role_counts[FantasyRole.D] != expected.defenders
            or starter_role_counts[FantasyRole.C] != expected.midfielders
            or starter_role_counts[FantasyRole.A] != expected.forwards
        ):
            issues.append(
                LineupIssue(
                    code="module_role_mismatch",
                    message=(
                        f"Il modulo {parsed.value} richiede "
                        f"{expected.defenders}D–{expected.midfielders}C–{expected.forwards}A "
                        "titolari "
                        f"(attuali: {starter_role_counts[FantasyRole.D]}D–"
                        f"{starter_role_counts[FantasyRole.C]}C–"
                        f"{starter_role_counts[FantasyRole.A]}A)."
                    ),
                )
            )

    if not strict:
        # Bozza: può essere incompleta, ma non oltre i massimi (QA 18/11: si
        # salvavano 20 titolari o 2 portieri).
        if len(filled_starters) > STARTER_COUNT:
            issues.append(
                LineupIssue(
                    code="starter_count_invalid",
                    message=(
                        f"La formazione può avere al massimo {STARTER_COUNT} titolari "
                        f"(attuali: {len(filled_starters)})."
                    ),
                )
            )
        if starter_role_counts[FantasyRole.P] > GOALKEEPER_STARTERS:
            issues.append(
                LineupIssue(
                    code="goalkeeper_count_invalid",
                    message=(
                        f"Puoi schierare al massimo {GOALKEEPER_STARTERS} portiere titolare "
                        f"(attuali: {starter_role_counts[FantasyRole.P]})."
                    ),
                )
            )
        if parsed is not None:
            expected = module_counts(parsed)
            if (
                starter_role_counts[FantasyRole.D] > expected.defenders
                or starter_role_counts[FantasyRole.C] > expected.midfielders
                or starter_role_counts[FantasyRole.A] > expected.forwards
            ):
                issues.append(
                    LineupIssue(
                        code="module_role_mismatch",
                        message=(
                            f"Il modulo {parsed.value} ammette al massimo "
                            f"{expected.defenders}D–{expected.midfielders}C–"
                            f"{expected.forwards}A titolari "
                            f"(attuali: {starter_role_counts[FantasyRole.D]}D–"
                            f"{starter_role_counts[FantasyRole.C]}C–"
                            f"{starter_role_counts[FantasyRole.A]}A)."
                        ),
                    )
                )

    if strict and filled_bench:
        unfieldable = {item for item in unfieldable_athlete_ids if item not in {None, ""}}
        required = bench_active_role_requirements(
            [player for player in filled_bench if player.athlete_id not in unfieldable]
        )
        active_slots = filled_bench[:BENCH_ACTIVE_SIZE]
        active_role_counts = count_roles(active_slots)
        missing = {
            role: needed - active_role_counts.get(role, 0)
            for role, needed in required.items()
            if active_role_counts.get(role, 0) < needed
        }
        if missing:
            issues.append(
                LineupIssue(
                    code="bench_roles_invalid",
                    message=_bench_role_shortfall_message(missing),
                )
            )

    unused = [item for item in roster_athlete_ids if item not in {None, ""} and item not in seen]
    if unused and strict:
        issues.append(
            LineupIssue(
                code="bench_incomplete",
                message=(
                    "Tutti i calciatori in rosa devono essere schierati: "
                    f"mancano {len(unused)} in panchina."
                ),
            )
        )

    unique: list[LineupIssue] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in issues:
        key = (item.code, item.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(item)

    return LineupEvaluation(
        valid=not unique,
        issues=tuple(unique),
        starter_counts={role.value: starter_role_counts[role] for role in FantasyRole},
    )


def is_athlete_kickoff_locked(
    *,
    now: datetime,
    kickoff_at: datetime | None,
    status_short: str | None = None,
    lock_latched: bool = False,
    margin_minutes: int = 0,
) -> bool:
    """True when the athlete's real match has started, or is about to.

    ``lock_latched`` keeps the player frozen after a postponement or kickoff
    change that arrives only after the previously published time elapsed.

    ``margin_minutes`` anticipates the lock instant (formazione a step,
    EP-turni-automazione): a player still locks individually at his own real
    kickoff, just with a configurable preavviso instead of exactly at it. 0
    reproduces the previous exact-kickoff behavior.
    """
    if lock_latched:
        return True
    status = (status_short or "").strip().upper()
    if status in STARTED_FIXTURE_STATUSES:
        return True
    if status in INACTIVE_FIXTURE_STATUSES:
        return False
    if kickoff_at is None:
        return False
    threshold = ensure_utc(kickoff_at) - timedelta(minutes=margin_minutes)
    return ensure_utc(now) >= threshold


def next_unlocked_kickoff(
    kickoffs: Iterable[tuple[datetime | None, str | None, bool]],
    *,
    now: datetime,
    margin_minutes: int,
) -> datetime | None:
    """Kickoff più vicino tra i candidati non ancora bloccati (EP-turni-automazione).

    Ogni voce è ``(kickoff_at, status_short, lock_latched)`` — la stessa
    forma di ``_KickoffRef``. Riusa ``is_athlete_kickoff_locked`` così il
    "prossimo blocco" resta sempre coerente con la regola che decide se un
    giocatore è già bloccato. Voci senza kickoff risolvibile (bye, club non
    mappato) non sono candidate né bloccanti.
    """
    candidates = [
        kickoff_at
        for kickoff_at, status_short, lock_latched in kickoffs
        if kickoff_at is not None
        and not is_athlete_kickoff_locked(
            now=now,
            kickoff_at=kickoff_at,
            status_short=status_short,
            lock_latched=lock_latched,
            margin_minutes=margin_minutes,
        )
    ]
    return min(candidates) if candidates else None


def evaluate_progressive_lock(
    *,
    previous_slots: Mapping[object, str],
    proposed_slots: Mapping[object, str],
    locked_athlete_ids: Iterable[object],
) -> tuple[LineupIssue, ...]:
    """Reject slot changes for athletes whose kickoff has already started."""
    issues: list[LineupIssue] = []
    for athlete_id in locked_athlete_ids:
        previous = previous_slots.get(athlete_id)
        proposed = proposed_slots.get(athlete_id)
        if previous is None:
            if proposed == LineupSlotKind.STARTER.value:
                issues.append(
                    LineupIssue(
                        code="athlete_kickoff_locked",
                        message=(
                            "Uno o più calciatori non sono più modificabili: "
                            "la loro partita è già iniziata."
                        ),
                    )
                )
            continue
        if proposed != previous:
            issues.append(
                LineupIssue(
                    code="athlete_kickoff_locked",
                    message=(
                        "Uno o più calciatori non sono più modificabili: "
                        "la loro partita è già iniziata."
                    ),
                )
            )
    unique: list[LineupIssue] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in issues:
        key = (item.code, item.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(item)
    return tuple(unique)


def assert_progressive_lock(
    *,
    previous_slots: Mapping[object, str],
    proposed_slots: Mapping[object, str],
    locked_athlete_ids: Iterable[object],
) -> None:
    from auth.exceptions import ValidationAuthError

    issues = evaluate_progressive_lock(
        previous_slots=previous_slots,
        proposed_slots=proposed_slots,
        locked_athlete_ids=locked_athlete_ids,
    )
    if not issues:
        return
    first = issues[0]
    raise ValidationAuthError(first.message, code=first.code)


def is_lineup_modification_allowed(*, stored: FantasyTurnStatus) -> bool:
    """Turn-level gate: progressive edits stay open on open/locked turns (EP06-03)."""
    return stored in {FantasyTurnStatus.OPEN, FantasyTurnStatus.LOCKED}


def assert_lineup_modification_allowed(*, stored: FantasyTurnStatus) -> None:
    from auth.exceptions import ValidationAuthError

    if stored == FantasyTurnStatus.SCHEDULED:
        raise ValidationAuthError(
            "Il turno non è ancora aperto: la formazione si schiera dopo l'apertura.",
            code="turn_not_open",
        )
    if stored == FantasyTurnStatus.SKIPPED:
        raise ValidationAuthError(
            "Il turno non è stato disputato e la formazione non può essere modificata.",
            code="turn_skipped",
        )
    if is_lineup_modification_allowed(stored=stored):
        return
    raise ValidationAuthError(
        "Modifica fuori tempo: il turno non accetta più cambiamenti di formazione.",
        code="turn_modification_closed",
    )


def remaining_roster_for_bench(
    roster_athlete_ids: Sequence[object],
    starter_athlete_ids: Sequence[object],
) -> list[object]:
    used = {item for item in starter_athlete_ids if item not in {None, ""}}
    return [item for item in roster_athlete_ids if item not in {None, ""} and item not in used]


def ordered_bench_from_roster(
    roster_athlete_ids: Sequence[object],
    starter_athlete_ids: Sequence[object],
    previous_bench_order: Sequence[object] | None = None,
) -> list[object]:
    remaining = remaining_roster_for_bench(roster_athlete_ids, starter_athlete_ids)
    remaining_set = set(remaining)
    ordered: list[object] = []
    for athlete_id in previous_bench_order or ():
        if athlete_id in remaining_set:
            ordered.append(athlete_id)
            remaining_set.discard(athlete_id)
    for athlete_id in remaining:
        if athlete_id in remaining_set:
            ordered.append(athlete_id)
    return ordered


def _dedupe_issues(issues: Sequence[LineupIssue]) -> tuple[LineupIssue, ...]:
    unique: list[LineupIssue] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in issues:
        key = (item.code, item.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(item)
    return tuple(unique)


def evaluate_bench_order_lock(
    *,
    previous_bench: Sequence[object],
    proposed_bench: Sequence[object],
    locked_athlete_ids: Iterable[object],
    role_by_athlete_id: Mapping[object, object] | None = None,
) -> tuple[LineupIssue, ...]:
    """Reject bench-order changes that cross a locked player (no retroactive advantage).

    Ogni bloccato resta al suo numero e davanti a lui non diminuiscono i pari ruolo.
    Eccezioni, purché ogni bloccato resti nella sua posizione: chi entra in panchina prende
    il posto esatto di un pari ruolo uscito (scambio 1:1), oppure dopo di lui non ci sono
    bloccati del suo stesso ruolo (es. cambio modulo). Nessun vantaggio retroattivo: i cambi
    automatici vanno solo a parità di ruolo.
    """
    locked = {item for item in locked_athlete_ids if item not in {None, ""}}
    previous = [item for item in previous_bench if item not in {None, ""}]
    proposed = [item for item in proposed_bench if item not in {None, ""}]
    if not locked or not previous:
        return ()

    previous_set = set(previous)
    proposed_set = set(proposed)
    common = [item for item in previous if item in proposed_set]
    locked_remaining = [item for item in previous if item in locked and item in proposed_set]
    issues: list[LineupIssue] = []

    for locked_id in locked_remaining:
        previous_index = previous.index(locked_id)
        proposed_index = proposed.index(locked_id)
        crossed = False
        for other in common:
            if other == locked_id:
                continue
            was_before = previous.index(other) < previous_index
            now_before = proposed.index(other) < proposed_index
            if was_before != now_before:
                crossed = True
                break
        if crossed:
            issues.append(
                LineupIssue(code="bench_order_locked", message=BENCH_ORDER_LOCKED_MESSAGE)
            )
            break

    # Il bloccato tiene il suo numero (panchina o tribuna) e davanti a lui non diminuiscono i
    # pari ruolo: altrimenti, con un cambio modulo, guadagnerebbe priorità nei cambi automatici.
    for locked_id in locked_remaining if not issues else []:
        previous_index = previous.index(locked_id)
        proposed_index = proposed.index(locked_id)
        if previous_index != proposed_index or _same_role_ahead(
            proposed, proposed_index, locked_id, role_by_athlete_id
        ) < _same_role_ahead(previous, previous_index, locked_id, role_by_athlete_id):
            issues.append(
                LineupIssue(code="bench_order_locked", message=BENCH_ORDER_LOCKED_MESSAGE)
            )
            break

    if locked_remaining and not issues:
        last_locked_proposed = max(proposed.index(item) for item in locked_remaining)
        locked_keep_position = all(
            previous.index(item) == proposed.index(item) for item in locked_remaining
        )
        for index, athlete_id in enumerate(proposed):
            if athlete_id in previous_set or index >= last_locked_proposed:
                continue
            if locked_keep_position and (
                _replaces_same_role_slot(
                    index=index,
                    athlete_id=athlete_id,
                    previous=previous,
                    proposed_set=proposed_set,
                    role_by_athlete_id=role_by_athlete_id,
                )
                or _no_locked_same_role_after(
                    index=index,
                    athlete_id=athlete_id,
                    proposed=proposed,
                    locked=locked,
                    role_by_athlete_id=role_by_athlete_id,
                )
            ):
                continue
            issues.append(
                LineupIssue(code="bench_order_locked", message=BENCH_ORDER_LOCKED_MESSAGE)
            )
            break

    return _dedupe_issues(issues)


def _same_role_ahead(
    bench: Sequence[object],
    index: int,
    athlete_id: object,
    role_by_athlete_id: Mapping[object, object] | None,
) -> int:
    if role_by_athlete_id is None:
        return 0
    role = role_by_athlete_id.get(athlete_id)
    if role is None:
        return 0
    return sum(1 for item in bench[:index] if role_by_athlete_id.get(item) == role)


def _no_locked_same_role_after(
    *,
    index: int,
    athlete_id: object,
    proposed: Sequence[object],
    locked: set[object],
    role_by_athlete_id: Mapping[object, object] | None,
) -> bool:
    """True se dopo `index` non c'è un bloccato dello stesso ruolo di chi entra.

    I cambi automatici vanno solo a parità di ruolo: chi entra davanti a bloccati di altri
    ruoli non cambia la priorità di nessun bloccato (nessun vantaggio retroattivo).
    """
    if role_by_athlete_id is None:
        return False
    role = role_by_athlete_id.get(athlete_id)
    if role is None:
        return False
    return not any(
        item in locked and role_by_athlete_id.get(item) == role for item in proposed[index + 1 :]
    )


def _replaces_same_role_slot(
    *,
    index: int,
    athlete_id: object,
    previous: Sequence[object],
    proposed_set: set[object],
    role_by_athlete_id: Mapping[object, object] | None,
) -> bool:
    """True se `athlete_id` prende il posto di un pari ruolo uscito dalla panchina."""
    if role_by_athlete_id is None or index >= len(previous):
        return False
    departed = previous[index]
    if departed in proposed_set:
        return False
    incoming_role = role_by_athlete_id.get(athlete_id)
    return incoming_role is not None and incoming_role == role_by_athlete_id.get(departed)


def assert_bench_order_lock(
    *,
    previous_bench: Sequence[object],
    proposed_bench: Sequence[object],
    locked_athlete_ids: Iterable[object],
    role_by_athlete_id: Mapping[object, object] | None = None,
) -> None:
    from auth.exceptions import ValidationAuthError

    issues = evaluate_bench_order_lock(
        previous_bench=previous_bench,
        proposed_bench=proposed_bench,
        locked_athlete_ids=locked_athlete_ids,
        role_by_athlete_id=role_by_athlete_id,
    )
    if not issues:
        return
    first = issues[0]
    raise ValidationAuthError(first.message, code=first.code)


def resolve_automatic_substitutions(
    *,
    module: str,
    starters: Sequence[LineupPlayerRef],
    bench: Sequence[LineupPlayerRef],
    played_athlete_ids: Sequence[object],
    max_substitutions: int = MAX_AUTOMATIC_SUBSTITUTIONS,
) -> SubstitutionResolution:
    """Apply up to ``max_substitutions`` same-role substitutions (FR-SUB-01).

    ``played_athlete_ids`` identifies starters/bench players with a valid
    statistical vote (EP07-02 eligibility): a titolare "senza voto" is
    replaced by the first compatible bench player with a vote, walking the
    bench in its saved order. Every bench candidate not used is reported in
    ``skipped`` with the reason, so the result explains "chi è entrato, per
    chi e perché gli altri sono stati saltati".
    """
    # Entrano solo i primi BENCH_ACTIVE_SIZE della panchina: chi è in tribuna resta fuori dal
    # turno, come nel calcio reale (decisione del 08/11/2026).
    bench = list(bench)[:BENCH_ACTIVE_SIZE]
    played = {item for item in played_athlete_ids if item not in {None, ""}}
    substitutions: list[AutomaticSubstitution] = []
    skipped: list[SkippedBenchCandidate] = []
    replaced: set[object] = set()
    effective = [player.athlete_id for player in starters]
    role_by_id: dict[object, FantasyRole | None] = {}
    for player in [*starters, *bench]:
        if player.athlete_id not in {None, ""}:
            role_by_id[player.athlete_id] = player.role

    for bench_player in bench:
        if bench_player.athlete_id in {None, ""}:
            continue
        if len(substitutions) >= max_substitutions:
            skipped.append(
                SkippedBenchCandidate(
                    athlete_id=bench_player.athlete_id,
                    role=bench_player.role,
                    reason="limit_reached",
                )
            )
            continue
        if bench_player.athlete_id not in played:
            skipped.append(
                SkippedBenchCandidate(
                    athlete_id=bench_player.athlete_id,
                    role=bench_player.role,
                    reason="not_eligible",
                )
            )
            continue
        if bench_player.role is None:
            skipped.append(
                SkippedBenchCandidate(
                    athlete_id=bench_player.athlete_id,
                    role=None,
                    reason="role_unresolved",
                )
            )
            continue
        starter_index = next(
            (
                index
                for index, starter in enumerate(starters)
                if starter.athlete_id not in {None, ""}
                and starter.athlete_id not in replaced
                and starter.role == bench_player.role
                and starter.athlete_id not in played
            ),
            None,
        )
        if starter_index is None:
            skipped.append(
                SkippedBenchCandidate(
                    athlete_id=bench_player.athlete_id,
                    role=bench_player.role,
                    reason="no_compatible_starter",
                )
            )
            continue
        outgoing = starters[starter_index]
        replaced.add(outgoing.athlete_id)
        effective[starter_index] = bench_player.athlete_id
        substitutions.append(
            AutomaticSubstitution(
                out_athlete_id=outgoing.athlete_id,
                in_athlete_id=bench_player.athlete_id,
                role=bench_player.role,
                order=len(substitutions) + 1,
            )
        )

    parsed = parse_module(module)
    module_valid = False
    if parsed is not None:
        expected = module_counts(parsed)
        counts = count_roles(
            [
                LineupPlayerRef(athlete_id=athlete_id, role=role_by_id.get(athlete_id))
                for athlete_id in effective
            ]
        )
        module_valid = (
            counts[FantasyRole.P] == expected.goalkeepers
            and counts[FantasyRole.D] == expected.defenders
            and counts[FantasyRole.C] == expected.midfielders
            and counts[FantasyRole.A] == expected.forwards
        )

    return SubstitutionResolution(
        substitutions=tuple(substitutions),
        effective_starter_ids=tuple(effective),
        module_valid=module_valid,
        skipped=tuple(skipped),
    )


def lineup_signature(
    *,
    module: str,
    starter_ids: Sequence[object],
    bench_ids: Sequence[object],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Stable fingerprint of a saved formation (module + ordered slots)."""
    return (
        str(module),
        tuple(str(item) for item in starter_ids if item not in {None, ""}),
        tuple(str(item) for item in bench_ids if item not in {None, ""}),
    )


def is_tactical_window_active(*, any_athlete_locked: bool) -> bool:
    """Moves start after at least one real kickoff has locked a roster player."""
    return bool(any_athlete_locked)


def remaining_tactical_moves(*, used: int, maximum: int = MAX_TACTICAL_MOVES) -> int:
    return max(0, maximum - max(0, used))


def evaluate_tactical_move(
    *,
    has_saved_lineup: bool,
    any_athlete_locked: bool,
    moves_used: int,
    proposed_module: str,
    proposed_starter_ids: Sequence[object],
    proposed_bench_ids: Sequence[object],
    previous_module: str | None = None,
    previous_starter_ids: Sequence[object] | None = None,
    previous_bench_ids: Sequence[object] | None = None,
    maximum: int = MAX_TACTICAL_MOVES,
) -> TacticalMoveEvaluation:
    """One confirmed save in the progressive window consumes one of three moves.

    The initial formation (FR-FOR-01) and identical re-saves do not consume.
    Automatic substitutions are out of this engine and never consume a move.
    A composed save (module + unlocked swaps + bench order) counts as one move.
    """
    changed = False
    if has_saved_lineup:
        changed = lineup_signature(
            module=proposed_module,
            starter_ids=proposed_starter_ids,
            bench_ids=proposed_bench_ids,
        ) != lineup_signature(
            module=previous_module or "",
            starter_ids=previous_starter_ids or (),
            bench_ids=previous_bench_ids or (),
        )
    would_consume = bool(
        has_saved_lineup
        and is_tactical_window_active(any_athlete_locked=any_athlete_locked)
        and changed
    )
    issues: list[LineupIssue] = []
    if would_consume and moves_used >= maximum:
        issues.append(
            LineupIssue(
                code="tactical_moves_exhausted",
                message=TACTICAL_MOVES_EXHAUSTED_MESSAGE,
            )
        )
    remaining_after = remaining_tactical_moves(
        used=moves_used + (1 if would_consume else 0),
        maximum=maximum,
    )
    return TacticalMoveEvaluation(
        would_consume=would_consume,
        remaining_after=remaining_after,
        issues=_dedupe_issues(issues),
    )


def assert_tactical_move(
    *,
    has_saved_lineup: bool,
    any_athlete_locked: bool,
    moves_used: int,
    proposed_module: str,
    proposed_starter_ids: Sequence[object],
    proposed_bench_ids: Sequence[object],
    previous_module: str | None = None,
    previous_starter_ids: Sequence[object] | None = None,
    previous_bench_ids: Sequence[object] | None = None,
    maximum: int = MAX_TACTICAL_MOVES,
) -> TacticalMoveEvaluation:
    from auth.exceptions import ValidationAuthError

    evaluation = evaluate_tactical_move(
        has_saved_lineup=has_saved_lineup,
        any_athlete_locked=any_athlete_locked,
        moves_used=moves_used,
        proposed_module=proposed_module,
        proposed_starter_ids=proposed_starter_ids,
        proposed_bench_ids=proposed_bench_ids,
        previous_module=previous_module,
        previous_starter_ids=previous_starter_ids,
        previous_bench_ids=previous_bench_ids,
        maximum=maximum,
    )
    if not evaluation.issues:
        return evaluation
    first = evaluation.issues[0]
    raise ValidationAuthError(first.message, code=first.code)


def copy_previous_lineup(
    *,
    previous_module: str,
    previous_starter_ids: Sequence[object],
    previous_bench_ids: Sequence[object],
    roster_athlete_ids: Sequence[object],
    locked_athlete_ids: Iterable[object] | None = None,
    current_confirmed_slots: Mapping[object, str] | None = None,
    current_confirmed_bench: Sequence[object] | None = None,
    role_by_athlete_id: Mapping[object, FantasyRole | None] | None = None,
    excess_athlete_ids: Iterable[object] = (),
    athlete_names: Mapping[object, str] | None = None,
    role_unresolved_athlete_ids: Iterable[object] = (),
) -> CopyLineupResult:
    """Revalidate a previous lineup against current roster and kickoff availability.

    Chi oggi è in esubero di ruolo (``excess_athlete_ids``, fuori da ``roster_athlete_ids``)
    resta fuori dalla copia come chi non è più in rosa: se era in tribuna senza avviso, se era
    titolare o nei primi 10 della panchina con un avviso che lo nomina (``athlete_names``).
    Lo stesso per chi oggi non ha un ruolo nel listone (``role_unresolved_athlete_ids``), con
    l'avviso ``copied_athlete_role_unresolved``.
    """
    roster_set = {item for item in roster_athlete_ids if item not in {None, ""}}
    locked = {item for item in (locked_athlete_ids or ()) if item not in {None, ""}}
    confirmed = dict(current_confirmed_slots or {})
    excess = {item for item in excess_athlete_ids if item not in {None, ""}}
    unresolved = {item for item in role_unresolved_athlete_ids if item not in {None, ""}}
    previous_bench_ids = drop_role_quota_excess_from_tribuna(
        previous_bench_ids, excess | unresolved
    )
    dropped: list[object] = []
    unavailable: list[object] = []
    starters: list[object] = []

    for athlete_id in previous_starter_ids:
        if athlete_id in {None, ""}:
            starters.append("")
            continue
        if athlete_id not in roster_set:
            dropped.append(athlete_id)
            starters.append("")
            continue
        if athlete_id in locked and confirmed.get(athlete_id) != LineupSlotKind.STARTER.value:
            unavailable.append(athlete_id)
            starters.append("")
            continue
        starters.append(athlete_id)
    while len(starters) < STARTER_COUNT:
        starters.append("")
    starter_ids = starters[:STARTER_COUNT]
    starter_set = {item for item in starter_ids if item not in {None, ""}}

    for athlete_id in previous_bench_ids:
        if (
            athlete_id not in {None, ""}
            and athlete_id not in roster_set
            and athlete_id not in dropped
        ):
            dropped.append(athlete_id)

    previous_bench_kept = [
        item
        for item in previous_bench_ids
        if item not in {None, ""} and item in roster_set and item not in starter_set
    ]
    displaced = [item for item in unavailable if item in roster_set and item not in starter_set]
    bench_ids = ordered_bench_from_roster(
        roster_athlete_ids,
        starter_ids,
        [*previous_bench_kept, *displaced],
    )
    # La panchina ereditata dal turno precedente può non rispettare più la
    # regola "panchina attiva" solo per l'ordine (es. i cambi di modulo
    # hanno spostato chi è titolare/panchinaro): si auto-corregge quando la
    # rosa lo permette, invece di bloccare una copia altrimenti valida. Non
    # quando c'è già un bloccato in panchina: riordinare potrebbe scavalcarlo
    # (`evaluate_bench_order_lock`), e quel vincolo ha priorità — in quel
    # caso l'eventuale violazione resta segnalata più sotto come issue.
    roles = role_by_athlete_id or {}
    if not locked:
        bench_ids = [
            player.athlete_id
            for player in reorder_bench_for_active_roles(
                [
                    LineupPlayerRef(athlete_id=athlete_id, role=roles.get(athlete_id))
                    for athlete_id in bench_ids
                ]
            )
        ]

    lock_issues = [
        *evaluate_progressive_lock(
            previous_slots=confirmed,
            proposed_slots={
                **{
                    item: LineupSlotKind.STARTER.value
                    for item in starter_ids
                    if item not in {None, ""}
                },
                **{
                    item: LineupSlotKind.BENCH.value for item in bench_ids if item not in {None, ""}
                },
            },
            locked_athlete_ids=locked,
        ),
        *evaluate_bench_order_lock(
            previous_bench=current_confirmed_bench or (),
            proposed_bench=bench_ids,
            locked_athlete_ids=locked,
        ),
    ]

    issues: list[LineupIssue] = []
    if any(item not in excess and item not in unresolved for item in dropped):
        issues.append(
            LineupIssue(code="copied_athlete_not_in_roster", message=COPIED_NOT_IN_ROSTER_MESSAGE)
        )
    names = athlete_names or {}
    dropped_excess = [item for item in dropped if item in excess]
    if dropped_excess:
        issues.append(
            LineupIssue(
                code=COPIED_EXCEEDS_ROLE_QUOTA_CODE,
                message=copied_athlete_exceeds_role_quota_message(
                    [names[item] for item in dropped_excess if item in names]
                ),
            )
        )
    dropped_unresolved = [item for item in dropped if item in unresolved]
    if dropped_unresolved:
        issues.append(
            LineupIssue(
                code=COPIED_ROLE_UNRESOLVED_CODE,
                message=copied_athlete_role_unresolved_message(
                    [names[item] for item in dropped_unresolved if item in names]
                ),
            )
        )
    if unavailable:
        issues.append(
            LineupIssue(code="copied_athlete_unavailable", message=COPIED_UNAVAILABLE_MESSAGE)
        )
    issues.extend(lock_issues)

    confirmation = evaluate_lineup(
        module=previous_module,
        starters=[
            LineupPlayerRef(
                athlete_id=athlete_id,
                role=roles.get(athlete_id) if athlete_id not in {None, ""} else None,
            )
            for athlete_id in starter_ids
        ],
        bench=[
            LineupPlayerRef(
                athlete_id=athlete_id,
                role=roles.get(athlete_id) if athlete_id not in {None, ""} else None,
            )
            for athlete_id in bench_ids
        ],
        roster_athlete_ids=roster_athlete_ids,
    )
    # Non rispostabile con il solo riordino (rosa senza abbastanza giocatori
    # di un ruolo, o bloccato di mezzo che impedisce il riordino sopra):
    # segnalata come le altre issue, non lasciata silenziosa dentro
    # `can_confirm=False`.
    issues.extend(item for item in confirmation.issues if item.code == "bench_roles_invalid")
    return CopyLineupResult(
        module=previous_module,
        starter_ids=tuple(starter_ids),
        bench_ids=tuple(bench_ids),
        dropped_athlete_ids=tuple(dropped),
        unavailable_athlete_ids=tuple(unavailable),
        issues=_dedupe_issues(issues),
        blocked=bool(lock_issues),
        can_confirm=confirmation.valid and not lock_issues,
    )


def assert_copy_previous_lineup(result: CopyLineupResult) -> CopyLineupResult:
    from auth.exceptions import ValidationAuthError

    if not result.blocked:
        return result
    first = next(
        (
            item
            for item in result.issues
            if item.code in {"athlete_kickoff_locked", "bench_order_locked"}
        ),
        result.issues[0] if result.issues else None,
    )
    if first is None:
        raise ValidationAuthError(
            "Modifica fuori tempo: il turno non accetta più cambiamenti di formazione.",
            code="turn_modification_closed",
        )
    raise ValidationAuthError(first.message, code=first.code)
