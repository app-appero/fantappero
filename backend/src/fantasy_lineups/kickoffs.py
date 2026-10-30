"""Kickoff reali per atleta, condiviso tra salvataggio formazione e job periodici.

Estratto da ``fantasy_lineups.service.FantasyLineupService._athlete_kickoffs``
perché serve anche fuori da un `LeagueAccess` autenticato (es.
``LineupLockReminderService``, che gira come job periodico su ogni squadra
di ogni lega) — nessun cambio di comportamento rispetto all'originale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fantasy_turns.models import FantasyRoundFixture
from sports_data.catalog.models import SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import SquadMembership

__all__ = ["KickoffRef", "athlete_kickoffs"]


@dataclass(frozen=True)
class KickoffRef:
    kickoff_at: datetime | None
    status_short: str | None
    lock_latched: bool = False


def athlete_kickoffs(
    session: Session,
    *,
    round_id: UUID,
    season_year: int,
    athlete_ids: list[UUID],
    for_update: bool = False,
) -> dict[UUID, KickoffRef]:
    if not athlete_ids:
        return {}
    links = session.scalars(
        select(FantasyRoundFixture)
        .options(selectinload(FantasyRoundFixture.fixture))
        .where(
            FantasyRoundFixture.round_id == round_id,
            FantasyRoundFixture.excluded_at.is_(None),
        )
    ).all()
    locked_fixtures_by_id: dict[UUID, Fixture] = {}
    if for_update:
        fixture_ids = {link.fixture_id for link in links if link.fixture_id is not None}
        if fixture_ids:
            # Blocca le righe delle partite coinvolte finché la richiesta non
            # fa commit: un aggiornamento concorrente del kickoff/stato (es.
            # lo scheduler dati sportivi) deve attendere questa transazione
            # invece di intrufolarsi tra la lettura e il salvataggio.
            locked = session.scalars(
                select(Fixture).where(Fixture.id.in_(fixture_ids)).with_for_update()
            ).all()
            locked_fixtures_by_id = {fixture.id: fixture for fixture in locked}
    fixture_by_club: dict[UUID, tuple[Fixture, FantasyRoundFixture]] = {}
    for link in links:
        fixture = locked_fixtures_by_id.get(link.fixture_id) if for_update else link.fixture
        if fixture is None:
            continue
        for club_id in (fixture.home_club_id, fixture.away_club_id):
            current = fixture_by_club.get(club_id)
            if current is None:
                fixture_by_club[club_id] = (fixture, link)
                continue
            current_fixture = current[0]
            if fixture.kickoff_at is None:
                continue
            current_kickoff = current_fixture.kickoff_at
            if current_kickoff is None or fixture.kickoff_at < current_kickoff:
                fixture_by_club[club_id] = (fixture, link)

    club_by_athlete: dict[UUID, UUID] = {}
    assignments = session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id.in_(athlete_ids),
            RoleAssignment.season_year == season_year,
        )
    ).all()
    for assignment in assignments:
        if assignment.club_id is not None:
            club_by_athlete[assignment.athlete_id] = assignment.club_id

    missing = [athlete_id for athlete_id in athlete_ids if athlete_id not in club_by_athlete]
    if missing:
        memberships = session.scalars(
            select(SquadMembership)
            .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
            .where(
                SquadMembership.athlete_id.in_(missing),
                SquadMembership.is_active.is_(True),
                SquadMembership.ended_at.is_(None),
                SportSeason.year == season_year,
            )
        ).all()
        for membership in memberships:
            club_by_athlete.setdefault(membership.athlete_id, membership.club_id)

    result: dict[UUID, KickoffRef] = {}
    for athlete_id, club_id in club_by_athlete.items():
        mapped = fixture_by_club.get(club_id)
        if mapped is None:
            continue
        fixture, link = mapped
        result[athlete_id] = KickoffRef(
            kickoff_at=fixture.kickoff_at,
            status_short=fixture.status_short,
            lock_latched=link.lock_latched_at is not None,
        )
    return result
