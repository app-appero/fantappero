"""Persistenza idempotente dei voti statistici (EP07-01 / EP07-02)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from fantasy_ratings.bonus import (
    BonusMalusResult,
    compute_bonus_malus,
    reconstruct_total_from_stored,
)
from fantasy_ratings.bonus_config import BonusMalusConfig, default_bonus_config
from fantasy_ratings.config import FormulaConfig, default_formula_config
from fantasy_ratings.eligibility import evaluate_eligibility
from fantasy_ratings.exceptions import FantasyRatingError
from fantasy_ratings.formula import (
    RatingResult,
    compute_rating,
    reconstruct_raw_from_stored,
    round_to_step,
)
from fantasy_ratings.input import RelevantEvents
from fantasy_ratings.mapping import (
    bonus_input_from_stat,
    inputs_from_fixture_stats,
    own_goal_counts_by_provider_id,
)
from fantasy_ratings.models import PlayerMatchRating
from fantasy_ratings.schemas import ComputeRatingsResponse, PlayerMatchRatingResponse
from fantasy_ratings.validators import (
    validate_compute_target,
    validate_formula_snapshot,
    validate_minutes_threshold,
    validate_threshold_target,
)
from fantasy_turns.homologation import assert_fixture_not_homologated
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.fixtures.models import Fixture, MatchEvent, PlayerMatchStat

logger = get_logger(__name__)

RATINGS_COMPUTE_RUNS_TOTAL = "fantasy_ratings_compute_runs_total"
RATINGS_COMPUTE_VOTES_TOTAL = "fantasy_ratings_compute_votes_total"
RATINGS_COMPUTE_DURATION_SECONDS = "fantasy_ratings_compute_duration_seconds"

UpsertResult = str  # created | updated | unchanged | removed


@dataclass
class RatingComputeCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0

    def incr(self, result: UpsertResult) -> None:
        setattr(self, result, getattr(self, result) + 1)
        get_metrics().incr(RATINGS_COMPUTE_VOTES_TOTAL, labels={"result": result})


@dataclass
class RatingComputeResult:
    fixture_id: UUID
    fixture_provider_id: int
    formula_version: str
    counters: RatingComputeCounters = field(default_factory=RatingComputeCounters)


def _touch_updated_at(row: PlayerMatchRating) -> None:
    row.updated_at = datetime.now(UTC)


def _role_enum(role: str | None) -> FantasyRole | None:
    if role is None:
        return None
    return FantasyRole(role)


def _payload_equal(left: Any, right: Any) -> bool:
    return left == right


class FantasyRatingService:
    def __init__(
        self,
        session: Session,
        *,
        config: FormulaConfig | None = None,
        bonus_config: BonusMalusConfig | None = None,
    ) -> None:
        self._session = session
        self._config = config or default_formula_config()
        self._bonus_config = bonus_config or default_bonus_config()

    def compute_for_fixture(
        self,
        *,
        fixture_id: UUID | None = None,
        fixture_provider_id: int | None = None,
        league_id: UUID | None = None,
        minutes_threshold: int | None = None,
    ) -> ComputeRatingsResponse:
        validate_compute_target(
            fixture_id=fixture_id,
            fixture_provider_id=fixture_provider_id,
        )
        result = compute_fixture_ratings(
            self._session,
            fixture_id=fixture_id,
            fixture_provider_id=fixture_provider_id,
            config=self._config,
            bonus_config=self._bonus_config,
            league_id=league_id,
            minutes_threshold=minutes_threshold,
        )
        self._session.flush()
        return ComputeRatingsResponse(
            fixture_id=str(result.fixture_id),
            fixture_provider_id=result.fixture_provider_id,
            formula_version=result.formula_version,
            created=result.counters.created,
            updated=result.counters.updated,
            unchanged=result.counters.unchanged,
            removed=result.counters.removed,
            votes=result.counters.created + result.counters.updated + result.counters.unchanged,
        )

    def list_for_fixture(
        self,
        fixture_id: UUID,
        *,
        league_id: UUID | None = None,
        minutes_threshold: int | None = None,
    ) -> list[PlayerMatchRatingResponse]:
        fixture = self._session.get(Fixture, fixture_id)
        if fixture is None:
            raise FantasyRatingError("fixture_not_found", "Partita non trovata.")
        rows = self._session.scalars(
            select(PlayerMatchRating)
            .where(
                PlayerMatchRating.fixture_id == fixture_id,
                PlayerMatchRating.formula_version == self._config.version,
            )
            .order_by(PlayerMatchRating.athlete_provider_id.asc())
        ).all()
        overlay = _resolve_minutes_threshold(
            self._session,
            league_id=league_id,
            minutes_threshold=minutes_threshold,
        )
        return [_to_response(row, overlay_threshold=overlay, config=self._config) for row in rows]


def compute_fixture_ratings(
    session: Session,
    *,
    fixture_id: UUID | None = None,
    fixture_provider_id: int | None = None,
    config: FormulaConfig | None = None,
    bonus_config: BonusMalusConfig | None = None,
    league_id: UUID | None = None,
    minutes_threshold: int | None = None,
) -> RatingComputeResult:
    formula = config or default_formula_config()
    bonus_cfg = bonus_config or default_bonus_config()
    resolved = _resolve_minutes_threshold(
        session,
        league_id=league_id,
        minutes_threshold=minutes_threshold,
    )
    if resolved is not None:
        formula = formula.with_minutes_threshold(resolved)
    fixture = _load_fixture(
        session,
        fixture_id=fixture_id,
        fixture_provider_id=fixture_provider_id,
    )
    assert_fixture_not_homologated(session, fixture_id=fixture.id)
    counters = RatingComputeCounters()
    metrics = get_metrics()
    status = "ok"
    with Timer(metrics, RATINGS_COMPUTE_DURATION_SECONDS, labels={"version": formula.version}):
        try:
            stats = list(
                session.scalars(
                    select(PlayerMatchStat).where(PlayerMatchStat.fixture_id == fixture.id)
                ).all()
            )
            events = list(
                session.scalars(select(MatchEvent).where(MatchEvent.fixture_id == fixture.id)).all()
            )
            inputs = inputs_from_fixture_stats(
                fixture_provider_id=fixture.provider_id,
                stats=stats,
                events=events,
            )
            own_goal_counts = own_goal_counts_by_provider_id(events)
            kept_ids: set[int] = set()
            formula_snapshot = formula.as_dict()
            for player, stat in zip(inputs, stats, strict=True):
                rating = compute_rating(player, formula)
                bonus_input = bonus_input_from_stat(
                    fixture=fixture,
                    stat=stat,
                    role=rating.role,
                    own_goal_counts=own_goal_counts,
                )
                bonus = compute_bonus_malus(bonus_input, bonus_cfg, eligible=rating.eligible)
                _upsert_rating(
                    session,
                    fixture=fixture,
                    stat=stat,
                    rating=rating,
                    bonus=bonus,
                    formula_snapshot=formula_snapshot,
                    input_snapshot=player.as_input_snapshot(),
                    counters=counters,
                )
                kept_ids.add(stat.athlete_provider_id)

            stale_query = select(PlayerMatchRating).where(
                PlayerMatchRating.fixture_id == fixture.id,
                PlayerMatchRating.formula_version == formula.version,
            )
            if kept_ids:
                stale_query = stale_query.where(
                    PlayerMatchRating.athlete_provider_id.not_in(kept_ids)
                )
            for row in session.scalars(stale_query).all():
                session.delete(row)
                counters.incr("removed")
        except Exception:
            status = "error"
            raise
        finally:
            metrics.incr(
                RATINGS_COMPUTE_RUNS_TOTAL,
                labels={"version": formula.version, "result": status},
            )

    logger.info(
        "fantasy_ratings_compute_done",
        extra={
            "fixture_id": str(fixture.id),
            "fixture_provider_id": fixture.provider_id,
            "formula_version": formula.version,
            "minutes_threshold": formula.minutes_threshold,
            "created": counters.created,
            "updated": counters.updated,
            "unchanged": counters.unchanged,
            "removed": counters.removed,
        },
    )
    return RatingComputeResult(
        fixture_id=fixture.id,
        fixture_provider_id=fixture.provider_id,
        formula_version=formula.version,
        counters=counters,
    )


def _resolve_minutes_threshold(
    session: Session,
    *,
    league_id: UUID | None,
    minutes_threshold: int | None,
) -> int | None:
    validate_threshold_target(league_id=league_id, minutes_threshold=minutes_threshold)
    if minutes_threshold is not None:
        return validate_minutes_threshold(minutes_threshold)
    if league_id is None:
        return None
    from leagues.models.league_rules import LeagueRules

    rules = session.execute(
        select(LeagueRules).where(LeagueRules.league_id == league_id)
    ).scalar_one_or_none()
    if rules is None:
        raise FantasyRatingError("league_not_found", "Lega non trovata.")
    return validate_minutes_threshold(int(rules.minutes_threshold))


def _overlay_eligibility(
    row: PlayerMatchRating,
    *,
    threshold: int,
    config: FormulaConfig,
) -> tuple[bool, str, float | None]:
    payload = dict(row.input_json or {})
    relevant_events = payload.get("relevant_events")
    events_raw = relevant_events if isinstance(relevant_events, dict) else {}
    events = RelevantEvents(
        goal=bool(events_raw.get("goal")),
        assist=bool(events_raw.get("assist")),
        penalty_missed=bool(events_raw.get("penalty_missed")),
        own_goal=bool(events_raw.get("own_goal")),
        red_card=bool(events_raw.get("red_card")),
    )
    role = row.role.value if row.role else None
    minutes = payload.get("minutes", row.minutes)
    decision = evaluate_eligibility(
        minutes=int(minutes) if minutes is not None else None,
        substitute=bool(payload.get("substitute")),
        role=role,
        has_relevant_event=events.any_relevant(config.relevant_event_flags),
        entered_in_stoppage=bool(payload.get("entered_in_stoppage")),
        minutes_threshold=threshold,
        goalkeeper_starter_always_eligible=config.goalkeeper_starter_always_eligible,
    )
    display = round_to_step(row.raw, config.display_step) if decision.eligible else None
    return decision.eligible, decision.reason, display


def _load_fixture(
    session: Session,
    *,
    fixture_id: UUID | None,
    fixture_provider_id: int | None,
) -> Fixture:
    if fixture_id is not None:
        fixture = session.get(Fixture, fixture_id)
    else:
        fixture = session.execute(
            select(Fixture).where(Fixture.provider_id == fixture_provider_id)
        ).scalar_one_or_none()
    if fixture is None:
        raise FantasyRatingError("fixture_not_found", "Partita non trovata.")
    return fixture


def _upsert_rating(
    session: Session,
    *,
    fixture: Fixture,
    stat: PlayerMatchStat,
    rating: RatingResult,
    bonus: BonusMalusResult,
    formula_snapshot: dict[str, Any],
    input_snapshot: dict[str, Any],
    counters: RatingComputeCounters,
) -> PlayerMatchRating:
    validate_formula_snapshot(formula_snapshot)
    components = [item.as_dict() for item in rating.components]
    reconstructed = reconstruct_raw_from_stored(formula_snapshot, components)
    if reconstructed != rating.raw and abs(reconstructed - rating.raw) > 1e-9:
        raise FantasyRatingError(
            "rating_not_reconstructable",
            "Il voto calcolato non è ricostruibile da formula e componenti.",
        )

    bonus_components = bonus.as_dict()
    bonus_total = reconstruct_total_from_stored(bonus_components)
    if abs(bonus_total - bonus.total) > 1e-9:
        raise FantasyRatingError(
            "bonus_malus_not_reconstructable",
            "Il bonus/malus calcolato non è ricostruibile dai componenti.",
        )
    fantasy_score = (
        round(rating.display + bonus_total, 10)
        if rating.eligible and rating.display is not None
        else None
    )

    row = session.execute(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id == fixture.id,
            PlayerMatchRating.athlete_provider_id == stat.athlete_provider_id,
            PlayerMatchRating.formula_version == rating.formula_version,
        )
    ).scalar_one_or_none()

    role = _role_enum(rating.role)
    stats_hash = stat.stats_hash
    if row is None:
        row = PlayerMatchRating(
            fixture_id=fixture.id,
            athlete_id=stat.athlete_id,
            athlete_provider_id=stat.athlete_provider_id,
            formula_version=rating.formula_version,
            role=role,
            minutes=rating.minutes,
            eligible=rating.eligible,
            eligibility_reason=rating.eligibility_reason,
            base=rating.base,
            raw_before_clamp=rating.raw_before_clamp,
            raw=rating.raw,
            display=rating.display,
            stats_hash=stats_hash,
            formula_json=formula_snapshot,
            input_json=input_snapshot,
            components_json=components,
            bonus_config_version=bonus.config_version,
            bonus_malus_json=bonus_components,
            bonus_malus_total=bonus_total,
            fantasy_score=fantasy_score,
        )
        session.add(row)
        counters.incr("created")
        return row

    unchanged = (
        row.stats_hash == stats_hash
        and row.role == role
        and row.minutes == rating.minutes
        and row.eligible is rating.eligible
        and row.eligibility_reason == rating.eligibility_reason
        and _payload_equal(row.formula_json, formula_snapshot)
        and _payload_equal(row.input_json, input_snapshot)
        and _payload_equal(row.components_json, components)
        and row.bonus_config_version == bonus.config_version
        and _payload_equal(row.bonus_malus_json, bonus_components)
        and row.bonus_malus_total == bonus_total
        and row.fantasy_score == fantasy_score
    )
    if unchanged:
        counters.incr("unchanged")
        return row

    row.athlete_id = stat.athlete_id
    row.role = role
    row.minutes = rating.minutes
    row.eligible = rating.eligible
    row.eligibility_reason = rating.eligibility_reason
    row.base = rating.base
    row.raw_before_clamp = rating.raw_before_clamp
    row.raw = rating.raw
    row.display = rating.display
    row.stats_hash = stats_hash
    row.formula_json = formula_snapshot
    row.input_json = input_snapshot
    row.components_json = components
    row.bonus_config_version = bonus.config_version
    row.bonus_malus_json = bonus_components
    row.bonus_malus_total = bonus_total
    row.fantasy_score = fantasy_score
    _touch_updated_at(row)
    counters.incr("updated")
    return row


def _to_response(
    row: PlayerMatchRating,
    *,
    overlay_threshold: int | None = None,
    config: FormulaConfig | None = None,
) -> PlayerMatchRatingResponse:
    eligible = row.eligible
    reason = row.eligibility_reason
    display = row.display
    formula_payload = dict(row.formula_json)
    if overlay_threshold is not None:
        formula = config or default_formula_config()
        eligible, reason, display = _overlay_eligibility(
            row,
            threshold=overlay_threshold,
            config=formula,
        )
        formula_payload = {**formula_payload, "minutes_threshold": overlay_threshold}
    fantasy_score = row.fantasy_score
    if overlay_threshold is not None and eligible != row.eligible:
        # La soglia overlay cambia l'eleggibilità: senza voto niente fantavoto;
        # con voto usiamo il bonus/malus persistito (il ricalcolo reale avviene
        # solo tramite POST /fantasy-ratings/compute).
        fantasy_score = (
            round(display + row.bonus_malus_total, 10) if eligible and display is not None else None
        )
    return PlayerMatchRatingResponse(
        id=str(row.id),
        fixture_id=str(row.fixture_id),
        athlete_id=str(row.athlete_id) if row.athlete_id else None,
        athlete_provider_id=row.athlete_provider_id,
        formula_version=row.formula_version,
        role=row.role.value if row.role else None,
        minutes=row.minutes,
        eligible=eligible,
        eligibility_reason=reason,
        base=row.base,
        raw_before_clamp=row.raw_before_clamp,
        raw=row.raw,
        display=display,
        stats_hash=row.stats_hash,
        formula=formula_payload,
        input=dict(row.input_json),
        components=list(row.components_json),
        bonus_config_version=row.bonus_config_version,
        bonus_malus=list(row.bonus_malus_json),
        bonus_malus_total=row.bonus_malus_total,
        fantasy_score=fantasy_score,
    )
