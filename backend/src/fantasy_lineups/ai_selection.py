"""Selezione deterministica della formazione per fantallenatori IA (EP13-P05).

Motore puro, senza sessione né I/O. Implementa ADR-0005: formula versionata e
ispezionabile, nessun uso di dati successivi all'istante di decisione.

Le squadre IA partecipano al pilot reale, quindi ogni scelta dev'essere
riproducibile e contestabile: a parità di input e versione l'output è identico,
e ogni esclusione porta con sé il motivo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from database.enums import FantasyRole

#: Versione della formula. Cambiarla invalida il confronto fra decisioni.
AI_LINEUP_ALGORITHM_VERSION = "ai_lineup_v1"

#: Pesi approvati in ADR-0005. La disponibilità non è un peso: è un filtro.
WEIGHT_OFFICIAL_STARTER = 2.0
WEIGHT_RECENT_FORM = 1.0

#: Giornate concluse considerate per la forma recente.
RECENT_FORM_WINDOW = 5


class ExclusionReason(StrEnum):
    """Perché un calciatore posseduto non è stato schierato."""

    INJURED = "injured"
    NO_FIXTURE = "no_fixture"
    NOT_SELECTED = "not_selected"


EXCLUSION_LABELS: dict[ExclusionReason, str] = {
    ExclusionReason.INJURED: "Infortunato",
    ExclusionReason.NO_FIXTURE: "Nessuna partita nel turno",
    ExclusionReason.NOT_SELECTED: "Non selezionato dalla formula",
}


class SignalSource(StrEnum):
    """Da dove viene il segnale usato per un candidato."""

    OFFICIAL_LINEUP = "official_lineup"
    RECENT_FORM = "recent_form"
    LOCAL_FALLBACK = "local_fallback"


@dataclass(frozen=True)
class CandidateInput:
    """Un calciatore posseduto, con i soli segnali ammessi da ADR-0005."""

    athlete_id: UUID
    role: FantasyRole
    injured: bool
    #: True/False se la distinta è utilizzabile, None se non disponibile.
    official_starter: bool | None
    #: Media fantavoto sulle ultime giornate concluse; None se senza storico.
    recent_form: float | None
    #: Presenze recenti, usate come primo tie-break.
    recent_appearances: int
    #: False quando il calciatore non ha una partita in questo turno.
    has_fixture: bool
    #: True quando la sua partita è già iniziata.
    kickoff_locked: bool


@dataclass(frozen=True)
class ScoredCandidate:
    athlete_id: UUID
    role: FantasyRole
    score: float
    sources: tuple[SignalSource, ...]
    excluded_reason: ExclusionReason | None


@dataclass
class LineupPlan:
    """Esito della selezione, con tutto ciò che serve a giustificarla."""

    algorithm_version: str
    decided_at: datetime
    starters: tuple[UUID, ...] = ()
    bench: tuple[UUID, ...] = ()
    candidates: tuple[ScoredCandidate, ...] = ()
    used_fallback: bool = False
    unfilled_roles: tuple[FantasyRole, ...] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        return len(self.starters) == 11 and not self.unfilled_roles


def is_eligible(candidate: CandidateInput) -> ExclusionReason | None:
    """Motivo di esclusione, oppure ``None`` se schierabile.

    L'infortunio è un filtro assoluto, non una penalità: schierare un
    infortunato è un errore, non una scelta rischiosa.

    Il kickoff della partita reale non esclude più il candidato (decisione
    prodotto EP13-P04-bis): la formazione IA può essere generata anche
    retroattivamente, a turno iniziato o concluso. ``kickoff_locked`` resta
    calcolato sul candidato solo per il lock progressivo su una formazione
    IA già esistente (vedi ``ai_service.generate_ai_lineup``).
    """
    if candidate.injured:
        return ExclusionReason.INJURED
    if not candidate.has_fixture:
        return ExclusionReason.NO_FIXTURE
    return None


def score_candidate(candidate: CandidateInput) -> tuple[float, tuple[SignalSource, ...]]:
    """Score e provenienza dei segnali effettivamente usati."""
    score = 0.0
    sources: list[SignalSource] = []

    if candidate.official_starter is not None:
        if candidate.official_starter:
            score += WEIGHT_OFFICIAL_STARTER
        sources.append(SignalSource.OFFICIAL_LINEUP)

    if candidate.recent_form is not None:
        score += WEIGHT_RECENT_FORM * candidate.recent_form
        sources.append(SignalSource.RECENT_FORM)

    if not sources:
        # Nessun segnale: resta solo l'ordinamento deterministico.
        sources.append(SignalSource.LOCAL_FALLBACK)

    return score, tuple(sources)


def _sort_key(scored: ScoredCandidate, candidate: CandidateInput) -> tuple[float, int, str]:
    """Score desc, presenze desc, athlete_id asc: stabile e riproducibile."""
    return (-scored.score, -candidate.recent_appearances, str(scored.athlete_id))


def build_lineup_plan(
    candidates: Iterable[CandidateInput],
    role_targets: Sequence[tuple[FantasyRole, int]],
    *,
    decided_at: datetime,
    bench_size: int | None = None,
) -> LineupPlan:
    """Seleziona titolari e panchina rispettando i vincoli di ruolo.

    ``role_targets`` arriva dal catalogo moduli approvato: la formula non
    inventa moduli, sceglie solo chi occupa gli slot previsti.
    """
    pool = list(candidates)
    by_id = {candidate.athlete_id: candidate for candidate in pool}

    scored: list[ScoredCandidate] = []
    for candidate in pool:
        reason = is_eligible(candidate)
        if reason is not None:
            scored.append(
                ScoredCandidate(
                    athlete_id=candidate.athlete_id,
                    role=candidate.role,
                    score=0.0,
                    sources=(),
                    excluded_reason=reason,
                )
            )
            continue
        value, sources = score_candidate(candidate)
        scored.append(
            ScoredCandidate(
                athlete_id=candidate.athlete_id,
                role=candidate.role,
                score=value,
                sources=sources,
                excluded_reason=None,
            )
        )

    eligible = [item for item in scored if item.excluded_reason is None]
    eligible.sort(key=lambda item: _sort_key(item, by_id[item.athlete_id]))

    starters: list[UUID] = []
    unfilled: list[FantasyRole] = []
    taken: set[UUID] = set()

    for role, needed in role_targets:
        picked = 0
        for item in eligible:
            if picked == needed:
                break
            if item.role != role or item.athlete_id in taken:
                continue
            starters.append(item.athlete_id)
            taken.add(item.athlete_id)
            picked += 1
        if picked < needed:
            # Rosa insufficiente per il modulo: va detto, non nascosto.
            unfilled.extend([role] * (needed - picked))

    remaining = [item for item in eligible if item.athlete_id not in taken]
    # Il regolamento umano richiede che ogni elemento della rosa compaia tra
    # titolari e panchina. Infortunati, senza fixture e giocatori già bloccati
    # non possono partire titolari, ma restano in fondo alla panchina con il
    # motivo di esclusione tracciato nel decision log.
    excluded_remaining = sorted(
        (item for item in scored if item.excluded_reason is not None),
        key=lambda item: (item.role.value, str(item.athlete_id)),
    )
    remaining.extend(excluded_remaining)
    bench_ids = [item.athlete_id for item in remaining]
    if bench_size is not None:
        bench_ids = bench_ids[:bench_size]

    # Chi resta fuori senza un motivo tecnico è "non selezionato".
    final_scored = tuple(
        item
        if item.excluded_reason is not None
        or item.athlete_id in taken
        or item.athlete_id in set(bench_ids)
        else ScoredCandidate(
            athlete_id=item.athlete_id,
            role=item.role,
            score=item.score,
            sources=item.sources,
            excluded_reason=ExclusionReason.NOT_SELECTED,
        )
        for item in scored
    )

    used_fallback = any(
        SignalSource.LOCAL_FALLBACK in item.sources
        for item in final_scored
        if item.athlete_id in taken
    )

    return LineupPlan(
        algorithm_version=AI_LINEUP_ALGORITHM_VERSION,
        decided_at=decided_at,
        starters=tuple(starters),
        bench=tuple(bench_ids),
        candidates=final_scored,
        used_fallback=used_fallback,
        unfilled_roles=tuple(unfilled),
    )


def official_starter_signal(
    *,
    is_starter: bool | None,
    fetched_at: datetime | None,
    decided_at: datetime,
    athlete_kickoff_locked: bool,
) -> bool | None:
    """Titolarità ufficiale utilizzabile solo se acquisita prima della decisione.

    Restituisce ``None`` — segnale non ammesso — quando la distinta manca,
    quando non sappiamo dimostrare quando è stata acquisita, quando è arrivata
    dopo l'istante di decisione, o quando il calciatore è già bloccato dal
    fischio d'inizio. È la regola che impedisce un vantaggio invisibile
    rispetto ai lock umani (ADR-0005 §4).
    """
    if is_starter is None or fetched_at is None:
        return None
    if athlete_kickoff_locked:
        return None
    if fetched_at > decided_at:
        return None
    return is_starter
