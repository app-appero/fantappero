"""Compute and persist round-level H2H results (EP07-05 / FR-SCO-03).

Sums the fantavoti of the effective eleven (EP07-04) for each side of a
scontro diretto, converts the total to fantasy goals, and stores the
provisional result on the calendar slot. Idempotent: a recompute (e.g. after
a rating correction) overwrites the existing result instead of duplicating
it, so it stays deterministic (FR-SCO-03 criteri di accettazione).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from fantasy_lineups.models import EffectiveLineup
from fantasy_ratings.config import default_formula_config
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.models import FantasyTeam
from fantasy_turns.homologation import assert_round_not_homologated
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.calendar_round_mapping import h2h_round_numbers_for_round
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.scoring import MatchOutcome
from leagues.standings_service import compute_league_standings
from sports_data.fixtures.models import Fixture

# API-Football terminal "finished" statuses. Live/not-started fixtures keep the
# round's result provisional (FR-SCO-03: "distingue componenti definitive e
# ancora in attesa").
FINISHED_FIXTURE_STATUSES = frozenset({"FT", "AET", "PEN"})

UpsertResult = str  # created | updated | unchanged


@dataclass
class ScoringCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0

    def incr(self, result: UpsertResult) -> None:
        setattr(self, result, getattr(self, result) + 1)


@dataclass
class RoundScoringResult:
    round_id: UUID
    league_id: UUID
    result_final: bool
    matchups: int
    counters: ScoringCounters = field(default_factory=ScoringCounters)


def compute_round_results(
    session: Session,
    *,
    round_id: UUID,
    formula_version: str | None = None,
) -> RoundScoringResult:
    fantasy_round = session.get(FantasyRound, round_id)
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")
    assert_round_not_homologated(fantasy_round)

    calendar = session.execute(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).scalar_one_or_none()
    if calendar is None:
        raise ValidationAuthError("Calendario di lega non trovato.", code="calendar_not_found")

    version = formula_version or default_formula_config().version
    fixture_rows = list(
        session.execute(
            select(Fixture.id, Fixture.status_short)
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
    )
    fixture_ids = [row[0] for row in fixture_rows]
    result_final = bool(fixture_rows) and all(
        (status or "").upper() in FINISHED_FIXTURE_STATUSES for _, status in fixture_rows
    )

    # Giornate H2H ospitate da questo turno europeo: per finestra sui
    # calendari ancorati, per numero progressivo su quelli storici.
    h2h_round_numbers = h2h_round_numbers_for_round(
        session, calendar=calendar, fantasy_round=fantasy_round
    )
    slots = (
        []
        if not h2h_round_numbers
        else list(
            session.scalars(
                select(LeagueCalendarSlot).where(
                    LeagueCalendarSlot.calendar_id == calendar.id,
                    LeagueCalendarSlot.round_number.in_(h2h_round_numbers),
                    LeagueCalendarSlot.is_bye.is_(False),
                )
            ).all()
        )
    )

    counters = ScoringCounters()
    for slot in slots:
        home_team = _team_for_membership(session, slot.home_membership_id)
        away_team = _team_for_membership(session, slot.away_membership_id)
        home_lineup = _effective_lineup(session, round_id, home_team.id) if home_team else None
        away_lineup = _effective_lineup(session, round_id, away_team.id) if away_team else None
        if home_lineup is None or away_lineup is None:
            counters.skipped += 1
            continue

        home_points = _team_points(session, home_lineup, fixture_ids, version)
        away_points = _team_points(session, away_lineup, fixture_ids, version)
        outcome = MatchOutcome.from_points(home_points=home_points, away_points=away_points)

        _upsert_slot_result(
            slot,
            home_points=home_points,
            away_points=away_points,
            outcome=outcome,
            result_final=result_final,
            counters=counters,
        )

    session.flush()
    # Pipeline naturale EP07-05 → EP07-06: dopo i risultati H2H la classifica
    # viene ricostruita dall'origine (solo slot con result_final).
    compute_league_standings(session, league_id=fantasy_round.league_id)
    session.flush()
    return RoundScoringResult(
        round_id=round_id,
        league_id=fantasy_round.league_id,
        result_final=result_final,
        matchups=len(slots),
        counters=counters,
    )


def _team_for_membership(session: Session, membership_id: UUID | None) -> FantasyTeam | None:
    if membership_id is None:
        return None
    return session.execute(
        select(FantasyTeam).where(FantasyTeam.membership_id == membership_id)
    ).scalar_one_or_none()


def _effective_lineup(
    session: Session, round_id: UUID, fantasy_team_id: UUID
) -> EffectiveLineup | None:
    return session.execute(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == round_id,
            EffectiveLineup.fantasy_team_id == fantasy_team_id,
        )
    ).scalar_one_or_none()


def _team_points(
    session: Session,
    lineup: EffectiveLineup,
    fixture_ids: list[UUID],
    formula_version: str,
) -> float:
    athlete_ids = [UUID(item) for item in lineup.effective_starter_ids]
    if not athlete_ids or not fixture_ids:
        return 0.0
    rows = session.scalars(
        select(PlayerMatchRating).where(
            PlayerMatchRating.athlete_id.in_(athlete_ids),
            PlayerMatchRating.fixture_id.in_(fixture_ids),
            PlayerMatchRating.formula_version == formula_version,
        )
    ).all()
    scores = {row.athlete_id: row.fantasy_score for row in rows}
    return sum(scores.get(athlete_id) or 0.0 for athlete_id in athlete_ids)


def _upsert_slot_result(
    slot: LeagueCalendarSlot,
    *,
    home_points: float,
    away_points: float,
    outcome: MatchOutcome,
    result_final: bool,
    counters: ScoringCounters,
) -> None:
    unchanged = (
        slot.home_score == home_points
        and slot.away_score == away_points
        and slot.home_fantasy_goals == outcome.home_fantasy_goals
        and slot.away_fantasy_goals == outcome.away_fantasy_goals
        and slot.outcome == outcome.outcome
        and slot.result_final == result_final
    )
    if unchanged:
        counters.incr("unchanged")
        return

    was_computed = slot.outcome is not None
    slot.home_score = home_points
    slot.away_score = away_points
    slot.home_fantasy_goals = outcome.home_fantasy_goals
    slot.away_fantasy_goals = outcome.away_fantasy_goals
    slot.outcome = outcome.outcome
    slot.result_final = result_final
    slot.result_computed_at = datetime.now(UTC)
    counters.incr("updated" if was_computed else "created")
