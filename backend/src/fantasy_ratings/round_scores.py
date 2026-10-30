"""Voto fantacalcistico per-atleta di un turno europeo, per qualunque consumatore.

Estratto da ``leagues.h2h_matchday_service`` (dove è nato per /turni) perché
riusato anche da ``fantasy_lineups`` per mostrare i voti sulla pagina
Formazione — nessun cambio di comportamento rispetto all'originale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from fantasy_ratings.config import default_formula_config
from fantasy_ratings.models import PlayerMatchRating
from fantasy_turns.live_view import RawTimelineEvent, substitution_minutes
from fantasy_turns.models import FantasyRoundFixture
from fantasy_turns.readiness import FINISHED_FIXTURE_STATUSES
from sports_data.fixtures.models import Fixture, MatchEvent, PlayerMatchStat
from sports_data.roster.models import SquadMembership

__all__ = ["RoundAthleteScore", "compute_round_athlete_scores"]


@dataclass(frozen=True)
class RoundAthleteScore:
    fantasy_score: float | None = None
    base_score: float | None = None
    bonus_total: float = 0.0
    malus_total: float = 0.0
    bonus_malus: tuple[dict[str, object], ...] = ()
    real_team_name: str | None = None
    fixture_status: str | None = None
    fixture_status_label: str = "Partita non associata"
    score_final: bool = False
    kickoff_at: datetime | None = None
    substituted_out_minute: int | None = None
    substituted_in_minute: int | None = None


def _substitution_minutes_for_fixtures(
    session: Session,
    *,
    fixture_ids: list[UUID],
) -> tuple[dict[UUID, int], dict[UUID, int]]:
    """Minuto di uscita/ingresso per atleta, su tutte le fixture del turno.

    Riusa ``fantasy_turns.live_view.substitution_minutes`` (stessa logica
    del badge "sostituito" sulla pagina Turni) invece di duplicarla: qui
    serve per lo stesso badge sulla pagina di uno scontro H2H
    (``H2HPlayerScoreResponse``), che legge i voti da questo modulo e non
    dalla pipeline live.
    """
    rows = session.execute(
        select(
            MatchEvent.athlete_id,
            MatchEvent.related_athlete_id,
            MatchEvent.event_type,
            MatchEvent.minute_elapsed,
            MatchEvent.is_active,
            MatchEvent.retracted_at,
        ).where(MatchEvent.fixture_id.in_(fixture_ids))
    ).all()
    events = [
        RawTimelineEvent(
            id="",
            minute_elapsed=minute_elapsed,
            minute_extra=None,
            event_type=event_type,
            event_detail=None,
            scoring_kind=None,
            club_id=None,
            club_name=None,
            athlete_id=None if athlete_id is None else str(athlete_id),
            athlete_name=None,
            related_athlete_id=None if related_athlete_id is None else str(related_athlete_id),
            related_athlete_name=None,
            comments=None,
            is_active=is_active,
            retracted_at=retracted_at,
        )
        for (
            athlete_id,
            related_athlete_id,
            event_type,
            minute_elapsed,
            is_active,
            retracted_at,
        ) in rows
    ]
    out_minutes, in_minutes = substitution_minutes(events)
    return (
        {UUID(athlete_id): minute for athlete_id, minute in out_minutes.items()},
        {UUID(athlete_id): minute for athlete_id, minute in in_minutes.items()},
    )


def _fixture_status_label(status: str | None) -> str:
    normalized = (status or "").upper()
    if normalized in FINISHED_FIXTURE_STATUSES:
        return "Terminata"
    if normalized in {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}:
        return "LIVE"
    if normalized in {"PST", "SUSP"}:
        return "Rinviata o sospesa"
    if normalized in {"CANC", "ABD", "AWD", "WO"}:
        return "Non disputata"
    if normalized in {"NS", "TBD"}:
        return "Da giocare"
    return "Stato non disponibile"


def compute_round_athlete_scores(
    session: Session,
    round_id: UUID,
    *,
    league_id: UUID,
) -> dict[UUID, RoundAthleteScore]:
    version = default_formula_config().version
    fixtures = list(
        session.scalars(
            select(Fixture)
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
            .options(selectinload(Fixture.home_club), selectinload(Fixture.away_club))
            .order_by(Fixture.kickoff_at.asc(), Fixture.id.asc())
        ).all()
    )
    fixture_ids = [fixture.id for fixture in fixtures]
    if not fixture_ids:
        return {}

    fixture_by_id = {fixture.id: fixture for fixture in fixtures}
    substitution_out_by_athlete, substitution_in_by_athlete = _substitution_minutes_for_fixtures(
        session, fixture_ids=fixture_ids
    )
    # `fixtures` è già ordinato per kickoff crescente (riga sopra): con
    # `setdefault` un club con doppio turno nella stessa giornata fantacalcistica
    # resta agganciato alla fixture più vicina, non all'ultima incontrata.
    context_by_membership: dict[tuple[UUID, UUID], tuple[Fixture, str]] = {}
    for fixture in fixtures:
        context_by_membership.setdefault(
            (fixture.sport_season_id, fixture.home_club_id),
            (fixture, fixture.home_club.name),
        )
        context_by_membership.setdefault(
            (fixture.sport_season_id, fixture.away_club_id),
            (fixture, fixture.away_club.name),
        )

    snapshots: dict[UUID, RoundAthleteScore] = {}
    memberships = session.scalars(
        select(SquadMembership)
        .where(
            SquadMembership.is_active.is_(True),
            or_(
                *(
                    (SquadMembership.sport_season_id == season_id)
                    & (SquadMembership.club_id == club_id)
                    for season_id, club_id in context_by_membership
                )
            ),
        )
        .order_by(
            SquadMembership.athlete_id.asc(),
            SquadMembership.is_active.desc(),
            SquadMembership.created_at.desc(),
        )
    ).all()
    for membership in memberships:
        context = context_by_membership.get((membership.sport_season_id, membership.club_id))
        if context is None or membership.athlete_id in snapshots:
            continue
        fixture, team_name = context
        snapshots[membership.athlete_id] = RoundAthleteScore(
            real_team_name=team_name,
            fixture_status=fixture.status_short,
            fixture_status_label=_fixture_status_label(fixture.status_short),
            score_final=(fixture.status_short or "").upper() in FINISHED_FIXTURE_STATUSES,
            kickoff_at=fixture.kickoff_at,
            substituted_out_minute=substitution_out_by_athlete.get(membership.athlete_id),
            substituted_in_minute=substitution_in_by_athlete.get(membership.athlete_id),
        )

    stat_club_by_player = {
        (fixture_id, athlete_id): club_id
        for fixture_id, athlete_id, club_id in session.execute(
            select(
                PlayerMatchStat.fixture_id,
                PlayerMatchStat.athlete_id,
                PlayerMatchStat.club_id,
            ).where(
                PlayerMatchStat.fixture_id.in_(fixture_ids),
                PlayerMatchStat.athlete_id.is_not(None),
                PlayerMatchStat.club_id.is_not(None),
            )
        ).all()
        if athlete_id is not None and club_id is not None
    }

    rows = list(
        session.scalars(
            select(PlayerMatchRating).where(
                PlayerMatchRating.fixture_id.in_(fixture_ids),
                PlayerMatchRating.formula_version == version,
                PlayerMatchRating.athlete_id.is_not(None),
                PlayerMatchRating.league_id == league_id,
            )
        ).all()
    )
    if not rows:
        rows = list(
            session.scalars(
                select(PlayerMatchRating).where(
                    PlayerMatchRating.fixture_id.in_(fixture_ids),
                    PlayerMatchRating.formula_version == version,
                    PlayerMatchRating.athlete_id.is_not(None),
                    PlayerMatchRating.league_id.is_(None),
                )
            ).all()
        )

    for row in rows:
        if row.athlete_id is None:
            continue
        fixture = fixture_by_id.get(row.fixture_id)
        prior = snapshots.get(row.athlete_id, RoundAthleteScore())
        real_team_name = prior.real_team_name
        if fixture is not None and real_team_name is None:
            stat_club_id = stat_club_by_player.get((row.fixture_id, row.athlete_id))
            if stat_club_id == fixture.home_club_id:
                real_team_name = fixture.home_club.name
            elif stat_club_id == fixture.away_club_id:
                real_team_name = fixture.away_club.name
        positive = sum(
            float(item.get("contribution", 0))
            for item in row.bonus_malus_json
            if float(item.get("contribution", 0)) > 0
        )
        negative = sum(
            float(item.get("contribution", 0))
            for item in row.bonus_malus_json
            if float(item.get("contribution", 0)) < 0
        )
        snapshots[row.athlete_id] = RoundAthleteScore(
            fantasy_score=row.fantasy_score,
            base_score=row.display,
            bonus_total=positive,
            malus_total=negative,
            bonus_malus=tuple(dict(item) for item in row.bonus_malus_json),
            real_team_name=real_team_name,
            fixture_status=fixture.status_short if fixture is not None else prior.fixture_status,
            fixture_status_label=(
                _fixture_status_label(fixture.status_short)
                if fixture is not None
                else prior.fixture_status_label
            ),
            score_final=(
                (fixture.status_short or "").upper() in FINISHED_FIXTURE_STATUSES
                if fixture is not None
                else prior.score_final
            ),
            kickoff_at=fixture.kickoff_at if fixture is not None else prior.kickoff_at,
            substituted_out_minute=(
                substitution_out_by_athlete.get(row.athlete_id, prior.substituted_out_minute)
            ),
            substituted_in_minute=(
                substitution_in_by_athlete.get(row.athlete_id, prior.substituted_in_minute)
            ),
        )
    return snapshots
