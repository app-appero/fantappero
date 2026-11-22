"""Import una tantum delle statistiche di stagione dal fornitore (API-Football ``/players``).

Stagioni concluse (con la 2026/27 in corso: ``season=2025`` e ``season=2024``), dalla più
recente:

1. **pagine di campionato** ``/players?league=<id>&season=<anno>&page=<n>`` per i campionati
   di ``MVP_LEAGUE_IDS`` (20 calciatori per pagina, fino a ``paging.total``): una chiamata per
   pagina, non una per partita;
2. **calciatori mancanti** del listone (nessuna riga di quella stagione, es. arrivati da un altro
   campionato): ``/players?id=<provider_id>&season=<anno>``, uno per chiamata.

Ogni risposta passa da ``store_provider_snapshot`` (come le altre chiamate) e da una riga di
``athlete_season_import_fetches``: rieseguire salta le chiamate già fatte (riprendibile e
idempotente; le stagioni passate non cambiano). Le righe vanno in ``athlete_season_stats`` con
``source = 'provider'`` (upsert sulla chiave unica, nessun doppione).

Il ritmo è quello del client (``MinuteRateLimiter`` e pause sul 429). In più l'import si ferma
da solo quando: ha fatto ``max_calls`` chiamate, oppure la quota giornaliera rimasta scende
sotto ``QUOTA_RESERVE_FRACTION`` (resta margine per i giri live). Si riprende rilanciandolo.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from leagues.models.competition import Competition
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import Club
from sports_data.listone.models import RoleAssignment
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.constants import MVP_LEAGUE_IDS
from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
)
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.provider.types import ProviderEnvelope
from sports_data.roster.models import Athlete
from sports_data.scheduler.quota import DEGRADE_REMAINING_FRACTION
from sports_data.season_stats.models import AthleteSeasonImportFetch, AthleteSeasonStat
from sports_data.season_stats.seasons import (
    SOURCE_PROVIDER,
    UNKNOWN_PROVIDER_ID,
    past_seasons,
    season_label,
)

logger = get_logger(__name__)

PLAYERS_ENDPOINT = "/players"
PLAYERS_PER_PAGE = 20
KIND_LEAGUE_PAGE = "league_page"
KIND_ATHLETE = "athlete"

#: Pagine stimate per campionato-stagione finché la prima non dice ``paging.total``
#: (~800 calciatori a rosa nella stagione, giovani compresi, a 20 per pagina).
ESTIMATED_PAGES_PER_COMPETITION_SEASON = 40
#: Prima delle pagine di campionato: quota del listone da cercare uno per uno (neopromosse,
#: arrivati da altri campionati, giovani). Dopo le pagine il conto è esatto.
ESTIMATED_FILL_SHARE = 0.25
#: Tetto di chiamate per esecuzione (si riprende rilanciando).
DEFAULT_MAX_CALLS = 2000
#: Ci si ferma quando la quota giornaliera rimasta scende sotto questa frazione del limite.
QUOTA_RESERVE_FRACTION = DEGRADE_REMAINING_FRACTION
#: Errori di fila (non di quota/autenticazione) dopo cui l'import si ferma.
MAX_CONSECUTIVE_ERRORS = 10

SEASON_IMPORT_CALLS_TOTAL = "season_history_import_calls_total"

STOP_MAX_CALLS = "max_calls"
STOP_QUOTA_RESERVE = "quota_reserve"
STOP_TOO_MANY_ERRORS = "too_many_errors"


def league_page_key(competition_provider_id: int, season_year: int, page: int) -> str:
    return f"players:league={competition_provider_id}:season={season_year}:page={page}"


def athlete_key(athlete_provider_id: int, season_year: int) -> str:
    return f"players:id={athlete_provider_id}:season={season_year}"


# -- parsing ------------------------------------------------------------------


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_rating(value: Any) -> float | None:
    """``games.rating`` è una stringa ("6.842857") o null."""
    if value is None or value == "":
        return None
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    return rating if math.isfinite(rating) and rating > 0 else None


def _block(source: dict[str, Any], name: str) -> dict[str, Any]:
    value = source.get(name)
    return value if isinstance(value, dict) else {}


def _name(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()[:120]
    return None


@dataclass(frozen=True)
class ProviderSeasonRow:
    """Una voce di ``statistics[]``: calciatore + stagione + club + competizione."""

    athlete_provider_id: int
    season_year: int
    club_provider_id: int
    club_name: str | None
    competition_provider_id: int
    competition_name: str | None
    appearances: int | None
    lineups: int | None
    minutes: int | None
    rating: float | None
    goals: int | None
    assists: int | None
    goals_conceded: int | None
    saves: int | None
    penalties_saved: int | None
    yellow_cards: int | None
    red_cards: int | None


def parse_season_rows(envelope: ProviderEnvelope, *, season_year: int) -> list[ProviderSeasonRow]:
    """Righe di stagione da una risposta ``/players`` (campi confermati dai payload reali)."""
    rows: list[ProviderSeasonRow] = []
    seen: set[tuple[int, int, int]] = set()
    for item in envelope.response:
        if not isinstance(item, dict):
            continue
        player = _block(item, "player")
        athlete_provider_id = _as_int(player.get("id"))
        if athlete_provider_id is None:
            continue
        statistics = item.get("statistics")
        for stat in statistics if isinstance(statistics, list) else []:
            if not isinstance(stat, dict):
                continue
            team = _block(stat, "team")
            league = _block(stat, "league")
            stat_season = _as_int(league.get("season"))
            if stat_season is not None and stat_season != season_year:
                continue
            club_provider_id = _as_int(team.get("id")) or UNKNOWN_PROVIDER_ID
            competition_provider_id = _as_int(league.get("id")) or UNKNOWN_PROVIDER_ID
            key = (athlete_provider_id, club_provider_id, competition_provider_id)
            if key in seen:
                continue
            seen.add(key)
            games = _block(stat, "games")
            goals = _block(stat, "goals")
            cards = _block(stat, "cards")
            penalty = _block(stat, "penalty")
            rows.append(
                ProviderSeasonRow(
                    athlete_provider_id=athlete_provider_id,
                    season_year=season_year,
                    club_provider_id=club_provider_id,
                    club_name=_name(team.get("name")),
                    competition_provider_id=competition_provider_id,
                    competition_name=_name(league.get("name")),
                    # Sic: il fornitore scrive «appearences».
                    appearances=_as_int(games.get("appearences")),
                    lineups=_as_int(games.get("lineups")),
                    minutes=_as_int(games.get("minutes")),
                    rating=_as_rating(games.get("rating")),
                    goals=_as_int(goals.get("total")),
                    assists=_as_int(goals.get("assists")),
                    goals_conceded=_as_int(goals.get("conceded")),
                    saves=_as_int(goals.get("saves")),
                    penalties_saved=_as_int(penalty.get("saved")),
                    yellow_cards=_as_int(cards.get("yellow")),
                    red_cards=_as_int(cards.get("red")),
                )
            )
    return rows


# -- persistenza --------------------------------------------------------------


@dataclass
class _IdMaps:
    athletes: dict[int, UUID]
    clubs: dict[int, UUID]
    competitions: dict[int, UUID]


def _id_maps(session: Session, rows: list[ProviderSeasonRow]) -> _IdMaps:
    athlete_ids = {row.athlete_provider_id for row in rows}
    club_ids = {row.club_provider_id for row in rows} - {UNKNOWN_PROVIDER_ID}
    competition_ids = {row.competition_provider_id for row in rows} - {UNKNOWN_PROVIDER_ID}
    athletes: dict[int, UUID] = {}
    if athlete_ids:
        athletes = {
            int(pid): athlete_id
            for pid, athlete_id in session.execute(
                select(Athlete.provider_id, Athlete.id).where(
                    Athlete.provider_id.in_(sorted(athlete_ids))
                )
            ).tuples()
        }
    clubs: dict[int, UUID] = {}
    if club_ids:
        clubs = {
            int(pid): club_id
            for pid, club_id in session.execute(
                select(Club.provider_id, Club.id).where(Club.provider_id.in_(sorted(club_ids)))
            ).tuples()
        }
    competitions: dict[int, UUID] = {}
    if competition_ids:
        competitions = {
            int(pid): competition_id
            for pid, competition_id in session.execute(
                select(Competition.provider_id, Competition.id).where(
                    Competition.provider_id.in_(sorted(competition_ids))
                )
            ).tuples()
        }
    return _IdMaps(athletes=athletes, clubs=clubs, competitions=competitions)


_UPDATABLE = (
    "athlete_id",
    "club_id",
    "club_name",
    "competition_id",
    "competition_name",
    "appearances",
    "lineups",
    "minutes",
    "rating",
    "goals",
    "assists",
    "goals_conceded",
    "saves",
    "penalties_saved",
    "yellow_cards",
    "red_cards",
    "snapshot_id",
)


def upsert_provider_rows(
    session: Session,
    rows: list[ProviderSeasonRow],
    *,
    snapshot_id: UUID | None,
) -> tuple[int, int]:
    """Upsert sulla chiave unica; ritorna ``(create, aggiornate)``."""
    if not rows:
        return 0, 0
    maps = _id_maps(session, rows)
    keys = [
        (row.athlete_provider_id, row.club_provider_id, row.competition_provider_id) for row in rows
    ]
    season_years = {row.season_year for row in rows}
    existing = {
        (int(a), int(c), int(k))
        for a, c, k in session.execute(
            select(
                AthleteSeasonStat.athlete_provider_id,
                AthleteSeasonStat.club_provider_id,
                AthleteSeasonStat.competition_provider_id,
            ).where(
                AthleteSeasonStat.source == SOURCE_PROVIDER,
                AthleteSeasonStat.season_year.in_(sorted(season_years)),
                AthleteSeasonStat.athlete_provider_id.in_(sorted({key[0] for key in keys})),
            )
        ).tuples()
    }
    values = [
        {
            "athlete_provider_id": row.athlete_provider_id,
            "athlete_id": maps.athletes.get(row.athlete_provider_id),
            "season_year": row.season_year,
            "source": SOURCE_PROVIDER,
            "club_provider_id": row.club_provider_id,
            "club_id": maps.clubs.get(row.club_provider_id),
            "club_name": row.club_name,
            "competition_provider_id": row.competition_provider_id,
            "competition_id": maps.competitions.get(row.competition_provider_id),
            "competition_name": row.competition_name,
            "appearances": row.appearances,
            "lineups": row.lineups,
            "minutes": row.minutes,
            "rating": row.rating,
            "goals": row.goals,
            "assists": row.assists,
            "goals_conceded": row.goals_conceded,
            "saves": row.saves,
            "penalties_saved": row.penalties_saved,
            "yellow_cards": row.yellow_cards,
            "red_cards": row.red_cards,
            "clean_sheets": None,  # non c'è nell'aggregato di stagione del fornitore
            "snapshot_id": snapshot_id,
        }
        for row in rows
    ]
    stmt = insert(AthleteSeasonStat).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_athlete_season_stats_row",
        set_={name: stmt.excluded[name] for name in _UPDATABLE}
        | {"updated_at": func.timezone("utc", func.now())},
    )
    session.execute(stmt)
    created = sum(
        1
        for row in rows
        if (row.athlete_provider_id, row.club_provider_id, row.competition_provider_id)
        not in existing
    )
    return created, len(rows) - created


# -- stima (dry-run) ----------------------------------------------------------


@dataclass
class SeasonImportEstimate:
    season_year: int
    league_pages_done: int = 0
    league_pages_remaining: int = 0
    league_pages_exact: bool = True
    listone_athletes: int = 0
    athletes_with_rows: int = 0
    athletes_checked: int = 0
    athletes_to_fill: int = 0
    athletes_to_fill_exact: bool = True
    rows_stored: int = 0

    @property
    def estimated_calls(self) -> int:
        return self.league_pages_remaining + self.athletes_to_fill

    @property
    def label(self) -> str:
        return season_label(self.season_year)


@dataclass
class ImportEstimate:
    current_season_year: int
    seasons: list[SeasonImportEstimate] = field(default_factory=list)

    @property
    def estimated_calls(self) -> int:
        return sum(season.estimated_calls for season in self.seasons)


def _fetches(session: Session, *, season_year: int, kind: str) -> list[AthleteSeasonImportFetch]:
    return list(
        session.scalars(
            select(AthleteSeasonImportFetch).where(
                AthleteSeasonImportFetch.season_year == season_year,
                AthleteSeasonImportFetch.kind == kind,
            )
        ).all()
    )


def _listone_provider_ids(session: Session, *, current_season_year: int) -> list[int]:
    return [
        int(value)
        for value in session.scalars(
            select(Athlete.provider_id)
            .join(RoleAssignment, RoleAssignment.athlete_id == Athlete.id)
            .where(RoleAssignment.season_year == current_season_year)
            .order_by(Athlete.provider_id)
        ).all()
    ]


def _provider_ids_with_rows(session: Session, *, season_year: int) -> set[int]:
    return {
        int(value)
        for value in session.scalars(
            select(AthleteSeasonStat.athlete_provider_id)
            .where(
                AthleteSeasonStat.season_year == season_year,
                AthleteSeasonStat.source == SOURCE_PROVIDER,
            )
            .distinct()
        ).all()
    }


def _fill_candidates(
    session: Session, *, season_year: int, listone: list[int]
) -> tuple[list[int], int, int]:
    """Calciatori del listone senza righe della stagione e non ancora cercati."""
    with_rows = _provider_ids_with_rows(session, season_year=season_year)
    checked = {
        int(row.athlete_provider_id)
        for row in _fetches(session, season_year=season_year, kind=KIND_ATHLETE)
        if row.athlete_provider_id is not None
    }
    candidates = [pid for pid in listone if pid not in with_rows and pid not in checked]
    in_listone = set(listone)
    return candidates, len(with_rows & in_listone), len(checked & in_listone)


def estimate_import(
    session: Session,
    *,
    current_season_year: int,
    competitions: tuple[int, ...] = MVP_LEAGUE_IDS,
) -> ImportEstimate:
    """Quante chiamate mancano, senza chiamare il fornitore (modalità «conta»)."""
    listone = _listone_provider_ids(session, current_season_year=current_season_year)
    result = ImportEstimate(current_season_year=current_season_year)
    for season_year in past_seasons(current_season_year):
        item = SeasonImportEstimate(season_year=season_year, listone_athletes=len(listone))
        pages = _fetches(session, season_year=season_year, kind=KIND_LEAGUE_PAGE)
        by_competition: dict[int, list[AthleteSeasonImportFetch]] = {}
        for row in pages:
            if row.competition_provider_id is not None:
                by_competition.setdefault(int(row.competition_provider_id), []).append(row)
        for competition in competitions:
            done = by_competition.get(competition, [])
            item.league_pages_done += len(done)
            totals = [row.page_total for row in done if row.page_total is not None]
            if totals:
                item.league_pages_remaining += max(0, max(totals) - len(done))
            else:
                item.league_pages_remaining += ESTIMATED_PAGES_PER_COMPETITION_SEASON
                item.league_pages_exact = False
        candidates, with_rows, checked = _fill_candidates(
            session, season_year=season_year, listone=listone
        )
        item.athletes_with_rows = with_rows
        item.athletes_checked = checked
        if item.league_pages_remaining > 0:
            # Le pagine mancanti copriranno buona parte del listone: stima, non conto esatto.
            item.athletes_to_fill = min(
                len(candidates), math.ceil(len(listone) * ESTIMATED_FILL_SHARE)
            )
            item.athletes_to_fill_exact = False
        else:
            item.athletes_to_fill = len(candidates)
        item.rows_stored = int(
            session.scalar(
                select(func.count())
                .select_from(AthleteSeasonStat)
                .where(
                    AthleteSeasonStat.season_year == season_year,
                    AthleteSeasonStat.source == SOURCE_PROVIDER,
                )
            )
            or 0
        )
        result.seasons.append(item)
    return result


# -- esecuzione ---------------------------------------------------------------


@dataclass
class ImportCounters:
    calls: int = 0
    league_pages: int = 0
    athletes_checked: int = 0
    athletes_found: int = 0
    rows_created: int = 0
    rows_updated: int = 0
    snapshots_created: int = 0
    errors: int = 0


@dataclass
class ImportRunResult:
    current_season_year: int
    seasons: tuple[int, ...]
    counters: ImportCounters
    stopped_reason: str | None = None

    @property
    def completed(self) -> bool:
        return self.stopped_reason is None


class _Stop(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


ProgressFn = Callable[[int, int, str], None]


class _Runner:
    def __init__(
        self,
        session: Session,
        client: ApiFootballClient,
        *,
        max_calls: int,
        on_progress: ProgressFn | None,
        checkpoint: Callable[[], None] | None,
        planned_calls: int,
    ) -> None:
        self.session = session
        self.client = client
        self.max_calls = max(0, max_calls)
        self.on_progress = on_progress
        self.checkpoint = checkpoint
        self.planned_calls = max(1, min(planned_calls, self.max_calls or 1))
        self.counters = ImportCounters()
        self._consecutive_errors = 0

    def progress(self, label: str) -> None:
        if self.on_progress is not None:
            self.on_progress(self.counters.calls, self.planned_calls, label)

    def call(self, params: dict[str, Any]) -> ProviderEnvelope | None:
        if self.counters.calls >= self.max_calls:
            raise _Stop(STOP_MAX_CALLS)
        self.counters.calls += 1
        try:
            envelope = self.client.get(PLAYERS_ENDPOINT, params, fetch_all_pages=False)
        except (ProviderRateLimitError, ProviderAuthError, ProviderConfigError):
            raise
        except ProviderError:
            self.counters.errors += 1
            self._consecutive_errors += 1
            get_metrics().incr(SEASON_IMPORT_CALLS_TOTAL, labels={"result": "error"})
            logger.warning(
                "season_history_import_call_failed",
                extra={"params": {key: str(value) for key, value in params.items()}},
            )
            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                raise _Stop(STOP_TOO_MANY_ERRORS) from None
            return None
        self._consecutive_errors = 0
        get_metrics().incr(SEASON_IMPORT_CALLS_TOTAL, labels={"result": "ok"})
        return envelope

    def store(
        self,
        envelope: ProviderEnvelope,
        *,
        season_year: int,
        request_key: str,
        kind: str,
        competition_provider_id: int | None = None,
        page: int | None = None,
        athlete_provider_id: int | None = None,
    ) -> int:
        snapshot, created = store_provider_snapshot(self.session, envelope)
        if created:
            self.counters.snapshots_created += 1
        rows = parse_season_rows(envelope, season_year=season_year)
        rows_created, rows_updated = upsert_provider_rows(
            self.session, rows, snapshot_id=snapshot.id
        )
        self.counters.rows_created += rows_created
        self.counters.rows_updated += rows_updated
        stmt = insert(AthleteSeasonImportFetch).values(
            request_key=request_key,
            kind=kind,
            season_year=season_year,
            competition_provider_id=competition_provider_id,
            page=page,
            athlete_provider_id=athlete_provider_id,
            results_count=envelope.results,
            page_total=envelope.paging.total if kind == KIND_LEAGUE_PAGE else None,
            snapshot_id=snapshot.id,
            fetched_at=datetime.now(UTC),
        )
        self.session.execute(
            stmt.on_conflict_do_nothing(constraint="uq_athlete_season_import_fetches_request_key")
        )
        self.session.flush()
        if self.checkpoint is not None:
            self.checkpoint()
        self._check_quota(envelope)
        return len(rows)

    def _check_quota(self, envelope: ProviderEnvelope) -> None:
        rate = envelope.rate_limit
        if rate is None or rate.remaining is None or not rate.limit:
            return
        if rate.remaining <= rate.limit * QUOTA_RESERVE_FRACTION:
            raise _Stop(STOP_QUOTA_RESERVE)


def _league_pages(
    runner: _Runner,
    *,
    season_year: int,
    competition_provider_id: int,
) -> None:
    done = {
        int(row.page or 0): row
        for row in runner.session.scalars(
            select(AthleteSeasonImportFetch).where(
                AthleteSeasonImportFetch.season_year == season_year,
                AthleteSeasonImportFetch.kind == KIND_LEAGUE_PAGE,
                AthleteSeasonImportFetch.competition_provider_id == competition_provider_id,
            )
        ).all()
    }
    known_totals = [row.page_total for row in done.values() if row.page_total]
    total = max(known_totals) if known_totals else None
    page = 1
    while True:
        if page not in done:
            label = f"Stagione {season_label(season_year)} · campionato {competition_provider_id}"
            envelope = runner.call(
                {"league": competition_provider_id, "season": season_year, "page": page}
            )
            if envelope is None:
                if total is None:
                    return  # senza la prima pagina non si sa quante sono: si riprova dopo
            else:
                runner.counters.league_pages += 1
                total = max(total or 0, envelope.paging.total or 1)
                runner.store(
                    envelope,
                    season_year=season_year,
                    request_key=league_page_key(competition_provider_id, season_year, page),
                    kind=KIND_LEAGUE_PAGE,
                    competition_provider_id=competition_provider_id,
                    page=page,
                )
                runner.progress(f"{label} · pagina {page}/{total}")
        if page >= (total or 1):
            return
        page += 1


def _fill_athletes(runner: _Runner, *, season_year: int, listone: list[int]) -> None:
    candidates, _, _ = _fill_candidates(runner.session, season_year=season_year, listone=listone)
    for index, provider_id in enumerate(candidates, start=1):
        envelope = runner.call({"id": provider_id, "season": season_year})
        if envelope is None:
            continue
        runner.counters.athletes_checked += 1
        found = runner.store(
            envelope,
            season_year=season_year,
            request_key=athlete_key(provider_id, season_year),
            kind=KIND_ATHLETE,
            athlete_provider_id=provider_id,
        )
        if found:
            runner.counters.athletes_found += 1
        runner.progress(
            f"Stagione {season_label(season_year)} · calciatori mancanti {index}/{len(candidates)}"
        )


def run_provider_import(
    session: Session,
    client: ApiFootballClient,
    *,
    current_season_year: int,
    max_calls: int = DEFAULT_MAX_CALLS,
    on_progress: ProgressFn | None = None,
    checkpoint: Callable[[], None] | None = None,
    competitions: tuple[int, ...] = MVP_LEAGUE_IDS,
) -> ImportRunResult:
    """Scarica le stagioni passate mancanti. Rieseguibile: salta le chiamate già registrate.

    ``checkpoint`` (es. ``session.commit``) gira dopo ogni chiamata salvata: un'interruzione
    non perde il lavoro fatto. Errori di quota/autenticazione del fornitore risalgono.
    """
    seasons = past_seasons(current_season_year)
    estimate = estimate_import(
        session, current_season_year=current_season_year, competitions=competitions
    )
    runner = _Runner(
        session,
        client,
        max_calls=max_calls,
        on_progress=on_progress,
        checkpoint=checkpoint,
        planned_calls=estimate.estimated_calls,
    )
    stopped: str | None = None
    try:
        for season_year in seasons:
            for competition in competitions:
                _league_pages(runner, season_year=season_year, competition_provider_id=competition)
        listone = _listone_provider_ids(session, current_season_year=current_season_year)
        for season_year in seasons:
            _fill_athletes(runner, season_year=season_year, listone=listone)
    except _Stop as stop:
        stopped = stop.reason
    session.flush()
    logger.info(
        "season_history_import_done",
        extra={
            "current_season_year": current_season_year,
            "calls": runner.counters.calls,
            "league_pages": runner.counters.league_pages,
            "athletes_checked": runner.counters.athletes_checked,
            "rows_created": runner.counters.rows_created,
            "rows_updated": runner.counters.rows_updated,
            "stopped_reason": stopped,
        },
    )
    return ImportRunResult(
        current_season_year=current_season_year,
        seasons=seasons,
        counters=runner.counters,
        stopped_reason=stopped,
    )
