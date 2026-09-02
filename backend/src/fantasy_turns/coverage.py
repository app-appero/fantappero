"""Validità di un Turno Europeo in base alla copertura formazione.

Un turno non è più una semplice finestra di calendario con abbastanza partite:
è valido solo se i fantallenatori possono davvero schierare una formazione.
La copertura si misura sugli **11 titolari**, non sul numero grezzo di
giocatori disponibili: avere 11 attaccanti che giocano non permette comunque
di schierare un modulo valido.

Regola (configurabile per lega da `LeagueRules.turn_coverage_threshold`):
una finestra è un turno valido se **ogni** squadra della lega copre almeno la
soglia degli 11 titolari con i propri giocatori il cui club reale gioca in
quella finestra. Se nessuna squadra ha giocatori in rosa (asta non ancora
svolta) la finestra non è valida: niente turni prima dell'asta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from fantasy_lineups.rules import GOALKEEPER_STARTERS, MODULE_OUTFIELD, STARTER_COUNT
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from leagues.models.league_competition import LeagueCompetition
from sports_data.catalog.models import SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.roster.models import SquadMembership

#: Soglia di copertura usata quando la lega non ne ha una configurata.
DEFAULT_COVERAGE_THRESHOLD = 0.75


@dataclass(frozen=True)
class RosteredPlayer:
    """Un giocatore in rosa con il ruolo effettivo e il club reale."""

    athlete_id: UUID
    role: FantasyRole
    club_id: UUID | None


def lineup_coverage(available_by_role: dict[FantasyRole, int]) -> float:
    """Frazione degli 11 titolari copribile dai giocatori disponibili.

    Prova tutti i moduli approvati e tiene il migliore: un modulo è utile
    solo se i ruoli disponibili lo permettono, quindi la copertura è il
    massimo ottenibile e non una media fra moduli.
    """
    goalkeepers = min(GOALKEEPER_STARTERS, available_by_role.get(FantasyRole.P, 0))
    defenders = available_by_role.get(FantasyRole.D, 0)
    midfielders = available_by_role.get(FantasyRole.C, 0)
    forwards = available_by_role.get(FantasyRole.A, 0)

    best_outfield = 0
    for need_def, need_mid, need_fwd in MODULE_OUTFIELD.values():
        filled = (
            min(need_def, defenders) + min(need_mid, midfielders) + min(need_fwd, forwards)
        )
        best_outfield = max(best_outfield, filled)

    return (goalkeepers + best_outfield) / STARTER_COUNT


def coverage_threshold_for(threshold: float | None) -> float:
    return DEFAULT_COVERAGE_THRESHOLD if threshold is None else float(threshold)


def window_is_valid(coverages: list[float], threshold: float) -> bool:
    """Vero se **ogni** squadra raggiunge la soglia.

    Una lista vuota significa "nessuna squadra con giocatori in rosa": la
    finestra non è un turno valido (regola "niente turni prima dell'asta").
    """
    if not coverages:
        return False
    return all(coverage >= threshold for coverage in coverages)


def load_league_rosters(
    session: Session,
    league: League,
    *,
    current_round: int = 0,
) -> dict[UUID, list[RosteredPlayer]]:
    """Rose della lega con ruolo effettivo e club reale, per squadra.

    Riusa `resolve_effective_athlete_roles` (che applica già gli override di
    ruolo di lega) e ricade su `SquadMembership` quando il listone non porta
    con sé il club, con lo stesso criterio delle formazioni: tesseramento
    attivo e non terminato nella stagione della lega.
    """
    slots = session.execute(
        select(FantasyRosterSlot.fantasy_team_id, FantasyRosterSlot.athlete_id)
        .join(FantasyTeam, FantasyTeam.id == FantasyRosterSlot.fantasy_team_id)
        .where(
            FantasyTeam.league_id == league.id,
            FantasyRosterSlot.athlete_id.is_not(None),
        )
    ).all()
    if not slots:
        return {}

    athlete_ids = [athlete_id for _, athlete_id in slots]
    competition_ids = set(
        session.scalars(
            select(LeagueCompetition.competition_id).where(
                LeagueCompetition.league_id == league.id
            )
        ).all()
    )
    roles = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=athlete_ids,
        season_year=league.season_year,
        current_round=current_round,
        competition_ids=competition_ids or None,
    )

    missing_club = [
        athlete_id
        for athlete_id in set(athlete_ids)
        if athlete_id in roles and roles[athlete_id].club_id is None
    ]
    fallback_clubs = _clubs_from_squad_memberships(session, league, missing_club)

    rosters: dict[UUID, list[RosteredPlayer]] = {}
    for team_id, athlete_id in slots:
        resolved = roles.get(athlete_id)
        if resolved is None:
            # Atleta senza assegnazione di ruolo nel listone: non schierabile,
            # non contribuisce alla copertura.
            continue
        club_id = resolved.club_id or fallback_clubs.get(athlete_id)
        rosters.setdefault(team_id, []).append(
            RosteredPlayer(athlete_id=athlete_id, role=resolved.role, club_id=club_id)
        )
    return rosters


def _clubs_from_squad_memberships(
    session: Session,
    league: League,
    athlete_ids: list[UUID],
) -> dict[UUID, UUID]:
    if not athlete_ids:
        return {}
    rows = session.execute(
        select(SquadMembership.athlete_id, SquadMembership.club_id)
        .join(SportSeason, SportSeason.id == SquadMembership.sport_season_id)
        .where(
            SquadMembership.athlete_id.in_(athlete_ids),
            SquadMembership.is_active.is_(True),
            SquadMembership.ended_at.is_(None),
            SportSeason.year == league.season_year,
        )
        .order_by(SquadMembership.created_at.desc())
    ).all()
    clubs: dict[UUID, UUID] = {}
    for athlete_id, club_id in rows:
        clubs.setdefault(athlete_id, club_id)
    return clubs


def clubs_playing_between(
    session: Session,
    league: League,
    *,
    window_start_at: datetime,
    window_end_at: datetime,
) -> set[UUID]:
    """Club delle competizioni della lega che giocano nella finestra."""
    competition_ids = session.scalars(
        select(LeagueCompetition.competition_id).where(LeagueCompetition.league_id == league.id)
    ).all()
    if not competition_ids:
        return set()
    season_ids = session.scalars(
        select(SportSeason.id).where(
            SportSeason.competition_id.in_(competition_ids),
            SportSeason.year == league.season_year,
        )
    ).all()
    if not season_ids:
        return set()
    rows = session.execute(
        select(Fixture.home_club_id, Fixture.away_club_id).where(
            Fixture.sport_season_id.in_(season_ids),
            Fixture.kickoff_at >= window_start_at,
            Fixture.kickoff_at < window_end_at,
        )
    ).all()
    clubs: set[UUID] = set()
    for home_club_id, away_club_id in rows:
        if home_club_id is not None:
            clubs.add(home_club_id)
        if away_club_id is not None:
            clubs.add(away_club_id)
    return clubs


def coverage_by_team(
    rosters: dict[UUID, list[RosteredPlayer]],
    playing_clubs: set[UUID],
) -> dict[UUID, float]:
    """Copertura degli 11 titolari per ogni squadra, nella finestra data."""
    coverages: dict[UUID, float] = {}
    for team_id, players in rosters.items():
        available: dict[FantasyRole, int] = {}
        for player in players:
            if player.club_id is None or player.club_id not in playing_clubs:
                continue
            available[player.role] = available.get(player.role, 0) + 1
        coverages[team_id] = lineup_coverage(available)
    return coverages
