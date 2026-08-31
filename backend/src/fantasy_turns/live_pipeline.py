"""Automatic provider-to-standings orchestration for fantasy matchdays.

This module composes the existing idempotent domain services.  It does not
introduce a second scoring formula: provider snapshots are normalized first,
then ratings, effective lineups, H2H results, standings and homologation run
in that order inside one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import FantasyRoundHomologationStatus, FantasyTurnStatus
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_turns.homologation_service import homologate_round
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.scoring_service import compute_round_results
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.fixtures.models import Fixture, PlayerMatchStat

logger = get_logger(__name__)

STARTED_FIXTURE_STATUSES = frozenset(
    {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "FT", "AET", "PEN"}
)


@dataclass
class LivePipelineResult:
    rounds_considered: int = 0
    rounds_processed: int = 0
    rounds_finalized: int = 0
    fixtures_scored: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "roundsConsidered": self.rounds_considered,
            "roundsProcessed": self.rounds_processed,
            "roundsFinalized": self.rounds_finalized,
            "fixturesScored": self.fixtures_scored,
            "errors": list(self.errors),
        }


def process_live_fantasy_rounds(session: Session) -> LivePipelineResult:
    """Refresh every started, non-homologated round.

    A savepoint isolates one league from another: malformed data in a single
    round is reported and does not prevent other live leagues from updating.
    """
    round_rows = list(
        session.execute(
            select(FantasyRound.id, FantasyRound.league_id)
            .join(FantasyRoundFixture, FantasyRoundFixture.round_id == FantasyRound.id)
            .join(Fixture, Fixture.id == FantasyRoundFixture.fixture_id)
            .where(
                FantasyRound.homologation_status
                == FantasyRoundHomologationStatus.PROVISIONAL,
                FantasyRound.status != FantasyTurnStatus.SKIPPED,
                FantasyRoundFixture.excluded_at.is_(None),
                Fixture.status_short.in_(STARTED_FIXTURE_STATUSES),
            )
            .distinct()
            .order_by(FantasyRound.id.asc())
        ).all()
    )
    result = LivePipelineResult(rounds_considered=len(round_rows))

    for round_id, league_id in round_rows:
        try:
            with session.begin_nested():
                fixture_ids = list(
                    session.scalars(
                        select(FantasyRoundFixture.fixture_id).where(
                            FantasyRoundFixture.round_id == round_id,
                            FantasyRoundFixture.excluded_at.is_(None),
                        )
                    ).all()
                )
                fixtures_with_stats = set(
                    session.scalars(
                        select(PlayerMatchStat.fixture_id)
                        .where(PlayerMatchStat.fixture_id.in_(fixture_ids))
                        .distinct()
                    ).all()
                )
                for fixture_id in fixture_ids:
                    if fixture_id not in fixtures_with_stats:
                        continue
                    compute_fixture_ratings(
                        session,
                        fixture_id=fixture_id,
                        league_id=league_id,
                    )
                    result.fixtures_scored += 1

                compute_round_effective_lineups(session, round_id=round_id)
                scoring = compute_round_results(session, round_id=round_id)
                result.rounds_processed += 1

                if scoring.result_final and scoring.counters.skipped == 0:
                    homologate_round(
                        session,
                        round_id=round_id,
                        actor_id=None,
                        automatic=True,
                    )
                    result.rounds_finalized += 1
        except ValidationAuthError as exc:
            result.errors.append({"roundId": str(round_id), "code": exc.code})
            logger.warning(
                "fantasy_live_pipeline_round_skipped",
                extra={"round_id": str(round_id), "result": exc.code},
            )
        except Exception as exc:  # noqa: BLE001 - isolate a single live league
            result.errors.append({"roundId": str(round_id), "code": type(exc).__name__})
            logger.exception(
                "fantasy_live_pipeline_round_failed",
                extra={"round_id": str(round_id)},
            )

    get_metrics().incr(
        "fantasy_live_pipeline_runs_total",
        labels={"result": "partial" if result.errors else "success"},
    )
    logger.info("fantasy_live_pipeline_completed", extra=result.as_dict())
    return result


__all__ = ["LivePipelineResult", "process_live_fantasy_rounds"]
