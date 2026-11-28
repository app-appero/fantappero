"""Applica al proprio turno la stessa formula IA usata per le squadre IA
(EP-self-service).

v1 (attuale): riusa **senza modifiche** l'euristica deterministica e
versionata ``ai_lineup_v1`` (``fantasy_lineups.ai_selection.build_lineup_plan``)
e la stessa raccolta candidati
(``fantasy_lineups.ai_service.collect_candidates_for_team``) già usata
dall'automazione ADR-0005 per le squadre IA. Qui è invocata on-demand, su
richiesta esplicita di un fantallenatore umano sulla **propria** squadra, non
dal job automatico e senza il guard ``user_type == UserType.AI``.

Se il turno ha già calciatori bloccati (partita iniziata),
`compute_best_lineup_respecting_locks` vincola quelli bloccati al ruolo già
confermato (titolare resta titolare, panchinaro resta panchinaro) e lascia
che l'euristica ottimizzi solo il resto — lo stesso principio di
`assert_progressive_lock` usato dal salvataggio manuale, non il blocco
totale del percorso IA-automatico (ADR-0005 §6).

Roadmap futura (non ancora implementata): una versione successiva potrà
sostituire ``build_lineup_plan`` con un modello ML addestrato, mantenendo
invariati la firma di ``compute_best_lineup_for_team`` e il contratto HTTP
dell'endpoint ``POST /leagues/{league_id}/turni/{round_id}/formazione/migliore``.
Il codice chiamante (router, servizio di salvataggio, UI) non dovrà cambiare:
cambierebbe solo ``algorithm_version`` e l'implementazione interna della
selezione.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from database.enums import FantasyModule, FantasyRole
from fantasy_lineups.ai_selection import (
    CandidateInput,
    LineupPlan,
    ScoredCandidate,
    active_bench_order,
    build_lineup_plan,
    is_eligible,
    score_candidate,
)
from fantasy_lineups.ai_service import collect_candidates_for_team
from fantasy_lineups.rules import (
    BENCH_ACTIVE_ROLE_QUOTA,
    BENCH_ACTIVE_SIZE,
    LineupPlayerRef,
    module_counts,
    restore_bench_active_roles,
)

__all__ = [
    "best_lineup_incomplete_message",
    "compute_best_lineup_for_team",
    "compute_best_lineup_respecting_locks",
    "select_best_module",
]

_ROLE_ORDER = (FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A)

_ROLE_NAMES: dict[FantasyRole, tuple[str, str]] = {
    FantasyRole.P: ("portiere", "portieri"),
    FantasyRole.D: ("difensore", "difensori"),
    FantasyRole.C: ("centrocampista", "centrocampisti"),
    FantasyRole.A: ("attaccante", "attaccanti"),
}

_INCOMPLETE_FALLBACK_MESSAGE = (
    "La rosa non permette di completare il modulo con la formula automatica."
)


def best_lineup_incomplete_message(module_code: str, unfilled_roles: Sequence[FantasyRole]) -> str:
    """Il messaggio quando la formazione migliore non completa il modulo.

    Dice quanti disponibili mancano per ruolo: la formula non riempie il buco con un
    indisponibile, quindi chi allena deve saperlo (Rosario, 27/11).
    """
    counts = Counter(unfilled_roles)
    parts = []
    for role in _ROLE_ORDER:
        missing = counts.get(role, 0)
        if missing:
            singular, plural = _ROLE_NAMES[role]
            parts.append(f"{missing} {singular if missing == 1 else plural}")
    if not parts:
        return _INCOMPLETE_FALLBACK_MESSAGE
    return (
        f"Formazione migliore non applicata: per il modulo {module_code} mancano "
        f"calciatori disponibili ({', '.join(parts)}). Gli indisponibili non vengono messi "
        "titolari: scegli tu chi schierare o cambia modulo."
    )


def compute_best_lineup_for_team(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
    season_year: int,
    module: FantasyModule,
    decided_at: datetime,
    unavailable_athlete_ids: Collection[UUID] = (),
    doubtful_athlete_ids: Collection[UUID] = (),
) -> LineupPlan:
    """Stessa euristica ``ai_lineup_v1``, applicata on-demand a una squadra qualunque.

    Nessun guard ``UserType.AI`` qui: la squadra può essere di un
    fantallenatore umano. La responsabilità di autorizzazione, lock
    progressivo e persistenza resta al chiamante
    (``FantasyLineupService.apply_best_lineup``), che riusa la pipeline di
    salvataggio umana — questa funzione è pura selezione, nessuna scrittura.

    ``unavailable_athlete_ids``: chi la formazione mostra in grigio (indisponibile). Non entra
    tra i titolari; se senza di loro il modulo non si completa il piano resta incompleto e il
    servizio lo dice, invece di riempire il buco con un indisponibile.

    ``doubtful_athlete_ids``: chi la formazione mostra «in dubbio» (arancione). Resta
    schierabile, ma solo come ultima risorsa: entra tra i titolari solo se nel suo ruolo non
    c'è un disponibile, e solo per completare il modulo (``ai_selection._sort_key``).
    """
    candidates = _mark_unavailable(
        collect_candidates_for_team(
            session,
            league_id=league_id,
            round_id=round_id,
            team_id=team_id,
            season_year=season_year,
            decided_at=decided_at,
        ),
        unavailable_athlete_ids,
        doubtful_athlete_ids,
    )
    return build_lineup_plan(candidates, _role_targets(module), decided_at=decided_at)


def compute_best_lineup_respecting_locks(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
    season_year: int,
    module: FantasyModule,
    decided_at: datetime,
    locked_athlete_ids: set[UUID],
    confirmed_starter_ids: set[UUID],
    confirmed_bench_order: Sequence[UUID],
    unavailable_athlete_ids: Collection[UUID] = (),
    doubtful_athlete_ids: Collection[UUID] = (),
) -> LineupPlan:
    """Come `compute_best_lineup_for_team`, ma vincola i calciatori già
    bloccati (partita iniziata) al ruolo già confermato — mai promuove un
    panchinaro bloccato a titolare, mai retrocede un titolare bloccato in
    panchina, esattamente come farebbe un salvataggio manuale
    (`assert_progressive_lock` in `service.py`). L'euristica ottimizza solo i
    calciatori non ancora bloccati, per i ruoli non già coperti dai bloccati.

    L'ordine di panchina già confermato non si tocca per chi vi compariva
    già (bloccato o no): solo i nuovi arrivi (ex titolari retrocessi, o mai
    schierati prima) si accodano, ordinati per punteggio. Questo garantisce
    di non violare mai `assert_bench_order_lock` al salvataggio finale — un
    umano può riordinare la panchina attorno a un bloccato senza scavalcarlo,
    qui si preferisce non toccare affatto l'ordine esistente piuttosto che
    rischiare di scavalcarlo per errore.

    Gli indisponibili (``unavailable_athlete_ids``) non entrano tra i titolari liberi; un
    titolare bloccato resta dov'è anche se indisponibile (la sua partita è già iniziata).
    Gli «in dubbio» (``doubtful_athlete_ids``) sono l'ultima risorsa, come nel caso libero.
    """
    candidates = _mark_unavailable(
        collect_candidates_for_team(
            session,
            league_id=league_id,
            round_id=round_id,
            team_id=team_id,
            season_year=season_year,
            decided_at=decided_at,
        ),
        unavailable_athlete_ids,
        doubtful_athlete_ids,
    )
    # Davanti a un bloccato in panchina (o in tribuna) non si entra e non si esce
    # (`assert_bench_order_lock`): chi è in panchina fino all'ultimo bloccato resta al suo
    # posto, anche se non ha ancora giocato. Prima un panchinaro davanti a un bloccato poteva
    # salire titolare: la panchina scalava di un posto (bloccati compresi) e al 10° posto
    # saliva il primo della tribuna, spesso un portiere (bozza non salvabile, e2e 20/11).
    last_locked = max(
        (
            index
            for index, athlete_id in enumerate(confirmed_bench_order)
            if athlete_id in locked_athlete_ids
        ),
        default=-1,
    )
    held_bench_ids = set(confirmed_bench_order[: last_locked + 1])
    locked = [c for c in candidates if c.athlete_id in locked_athlete_ids]
    held = [
        c
        for c in candidates
        if c.athlete_id in held_bench_ids and c.athlete_id not in locked_athlete_ids
    ]
    free = [
        c
        for c in candidates
        if c.athlete_id not in locked_athlete_ids and c.athlete_id not in held_bench_ids
    ]

    pinned_starters = [c for c in locked if c.athlete_id in confirmed_starter_ids]
    pinned_bench = [c for c in locked if c.athlete_id not in confirmed_starter_ids] + held

    targets = dict(_role_targets(module))
    for candidate in pinned_starters:
        targets[candidate.role] = max(0, targets[candidate.role] - 1)
    free_plan = build_lineup_plan(
        free,
        [(role, targets[role]) for role in _ROLE_ORDER],
        decided_at=decided_at,
    )

    # Il modulo è un template posizionale fisso (P poi D poi C poi A — vedi
    # `starterTemplate` lato frontend): i titolari vanno raggruppati per
    # ruolo in quest'ordine indipendentemente da chi è bloccato e chi no,
    # altrimenti un titolare bloccato "fuori sequenza" (es. un centrocampista
    # messo in testa alla tupla) finisce letto come titolare di un ruolo
    # diverso lato client, duplicando un altro calciatore in quello slot.
    free_role_by_id = {c.athlete_id: c.role for c in free}
    starters_by_role: dict[FantasyRole, list[UUID]] = {role: [] for role in _ROLE_ORDER}
    for candidate in pinned_starters:
        starters_by_role[candidate.role].append(candidate.athlete_id)
    for athlete_id in free_plan.starters:
        starters_by_role[free_role_by_id[athlete_id]].append(athlete_id)
    starters = tuple(athlete_id for role in _ROLE_ORDER for athlete_id in starters_by_role[role])

    # Nota: un eccesso di bloccati in un ruolo (modulo cambiato, o ruolo
    # riclassificato dal listone) non serve intercettarlo qui — `max(0, …)`
    # sopra azzera il fabbisogno, quindi o il totale supera gli 11 titolari o
    # resta scoperto un altro ruolo: in entrambi i casi `LineupPlan.is_complete`
    # è già falso e il servizio rifiuta con `ai_lineup_incomplete`.
    non_starter_ids = [c.athlete_id for c in pinned_bench] + list(free_plan.bench)
    non_starter_set = set(non_starter_ids)
    carried_bench = [
        athlete_id for athlete_id in confirmed_bench_order if athlete_id in non_starter_set
    ]
    carried_set = set(carried_bench)
    new_arrivals = [athlete_id for athlete_id in non_starter_ids if athlete_id not in carried_set]
    new_arrivals = _role_aware_new_arrivals(
        candidates=candidates,
        free_plan=free_plan,
        non_starter_ids=non_starter_ids,
        carried_bench=carried_bench,
        new_arrival_ids=new_arrivals,
    )
    # Un panchinaro dei primi 10 salito titolare (dopo l'ultimo bloccato) lascia un posto: chi
    # segue scala e al 10° posto sale il primo della tribuna, qualunque ruolo abbia. Stessa
    # riparazione della pulizia all'uscita e della regola di inizio turno (20/11): sale il
    # primo della tribuna con il ruolo che manca, senza spostare né scavalcare chi è fermo.
    role_by_id = {c.athlete_id: c.role for c in candidates}
    repaired = restore_bench_active_roles(
        [
            LineupPlayerRef(athlete_id=athlete_id, role=role_by_id.get(athlete_id))
            for athlete_id in (*carried_bench, *new_arrivals)
        ],
        locked_athlete_ids=set(locked_athlete_ids) | held_bench_ids,
    )

    return LineupPlan(
        algorithm_version=free_plan.algorithm_version,
        decided_at=decided_at,
        starters=starters,
        bench=tuple(ref.athlete_id for ref in repaired.bench),
        candidates=free_plan.candidates,
        used_fallback=free_plan.used_fallback,
        unfilled_roles=free_plan.unfilled_roles,
    )


def _mark_unavailable(
    candidates: list[CandidateInput],
    unavailable_athlete_ids: Collection[UUID],
    doubtful_athlete_ids: Collection[UUID] = (),
) -> list[CandidateInput]:
    """Segna chi la formazione mostra indisponibile (``is_eligible`` lo esclude dai titolari) e
    chi mostra «in dubbio» (schierabile, ma dopo tutti i disponibili dello stesso ruolo).

    Chi è in entrambi gli insiemi conta come indisponibile: un'assenza certa vince sul dubbio.
    """
    unavailable = set(unavailable_athlete_ids)
    doubtful = set(doubtful_athlete_ids) - unavailable
    if not unavailable and not doubtful:
        return candidates
    marked: list[CandidateInput] = []
    for candidate in candidates:
        if candidate.athlete_id in unavailable:
            marked.append(replace(candidate, unavailable=True))
        elif candidate.athlete_id in doubtful:
            marked.append(replace(candidate, doubtful=True))
        else:
            marked.append(candidate)
    return marked


def _role_aware_new_arrivals(
    *,
    candidates: Sequence[CandidateInput],
    free_plan: LineupPlan,
    non_starter_ids: Sequence[UUID],
    carried_bench: Sequence[UUID],
    new_arrival_ids: Sequence[UUID],
) -> list[UUID]:
    """Riordina i nuovi arrivi in coda alla panchina già confermata (regola
    "panchina attiva"): `carried_bench` non si tocca (lock safety, v.
    `compute_best_lineup_respecting_locks`), ma i nuovi arrivi completano
    prima gli slot attivi ancora scoperti dopo il prefisso già confermato,
    scegliendo i migliori per ruolo tra chi manca — poi il resto per
    punteggio, esattamente come `active_bench_order` per il caso normale.
    """
    if not new_arrival_ids:
        return []

    by_id = {c.athlete_id: c for c in candidates}
    role_by_id = {c.athlete_id: c.role for c in candidates}

    all_roles = Counter(role_by_id[athlete_id] for athlete_id in non_starter_ids)
    required = {
        role: min(BENCH_ACTIVE_ROLE_QUOTA.get(role, 0), all_roles.get(role, 0))
        for role in FantasyRole
    }
    carried_prefix_roles = Counter(
        role_by_id[athlete_id] for athlete_id in carried_bench[:BENCH_ACTIVE_SIZE]
    )
    still_needed = {
        role: max(0, required[role] - carried_prefix_roles.get(role, 0)) for role in FantasyRole
    }
    remaining_active_slots = max(0, BENCH_ACTIVE_SIZE - len(carried_bench[:BENCH_ACTIVE_SIZE]))

    free_plan_by_id = {c.athlete_id: c for c in free_plan.candidates}
    pool: list[ScoredCandidate] = []
    for athlete_id in new_arrival_ids:
        scored = free_plan_by_id.get(athlete_id)
        if scored is not None:
            pool.append(scored)
            continue
        # Bloccato (pinned_bench): mai scorato da build_lineup_plan, perché
        # la sua posizione in panchina non viene mai ridiscussa — qui serve
        # solo per decidere il suo posto fra gli altri nuovi arrivi.
        candidate = by_id[athlete_id]
        reason = is_eligible(candidate)
        if reason is not None:
            pool.append(
                ScoredCandidate(
                    athlete_id=athlete_id,
                    role=candidate.role,
                    score=0.0,
                    sources=(),
                    excluded_reason=reason,
                )
            )
            continue
        value, sources = score_candidate(candidate)
        pool.append(
            ScoredCandidate(
                athlete_id=athlete_id,
                role=candidate.role,
                score=value,
                sources=sources,
                excluded_reason=None,
                doubtful=candidate.doubtful,
            )
        )

    return active_bench_order(
        pool,
        by_id,
        required=still_needed,
        active_size=remaining_active_slots,
    )


def select_best_module(
    plans: Sequence[tuple[FantasyModule, LineupPlan]],
) -> tuple[FantasyModule, LineupPlan] | None:
    """Tra più piani (uno per modulo), quello con il punteggio totale più alto
    tra gli undici titolari scelti — ``None`` se nessuno è completabile.

    Prima di tutto conta quanti titolari «in dubbio» servono (1.5): un modulo completabile con
    meno «in dubbio» vince comunque, anche con un punteggio più basso. Senza «in dubbio» la
    scelta è quella di sempre.

    Funzione pura (EP-self-service, modalità ``best_module``): prende piani
    già calcolati (con o senza blocchi rispettati, indifferentemente) invece
    di calcolarli lei stessa, così la scelta del modulo migliore è
    testabile senza sessione né rosa reale. A parità di punteggio vince il
    modulo con codice testuale minore, per un ordine stabile e deterministico
    — nessuna sorpresa a rosa invariata.
    """
    best: tuple[FantasyModule, LineupPlan] | None = None
    best_score: float = float("-inf")
    best_doubtful = 0
    for module, plan in plans:
        if not plan.is_complete:
            continue
        starters = set(plan.starters)
        score = sum(
            candidate.score for candidate in plan.candidates if candidate.athlete_id in starters
        )
        doubtful = plan.doubtful_starter_count
        if best is not None and doubtful != best_doubtful:
            if doubtful < best_doubtful:
                best = (module, plan)
                best_score = score
                best_doubtful = doubtful
            continue
        tie_break_wins = score == best_score and best is not None and module.value < best[0].value
        if best is None or score > best_score or tie_break_wins:
            best = (module, plan)
            best_score = score
            best_doubtful = doubtful
    return best


def _role_targets(module: FantasyModule) -> list[tuple[FantasyRole, int]]:
    counts = module_counts(module)
    values = {
        FantasyRole.P: counts.goalkeepers,
        FantasyRole.D: counts.defenders,
        FantasyRole.C: counts.midfielders,
        FantasyRole.A: counts.forwards,
    }
    return [(role, values[role]) for role in _ROLE_ORDER]
