"""Ricalcolo e lettura di media stagionale, valore di mercato e storico del calciatore (1.3).

- ``refresh_market_values``: materializza lo storico della stagione in corso dai nostri dati,
  poi calcola media stagionale e Valore di tutto il listone e riscrive ``athlete_market_values``.
  Delle stagioni passate dal fornitore contano **solo le righe di campionato**: le coppe
  restano nella carriera (``build_career``) ma non nella media né nel Valore (decisione di
  Rosario, 22/11; regola in ``sports_data.season_stats.competition_types``).
  Salta il lavoro se nulla è cambiato dall'ultima volta (impronta in ``system_flags``).
  Gira dal job periodico «Medie e Valore di mercato», a fine import dello storico e a richiesta
  dell'operatore.
- ``load_market_info``: per una lega, ``marketValue`` (crediti proporzionali al budget della
  lega) e ``seasonAverage`` di un insieme di calciatori, con due query al massimo.
- ``build_career``: righe dello storico per la scheda calciatore.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from database.enums import FlagScope
from database.models.infrastructure import SystemFlag
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.ledger import resolve_initial_credits
from fantasy_turns.readiness import FINISHED_FIXTURE_STATUSES
from leagues.models.league import League
from market import valuation
from market.valuation import (
    SeasonSample,
    ValuationInput,
    base_reference_value,
    combine_rows,
    compute_valuations,
    credits_for_budget,
    select_season_average,
)
from market.valuation_models import AthleteMarketValue
from market.valuation_schemas import AthleteCareerRowResponse, AthleteSeasonAverageResponse
from observability.logging import get_logger
from sports_data.catalog.models import SportSeason
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete
from sports_data.season_stats.competition_types import (
    COMPETITION_TYPE_CUP,
    COMPETITION_TYPE_LEAGUE,
    competition_kind,
    load_competition_types,
)
from sports_data.season_stats.current_season import materialize_current_season
from sports_data.season_stats.models import AthleteSeasonStat, ProviderCompetitionType
from sports_data.season_stats.seasons import (
    SOURCE_FANTAPPERO,
    SOURCE_PROVIDER,
    career_seasons,
    season_label,
)

logger = get_logger(__name__)

#: Cambia quando cambia la formula o la struttura di ``components_json``: forza il ricalcolo
#: anche a dati fermi, così il ricalcolo successivo riscrive tutte le righe.
#: 1.3.1: solo le righe di campionato delle stagioni passate (coppe escluse, 22/11).
#: 1.4.0: ``components_json`` con il dettaglio di ogni passaggio («Dettaglio del Valore»,
#: pannello operatore); la formula non cambia.
VALUATION_VERSION = "1.4.0"
FINGERPRINT_FLAG_PREFIX = "market_values:"
#: Oltre questo numero di calciatori si legge la stagione intera (listone) invece di un IN.
_BULK_READ_THRESHOLD = 400


# -- ricalcolo ----------------------------------------------------------------


@dataclass
class MarketValuesRefreshResult:
    season_year: int
    skipped: bool
    current_season_rows: int = 0
    athletes_valued: int = 0
    athletes_with_history: int = 0
    athletes_with_current_average: int = 0
    athletes_with_previous_average: int = 0
    computed_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "seasonYear": self.season_year,
            "skipped": self.skipped,
            "currentSeasonRows": self.current_season_rows,
            "athletesValued": self.athletes_valued,
            "athletesWithHistory": self.athletes_with_history,
            "athletesWithCurrentAverage": self.athletes_with_current_average,
            "athletesWithPreviousAverage": self.athletes_with_previous_average,
            "computedAt": self.computed_at.isoformat() if self.computed_at else None,
        }


def _flag_key(season_year: int) -> str:
    return f"{FINGERPRINT_FLAG_PREFIX}{season_year}"


def _count_max(session: Session, stmt: Any) -> list[str]:
    count, latest = session.execute(stmt).one()
    return [str(int(count or 0)), latest.isoformat() if latest is not None else ""]


def data_fingerprint(session: Session, *, season_year: int) -> str:
    """Impronta dei dati che entrano nel calcolo: voti, statistiche, storico, tipi di
    competizione (campionato o coppa), listone."""
    parts: list[str] = [VALUATION_VERSION, str(season_year)]
    parts += _count_max(session, select(func.count(), func.max(PlayerMatchRating.updated_at)))
    parts += _count_max(session, select(func.count(), func.max(PlayerMatchStat.updated_at)))
    parts += _count_max(
        session,
        select(func.count(), func.max(Fixture.updated_at))
        .join(SportSeason, SportSeason.id == Fixture.sport_season_id)
        .where(
            SportSeason.year == season_year,
            Fixture.status_short.in_(sorted(FINISHED_FIXTURE_STATUSES)),
        ),
    )
    parts += _count_max(
        session,
        select(func.count(), func.max(AthleteSeasonStat.updated_at)).where(
            AthleteSeasonStat.source == SOURCE_PROVIDER
        ),
    )
    parts += _count_max(
        session,
        select(func.count(), func.max(ProviderCompetitionType.updated_at)),
    )
    parts += _count_max(
        session,
        select(func.count(), func.max(RoleAssignment.updated_at)).where(
            RoleAssignment.season_year == season_year
        ),
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def last_refresh(session: Session, *, season_year: int) -> dict[str, Any] | None:
    raw = session.scalar(select(SystemFlag.value).where(SystemFlag.key == _flag_key(season_year)))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _save_refresh(session: Session, *, season_year: int, payload: dict[str, Any]) -> None:
    key = _flag_key(season_year)
    text = json.dumps(payload, sort_keys=True)
    row = session.scalar(select(SystemFlag).where(SystemFlag.key == key))
    if row is None:
        session.add(SystemFlag(key=key, value=text, scope=FlagScope.SYSTEM))
    else:
        row.value = text
    session.flush()


def _backfill_athlete_ids(session: Session) -> None:
    """Le righe importate prima che il calciatore entrasse nel listone prendono il suo id."""
    session.execute(
        update(AthleteSeasonStat)
        .where(
            AthleteSeasonStat.athlete_id.is_(None),
            AthleteSeasonStat.athlete_provider_id == Athlete.provider_id,
        )
        .values(athlete_id=Athlete.id)
        .execution_options(synchronize_session=False)
    )


#: Riga dello storico che non conta perché senza media (fornitore ``rating`` vuoto, o nessun
#: voto FantApperò): non è un tipo di competizione, serve al dettaglio dell'operatore.
ROW_KIND_NO_RATING = "no_rating"


@dataclass(frozen=True)
class SeasonRowDetail:
    """Una riga dello storico letta per il Valore: contata o esclusa, e perché."""

    competition: str
    club: str | None
    #: Peso nella media: presenze (fornitore) o partite con voto (FantApperò); una riga con
    #: media ma senza presenze conta 1, come in ``combine_rows``.
    appearances: int
    average: float | None
    #: ``league`` (contata), ``cup`` / ``unknown`` (escluse: non campionato) o ``no_rating``.
    kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "competition": self.competition,
            "club": self.club,
            "appearances": self.appearances,
            "average": round(self.average, 4) if self.average is not None else None,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class SeasonSampleDetail:
    """Media di una stagione di un calciatore e le righe da cui viene."""

    #: Fonte delle righe usate (``provider`` o ``fantappero``).
    source: str
    sample: SeasonSample
    counted: tuple[SeasonRowDetail, ...] = ()
    excluded: tuple[SeasonRowDetail, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "rows": [row.as_dict() for row in self.counted],
            "excluded": [row.as_dict() for row in self.excluded],
        }


@dataclass(frozen=True)
class _StoredRow:
    competition: str
    club: str | None
    rating: float | None
    weight: int | None
    kind: str


def _competition_label(name: str | None, provider_id: int) -> str:
    if name:
        return name
    return f"Competizione {provider_id}" if provider_id else "Competizione sconosciuta"


def _row_detail(row: _StoredRow) -> SeasonRowDetail:
    kind = row.kind
    if kind == COMPETITION_TYPE_LEAGUE and row.rating is None:
        kind = ROW_KIND_NO_RATING
    if row.rating is not None:
        appearances = row.weight if row.weight is not None and row.weight > 0 else 1
    else:
        appearances = max(0, row.weight or 0)
    return SeasonRowDetail(
        competition=row.competition,
        club=row.club,
        appearances=appearances,
        average=row.rating,
        kind=kind,
    )


def _by_weight(rows: Iterable[SeasonRowDetail]) -> tuple[SeasonRowDetail, ...]:
    return tuple(sorted(rows, key=lambda row: (-row.appearances, row.competition)))


def season_sample_details(
    session: Session,
    *,
    current_season_year: int,
    provider_ids: Iterable[int] | None = None,
) -> dict[tuple[int, int], SeasonSampleDetail]:
    """Come ``season_samples``, con le righe contate ed escluse di ogni stagione (anche delle
    stagioni senza dati, es. sole coppe), per spiegare il Valore all'operatore."""
    seasons = career_seasons(current_season_year)
    stmt = select(
        AthleteSeasonStat.athlete_provider_id,
        AthleteSeasonStat.season_year,
        AthleteSeasonStat.source,
        AthleteSeasonStat.competition_provider_id,
        AthleteSeasonStat.competition_name,
        AthleteSeasonStat.club_name,
        AthleteSeasonStat.rating,
        AthleteSeasonStat.appearances,
        AthleteSeasonStat.votes,
    ).where(AthleteSeasonStat.season_year.in_(seasons))
    if provider_ids is not None:
        ids = sorted(set(provider_ids))
        if not ids:
            return {}
        stmt = stmt.where(AthleteSeasonStat.athlete_provider_id.in_(ids))
    types = load_competition_types(session)
    excluded_cups = 0
    excluded_unknown: dict[int, int] = defaultdict(int)
    by_key: dict[tuple[int, int], dict[str, list[_StoredRow]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (
        pid,
        year,
        source,
        competition,
        competition_name,
        club_name,
        rating,
        appearances,
        votes,
    ) in session.execute(stmt).tuples():
        # Le righe nostre vengono dalle partite del catalogo (solo i 5 campionati).
        kind = (
            COMPETITION_TYPE_LEAGUE
            if source == SOURCE_FANTAPPERO
            else competition_kind(int(competition), types)
        )
        if kind == COMPETITION_TYPE_CUP:
            excluded_cups += 1
        elif kind != COMPETITION_TYPE_LEAGUE:
            excluded_unknown[int(competition)] += 1
        by_key[(int(pid), int(year))][source].append(
            _StoredRow(
                competition=_competition_label(competition_name, int(competition)),
                club=club_name,
                rating=float(rating) if rating is not None else None,
                weight=votes if source == SOURCE_FANTAPPERO else appearances,
                kind=kind,
            )
        )
    if excluded_cups or excluded_unknown:
        logger.info(
            "season_samples_rows_excluded",
            extra={
                "current_season_year": current_season_year,
                "cup_rows": excluded_cups,
                "unknown_type_rows": sum(excluded_unknown.values()),
                # Le competizioni di tipo sconosciuto più frequenti (id del fornitore).
                "unknown_competitions": sorted(
                    excluded_unknown, key=lambda cid: (-excluded_unknown[cid], cid)
                )[:20],
                "competition_types_known": len(types),
            },
        )
    result: dict[tuple[int, int], SeasonSampleDetail] = {}
    for (pid, year), sources in by_key.items():
        # Stagione in corso: solo i nostri dati. Passate: i nostri se c'erano, poi il fornitore.
        if sources.get(SOURCE_FANTAPPERO):
            source = SOURCE_FANTAPPERO
        elif year != current_season_year and sources.get(SOURCE_PROVIDER):
            source = SOURCE_PROVIDER
        else:
            continue
        rows = sources[source]
        sample = combine_rows(
            (row.rating, row.weight) for row in rows if row.kind == COMPETITION_TYPE_LEAGUE
        )
        details = [_row_detail(row) for row in rows]
        result[(pid, year)] = SeasonSampleDetail(
            source=source,
            sample=sample,
            counted=_by_weight(row for row in details if row.kind == COMPETITION_TYPE_LEAGUE),
            excluded=_by_weight(row for row in details if row.kind != COMPETITION_TYPE_LEAGUE),
        )
    return result


def season_samples(
    session: Session,
    *,
    current_season_year: int,
    provider_ids: Iterable[int] | None = None,
) -> dict[tuple[int, int], SeasonSample]:
    """Media e peso per (calciatore, stagione) sulle tre stagioni del Valore.

    Stagione in corso: solo i nostri voti (peso = partite con voto). Stagioni passate: i nostri
    dati se c'erano (stagioni vissute in FantApperò), altrimenti il fornitore (peso = presenze).

    Solo campionati: delle righe del fornitore contano quelle di un campionato
    (``competition_types.is_championship``: i 5 di ``MVP_LEAGUE_IDS`` o tipo ``league``); le
    coppe e le competizioni di tipo sconosciuto sono escluse. Una stagione con sole coppe è
    una stagione senza dati. Le righe nostre vengono dalle partite del catalogo, che ha solo i
    5 campionati: si prendono tutte.
    """
    return {
        key: detail.sample
        for key, detail in season_sample_details(
            session, current_season_year=current_season_year, provider_ids=provider_ids
        ).items()
        if detail.sample.usable
    }


#: Stagione di ogni voce di ``components_json["seasons"]``: anni prima di quella in corso.
SLOT_SEASON_OFFSETS = {"current": 0, "previous": 1, "twoSeasonsAgo": 2}


def valuation_components(
    valued: valuation.Valuation,
    *,
    season_year: int,
    details: dict[str, SeasonSampleDetail | None],
) -> dict[str, Any]:
    """``components_json``: ogni passaggio della formula, con le righe di ogni stagione."""
    components = valued.components()
    components["version"] = VALUATION_VERSION
    for slot, season in components["seasons"].items():
        year = season_year - SLOT_SEASON_OFFSETS[slot]
        detail = details.get(slot)
        season["seasonYear"] = year
        season["seasonLabel"] = season_label(year)
        season.update(
            detail.as_dict() if detail is not None else {"source": None, "rows": [], "excluded": []}
        )
    return components


def refresh_market_values(
    session: Session,
    *,
    season_year: int,
    force: bool = False,
) -> MarketValuesRefreshResult:
    """Ricalcola storico della stagione in corso, media stagionale e Valore del listone."""
    fingerprint = data_fingerprint(session, season_year=season_year)
    previous = last_refresh(session, season_year=season_year)
    if not force and previous is not None and previous.get("fingerprint") == fingerprint:
        return MarketValuesRefreshResult(season_year=season_year, skipped=True)

    current_rows = materialize_current_season(session, season_year=season_year)
    _backfill_athlete_ids(session)

    listone = session.execute(
        select(RoleAssignment.athlete_id, RoleAssignment.role, Athlete.provider_id)
        .join(Athlete, Athlete.id == RoleAssignment.athlete_id)
        .where(RoleAssignment.season_year == season_year)
    ).all()
    details = season_sample_details(session, current_season_year=season_year)
    samples = {key: detail.sample for key, detail in details.items() if detail.sample.usable}
    inputs = [
        ValuationInput(
            key=athlete_id,
            role=role.value,
            current=samples.get((int(provider_id), season_year)),
            previous=samples.get((int(provider_id), season_year - 1)),
            two_seasons_ago=samples.get((int(provider_id), season_year - 2)),
        )
        for athlete_id, role, provider_id in listone
    ]
    valuations = compute_valuations(inputs)

    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    result = MarketValuesRefreshResult(
        season_year=season_year,
        skipped=False,
        current_season_rows=current_rows,
        computed_at=now,
    )
    provider_by_athlete = {athlete_id: int(pid) for athlete_id, _, pid in listone}
    for item in inputs:
        valued = valuations[item.key]
        provider_id = provider_by_athlete[item.key]  # type: ignore[index]
        average = select_season_average(
            current_season_year=season_year,
            current=item.current,
            previous=item.previous,
        )
        if valued.has_history:
            result.athletes_with_history += 1
        if average is not None and average.is_current:
            result.athletes_with_current_average += 1
        elif average is not None:
            result.athletes_with_previous_average += 1
        rows.append(
            {
                "athlete_id": item.key,
                "athlete_provider_id": provider_id,
                "season_year": season_year,
                "role": item.role,
                "value_index": valued.value_index,
                "reference_value": valued.reference_value,
                "season_average": average.value if average is not None else None,
                "season_average_year": average.season_year if average is not None else None,
                "season_average_is_current": bool(average is not None and average.is_current),
                "current_votes": item.current.appearances if item.current is not None else 0,
                "components_json": valuation_components(
                    valued,
                    season_year=season_year,
                    details={
                        slot: details.get((provider_id, season_year - offset))
                        for slot, offset in SLOT_SEASON_OFFSETS.items()
                    },
                ),
            }
        )
    session.execute(delete(AthleteMarketValue).where(AthleteMarketValue.season_year == season_year))
    if rows:
        session.execute(insert(AthleteMarketValue), rows)
    result.athletes_valued = len(rows)
    _save_refresh(
        session,
        season_year=season_year,
        payload={
            "fingerprint": fingerprint,
            "version": VALUATION_VERSION,
            **result.as_dict(),
        },
    )
    session.flush()
    logger.info(
        "market_values_refreshed",
        extra={
            "season_year": season_year,
            "athletes_valued": result.athletes_valued,
            "current_season_rows": current_rows,
            "athletes_with_history": result.athletes_with_history,
        },
    )
    return result


# -- lettura per le API -------------------------------------------------------


@dataclass(frozen=True)
class AthleteMarketInfo:
    market_value: int | None = None
    season_average: AthleteSeasonAverageResponse | None = None


def season_average_response(
    *, value: float | None, season_year: int | None, is_current: bool
) -> AthleteSeasonAverageResponse | None:
    if value is None or season_year is None:
        return None
    return AthleteSeasonAverageResponse(
        value=round(float(value), valuation.SEASON_AVERAGE_DECIMALS),
        seasonYear=season_year,
        seasonLabel=season_label(season_year),
        isCurrent=is_current,
    )


def load_market_info(
    session: Session,
    *,
    league_id: UUID,
    athlete_ids: Iterable[UUID],
    league: League | None = None,
) -> dict[UUID, AthleteMarketInfo]:
    """``marketValue`` e ``seasonAverage`` per la lega: al massimo due letture.

    Un calciatore senza riga materializzata (entrato nel listone dopo l'ultimo ricalcolo) ha il
    valore base del suo ruolo e nessuna media.
    """
    ids = list(dict.fromkeys(athlete_ids))
    if not ids:
        return {}
    target = league if league is not None else session.get(League, league_id)
    if target is None:
        return {}
    budget = resolve_initial_credits(session, league_id)
    season_year = target.season_year
    stmt = select(
        AthleteMarketValue.athlete_id,
        AthleteMarketValue.reference_value,
        AthleteMarketValue.season_average,
        AthleteMarketValue.season_average_year,
        AthleteMarketValue.season_average_is_current,
    ).where(AthleteMarketValue.season_year == season_year)
    wanted = set(ids)
    if len(ids) <= _BULK_READ_THRESHOLD:
        stmt = stmt.where(AthleteMarketValue.athlete_id.in_(ids))
    result: dict[UUID, AthleteMarketInfo] = {}
    for athlete_id, reference, average, average_year, is_current in session.execute(stmt):
        if athlete_id not in wanted:
            continue
        result[athlete_id] = AthleteMarketInfo(
            market_value=credits_for_budget(float(reference), budget),
            season_average=season_average_response(
                value=average, season_year=average_year, is_current=bool(is_current)
            ),
        )
    missing = [athlete_id for athlete_id in ids if athlete_id not in result]
    if missing:
        for athlete_id, role in session.execute(
            select(RoleAssignment.athlete_id, RoleAssignment.role).where(
                RoleAssignment.season_year == season_year,
                RoleAssignment.athlete_id.in_(missing),
            )
        ):
            result[athlete_id] = AthleteMarketInfo(
                market_value=credits_for_budget(base_reference_value(role.value), budget)
            )
    return result


class LeagueMarketInfoCache:
    """Cache per richiesta: il servizio la riusa per più risposte della stessa lega."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[tuple[UUID, UUID], AthleteMarketInfo] = {}

    def get(self, league_id: UUID, athlete_ids: Iterable[UUID]) -> dict[UUID, AthleteMarketInfo]:
        ids = list(dict.fromkeys(athlete_ids))
        missing = [athlete_id for athlete_id in ids if (league_id, athlete_id) not in self._cache]
        if missing:
            loaded = load_market_info(self._session, league_id=league_id, athlete_ids=missing)
            for athlete_id in missing:
                self._cache[(league_id, athlete_id)] = loaded.get(athlete_id, AthleteMarketInfo())
        return {athlete_id: self._cache[(league_id, athlete_id)] for athlete_id in ids}

    def one(self, league_id: UUID, athlete_id: UUID) -> AthleteMarketInfo:
        return self.get(league_id, [athlete_id])[athlete_id]


# -- scheda calciatore --------------------------------------------------------


def _round(value: float | None) -> float | None:
    return round(float(value), valuation.SEASON_AVERAGE_DECIMALS) if value is not None else None


def build_career(
    session: Session,
    *,
    athlete_provider_id: int,
    current_season_year: int,
) -> list[AthleteCareerRowResponse]:
    """Storico per la scheda: le due stagioni passate e quella in corso, dalla più recente.

    Stagione in corso: solo i nostri dati. Stagioni passate: i nostri se c'erano, altrimenti il
    fornitore. Una riga a zero presenze (es. coppa senza minuti) si mostra solo se è l'unica
    della sua stagione.
    """
    seasons = career_seasons(current_season_year)
    rows = session.scalars(
        select(AthleteSeasonStat).where(
            AthleteSeasonStat.athlete_provider_id == athlete_provider_id,
            AthleteSeasonStat.season_year.in_(seasons),
        )
    ).all()
    by_season: dict[int, dict[str, list[AthleteSeasonStat]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        by_season[row.season_year][row.source].append(row)
    career: list[AthleteCareerRowResponse] = []
    for season_year in seasons:
        sources = by_season.get(season_year, {})
        if season_year == current_season_year:
            chosen = sources.get(SOURCE_FANTAPPERO, [])
        else:
            chosen = sources.get(SOURCE_FANTAPPERO) or sources.get(SOURCE_PROVIDER, [])
        played = [row for row in chosen if (row.appearances or 0) > 0 or (row.minutes or 0) > 0]
        shown = played or chosen[:1]
        shown = sorted(
            shown,
            key=lambda row: (row.minutes or 0, row.appearances or 0),
            reverse=True,
        )
        for row in shown:
            career.append(
                AthleteCareerRowResponse(
                    seasonYear=season_year,
                    seasonLabel=season_label(season_year),
                    isCurrent=season_year == current_season_year,
                    source=row.source,  # type: ignore[arg-type]
                    clubId=str(row.club_id) if row.club_id else None,
                    clubName=row.club_name,
                    competitionId=str(row.competition_id) if row.competition_id else None,
                    competitionName=row.competition_name,
                    appearances=row.appearances,
                    minutes=row.minutes,
                    averageRating=_round(row.rating),
                    votes=row.votes,
                    fantasyAverage=_round(row.fantasy_average),
                    goals=row.goals,
                    assists=row.assists,
                    goalsConceded=row.goals_conceded,
                    saves=row.saves,
                    penaltiesSaved=row.penalties_saved,
                    yellowCards=row.yellow_cards,
                    redCards=row.red_cards,
                    cleanSheets=row.clean_sheets,
                )
            )
    return career
