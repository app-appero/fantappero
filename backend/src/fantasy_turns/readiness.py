"""Authoritative readiness checks for live and final fantasy scoring.

The provider status alone is not enough to close a fantasy round: a fixture
can be marked ``FT`` before its per-player statistics have reached our
normalized store. Keeping this rule in one place prevents scoring and
homologation from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy_turns.models import FantasyRoundFixture
from sports_data.fixtures.models import Fixture, PlayerMatchStat

FINISHED_FIXTURE_STATUSES = frozenset({"FT", "AET", "PEN"})
LIVE_FIXTURE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"})


@dataclass(frozen=True)
class RoundReadiness:
    fixture_ids: tuple[UUID, ...]
    all_fixtures_finished: bool
    all_statistics_available: bool

    @property
    def final_data_ready(self) -> bool:
        return (
            bool(self.fixture_ids)
            and self.all_fixtures_finished
            and self.all_statistics_available
        )


def evaluate_round_readiness(session: Session, *, round_id: UUID) -> RoundReadiness:
    rows = list(
        session.execute(
            select(
                Fixture.id,
                Fixture.status_short,
                Fixture.home_club_id,
                Fixture.away_club_id,
            )
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
    )
    fixture_ids = tuple(row.id for row in rows)
    all_finished = bool(rows) and all(
        (row.status_short or "").upper() in FINISHED_FIXTURE_STATUSES for row in rows
    )

    stats_clubs_by_fixture: dict[UUID, set[UUID]] = {}
    if fixture_ids:
        for fixture_id, club_id in session.execute(
            select(PlayerMatchStat.fixture_id, PlayerMatchStat.club_id)
            .where(
                PlayerMatchStat.fixture_id.in_(fixture_ids),
                PlayerMatchStat.club_id.is_not(None),
            )
            .distinct()
        ).all():
            if club_id is not None:
                stats_clubs_by_fixture.setdefault(fixture_id, set()).add(club_id)

    all_statistics_available = bool(rows) and all(
        {row.home_club_id, row.away_club_id}.issubset(
            stats_clubs_by_fixture.get(row.id, set())
        )
        for row in rows
    )
    return RoundReadiness(
        fixture_ids=fixture_ids,
        all_fixtures_finished=all_finished,
        all_statistics_available=all_statistics_available,
    )


def round_has_live_fixture(session: Session, *, round_id: UUID) -> bool:
    statuses = session.scalars(
        select(Fixture.status_short)
        .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
        .where(
            FantasyRoundFixture.round_id == round_id,
            FantasyRoundFixture.excluded_at.is_(None),
        )
    ).all()
    return any((status or "").upper() in LIVE_FIXTURE_STATUSES for status in statuses)


__all__ = [
    "FINISHED_FIXTURE_STATUSES",
    "LIVE_FIXTURE_STATUSES",
    "RoundReadiness",
    "evaluate_round_readiness",
    "round_has_live_fixture",
]
