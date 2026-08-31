"""Read-only H2H calendar + matchup detail for /turni (matchday:view).

Abbinamento giornata ↔ turno europeo in ``leagues.calendar_round_mapping``:
esplicito per finestra sui calendari ancorati (EP13-P03), per numero
progressivo su quelli generati prima (EP07-05).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from database.enums import (
    FantasyRoundHomologationStatus,
    LeagueCalendarStatus,
    LineupSlotKind,
)
from fantasy_lineups.models import EffectiveLineup, LineupPlayer, LineupSubmission
from fantasy_ratings.config import default_formula_config
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.readiness import FINISHED_FIXTURE_STATUSES, LIVE_FIXTURE_STATUSES
from fantasy_turns.rules import derive_effective_status
from fantasy_turns.service import FantasyTurnService
from leagues.calendar_round_mapping import round_for_h2h_number, rounds_by_h2h_number
from leagues.models.league import League
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.schemas import (
    H2HCalendarMatchupResponse,
    H2HCalendarResponse,
    H2HCalendarRoundResponse,
    H2HMatchupDetailResponse,
    H2HMatchupScoreResponse,
    H2HPlayerScoreResponse,
    H2HSideLineupResponse,
    LeagueCalendarSummaryResponse,
)
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.roster.models import Athlete, SquadMembership


@dataclass(frozen=True)
class _PlayerScoreSnapshot:
    fantasy_score: float | None = None
    base_score: float | None = None
    bonus_total: float = 0.0
    malus_total: float = 0.0
    bonus_malus: tuple[dict[str, object], ...] = ()
    real_team_name: str | None = None
    fixture_status: str | None = None
    fixture_status_label: str = "Partita non associata"
    score_final: bool = False


def get_h2h_calendar(session: Session, *, league_id: UUID) -> H2HCalendarResponse | None:
    calendar = _load_confirmed_calendar(session, league_id)
    if calendar is None:
        return None

    teams_by_membership = {
        team.membership_id: team
        for team in session.scalars(
            select(FantasyTeam).where(FantasyTeam.league_id == league_id)
        ).all()
    }
    rounds_by_number = rounds_by_h2h_number(session, league_id=league_id, calendar=calendar)

    rounds_map: dict[int, list[LeagueCalendarSlot]] = defaultdict(list)
    for slot in calendar.slots:
        rounds_map[slot.round_number].append(slot)

    rounds: list[H2HCalendarRoundResponse] = []
    any_live = False

    # Turni europei antecedenti alla creazione della lega (numerazione
    # condivisa): nessuno scontro fantasy possibile, mostrati come
    # segnaposto invece di essere assenti o rinumerati da 1. Un turno
    # semplicemente "Non disputato" per soglia non raggiunta (una pausa del
    # campionato successiva alla creazione) non è un segnaposto: non è mai
    # stato un turno H2H giocabile, quindi non compare affatto.
    if rounds_map:
        first_real_number = min(rounds_map)
        league = session.get(League, league_id)
        turn_service = FantasyTurnService(session)
        placeholder_numbers = (
            turn_service.turn_numbers_before_creation(
                league_id, before_number=first_real_number, created_at=league.created_at
            )
            if league is not None
            else []
        )
        for placeholder_number in placeholder_numbers:
            rounds.append(
                H2HCalendarRoundResponse(
                    roundNumber=placeholder_number,
                    fantasyRoundId=None,
                    homologationStatus=None,
                    europeanTurnStatus=None,
                    beforeLeagueCreation=True,
                    matchups=[],
                )
            )

    for round_number in sorted(rounds_map):
        fantasy_round = rounds_by_number.get(round_number)
        live_team_ids: set[UUID] = set()
        european_status = None
        homologation = None
        fantasy_round_id = None
        if fantasy_round is not None:
            fantasy_round_id = str(fantasy_round.id)
            european_status = _effective_turn_status(fantasy_round)
            homologation = fantasy_round.homologation_status.value
            live_team_ids = _live_team_ids_for_round(session, fantasy_round)

        matchups: list[H2HCalendarMatchupResponse] = []
        for slot in sorted(rounds_map[round_number], key=lambda row: row.slot_index):
            home = slot.home_membership
            away = slot.away_membership
            home_team = teams_by_membership.get(slot.home_membership_id)
            away_team = (
                teams_by_membership.get(slot.away_membership_id)
                if slot.away_membership_id is not None
                else None
            )
            matchup_live = (
                fantasy_round is not None
                and (
                    (home_team is not None and home_team.id in live_team_ids)
                    or (away_team is not None and away_team.id in live_team_ids)
                )
            )
            any_live = any_live or matchup_live
            matchups.append(
                H2HCalendarMatchupResponse(
                    slotId=str(slot.id),
                    slotIndex=slot.slot_index,
                    isBye=slot.is_bye,
                    homeUserId=str(home.user_id),
                    homeDisplayName=home.user.display_name,
                    homeTeamName=home_team.name if home_team is not None else None,
                    awayUserId=None if away is None else str(away.user_id),
                    awayDisplayName=None if away is None else away.user.display_name,
                    awayTeamName=away_team.name if away_team is not None else None,
                    live=matchup_live,
                    result=_score_payload(slot),
                )
            )
        rounds.append(
            H2HCalendarRoundResponse(
                roundNumber=round_number,
                fantasyRoundId=fantasy_round_id,
                homologationStatus=homologation,
                europeanTurnStatus=european_status,
                matchups=matchups,
            )
        )

    return H2HCalendarResponse(
        id=str(calendar.id),
        leagueId=str(calendar.league_id),
        status="confirmed",
        format=calendar.format.value,
        algorithmVersion=calendar.algorithm_version,
        participantCount=calendar.participant_count,
        roundCount=calendar.round_count,
        matchupCount=calendar.matchup_count,
        byeCount=calendar.bye_count,
        generatedAt=calendar.generated_at,
        confirmedAt=calendar.confirmed_at,
        live=any_live,
        rounds=rounds,
        summary=LeagueCalendarSummaryResponse(
            message="Calendario H2H confermato: scontri e risultati fantasy."
        ),
    )


def get_h2h_matchup_detail(
    session: Session,
    *,
    league_id: UUID,
    slot_id: UUID,
) -> H2HMatchupDetailResponse:
    slot = session.execute(
        select(LeagueCalendarSlot)
        .join(LeagueCalendar, LeagueCalendar.id == LeagueCalendarSlot.calendar_id)
        .where(
            LeagueCalendarSlot.id == slot_id,
            LeagueCalendar.league_id == league_id,
            LeagueCalendar.status == LeagueCalendarStatus.CONFIRMED,
        )
        .options(
            selectinload(LeagueCalendarSlot.home_membership).selectinload(LeagueMembership.user),
            selectinload(LeagueCalendarSlot.away_membership).selectinload(LeagueMembership.user),
        )
    ).scalar_one_or_none()
    if slot is None:
        raise ValidationAuthError("Scontro non trovato.", code="matchup_not_found")

    calendar = session.get(LeagueCalendar, slot.calendar_id)
    fantasy_round = (
        None
        if calendar is None
        else round_for_h2h_number(
            session,
            league_id=league_id,
            calendar=calendar,
            round_number=slot.round_number,
        )
    )

    european_status = None
    homologation = None
    fantasy_round_id = None
    live = False
    home_team = _team_for_membership(session, slot.home_membership_id)
    away_team = _team_for_membership(session, slot.away_membership_id)
    if fantasy_round is not None:
        fantasy_round_id = str(fantasy_round.id)
        european_status = _effective_turn_status(fantasy_round)
        homologation = fantasy_round.homologation_status.value
        relevant_team_ids = {
            team.id for team in (home_team, away_team) if team is not None
        }
        live = bool(_live_team_ids_for_round(session, fantasy_round) & relevant_team_ids)

    scores_by_athlete: dict[UUID, _PlayerScoreSnapshot] = {}
    if fantasy_round is not None:
        scores_by_athlete = _round_athlete_scores(
            session,
            fantasy_round.id,
            league_id=league_id,
        )

    home_side = _build_side(
        session,
        membership=slot.home_membership,
        team=home_team,
        fantasy_round=fantasy_round,
        scores_by_athlete=scores_by_athlete,
        persisted_total=slot.home_score,
        persisted_goals=slot.home_fantasy_goals,
    )
    away_side = None
    if not slot.is_bye and slot.away_membership is not None:
        away_side = _build_side(
            session,
            membership=slot.away_membership,
            team=away_team,
            fantasy_round=fantasy_round,
            scores_by_athlete=scores_by_athlete,
            persisted_total=slot.away_score,
            persisted_goals=slot.away_fantasy_goals,
        )

    return H2HMatchupDetailResponse(
        slotId=str(slot.id),
        leagueId=str(league_id),
        roundNumber=slot.round_number,
        fantasyRoundId=fantasy_round_id,
        homologationStatus=homologation,
        europeanTurnStatus=european_status,
        live=live,
        isBye=slot.is_bye,
        home=home_side,
        away=away_side,
        result=_score_payload(slot),
    )


def _load_confirmed_calendar(session: Session, league_id: UUID) -> LeagueCalendar | None:
    calendar = session.scalars(
        select(LeagueCalendar)
        .where(
            LeagueCalendar.league_id == league_id,
            LeagueCalendar.status == LeagueCalendarStatus.CONFIRMED,
        )
        .options(
            selectinload(LeagueCalendar.slots)
            .selectinload(LeagueCalendarSlot.home_membership)
            .selectinload(LeagueMembership.user)
            .selectinload(User.profile),
            selectinload(LeagueCalendar.slots)
            .selectinload(LeagueCalendarSlot.away_membership)
            .selectinload(LeagueMembership.user)
            .selectinload(User.profile),
            selectinload(LeagueCalendar.round_windows),
        )
    ).first()
    return calendar


def _score_payload(slot: LeagueCalendarSlot) -> H2HMatchupScoreResponse | None:
    if slot.is_bye or slot.result_computed_at is None:
        return None
    outcome = slot.outcome
    if outcome is not None and outcome not in {"home", "away", "draw"}:
        outcome = None
    return H2HMatchupScoreResponse(
        homeScore=slot.home_score,
        awayScore=slot.away_score,
        homeFantasyGoals=slot.home_fantasy_goals,
        awayFantasyGoals=slot.away_fantasy_goals,
        outcome=outcome,  # type: ignore[arg-type]
        resultFinal=slot.result_final,
        computedAt=slot.result_computed_at,
    )


def _effective_turn_status(fantasy_round: FantasyRound) -> str:
    return derive_effective_status(
        fantasy_round.status,
        now=datetime.now(UTC),
        cutoff_at=fantasy_round.cutoff_at,
    ).value


def _live_team_ids_for_round(session: Session, fantasy_round: FantasyRound) -> set[UUID]:
    """Squadre fantasy con un titolare coinvolto in una fixture LIVE.

    Il collegamento usa gli identificativi persistenti di atleta, stagione e
    club. Le statistiche normalizzate hanno precedenza; la membership copre
    i primi minuti in cui il provider non ha ancora pubblicato i giocatori.
    """
    if fantasy_round.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED:
        return set()

    fixture_rows = list(
        session.execute(
            select(
                Fixture.id,
                Fixture.sport_season_id,
                Fixture.home_club_id,
                Fixture.away_club_id,
            )
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .where(
                FantasyRoundFixture.round_id == fantasy_round.id,
                FantasyRoundFixture.excluded_at.is_(None),
                Fixture.status_short.in_(LIVE_FIXTURE_STATUSES),
            )
        ).all()
    )
    if not fixture_rows:
        return set()

    fixture_ids = [row.id for row in fixture_rows]
    live_athlete_ids = set(
        session.scalars(
            select(PlayerMatchStat.athlete_id).where(
                PlayerMatchStat.fixture_id.in_(fixture_ids),
                PlayerMatchStat.athlete_id.is_not(None),
            )
        ).all()
    )
    season_club_pairs = {
        (row.sport_season_id, row.home_club_id) for row in fixture_rows
    } | {(row.sport_season_id, row.away_club_id) for row in fixture_rows}
    live_athlete_ids.update(
        session.scalars(
            select(SquadMembership.athlete_id).where(
                or_(
                    *(
                        (SquadMembership.sport_season_id == season_id)
                        & (SquadMembership.club_id == club_id)
                        for season_id, club_id in season_club_pairs
                    )
                )
            )
        ).all()
    )
    if not live_athlete_ids:
        return set()

    return set(
        session.scalars(
            select(LineupSubmission.fantasy_team_id)
            .join(LineupPlayer, LineupPlayer.submission_id == LineupSubmission.id)
            .where(
                LineupSubmission.round_id == fantasy_round.id,
                LineupPlayer.slot_kind == LineupSlotKind.STARTER,
                LineupPlayer.athlete_id.in_(live_athlete_ids),
            )
            .distinct()
        ).all()
    )


def _team_for_membership(session: Session, membership_id: UUID | None) -> FantasyTeam | None:
    if membership_id is None:
        return None
    return session.execute(
        select(FantasyTeam).where(FantasyTeam.membership_id == membership_id)
    ).scalar_one_or_none()


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


def _round_athlete_scores(
    session: Session,
    round_id: UUID,
    *,
    league_id: UUID,
) -> dict[UUID, _PlayerScoreSnapshot]:
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
    context_by_membership: dict[tuple[UUID, UUID], tuple[Fixture, str]] = {}
    for fixture in fixtures:
        context_by_membership[(fixture.sport_season_id, fixture.home_club_id)] = (
            fixture,
            fixture.home_club.name,
        )
        context_by_membership[(fixture.sport_season_id, fixture.away_club_id)] = (
            fixture,
            fixture.away_club.name,
        )

    snapshots: dict[UUID, _PlayerScoreSnapshot] = {}
    memberships = session.scalars(
        select(SquadMembership)
        .where(
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
        context = context_by_membership.get(
            (membership.sport_season_id, membership.club_id)
        )
        if context is None or membership.athlete_id in snapshots:
            continue
        fixture, team_name = context
        snapshots[membership.athlete_id] = _PlayerScoreSnapshot(
            real_team_name=team_name,
            fixture_status=fixture.status_short,
            fixture_status_label=_fixture_status_label(fixture.status_short),
            score_final=(fixture.status_short or "").upper() in FINISHED_FIXTURE_STATUSES,
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

    rows = list(session.scalars(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id.in_(fixture_ids),
            PlayerMatchRating.formula_version == version,
            PlayerMatchRating.athlete_id.is_not(None),
            PlayerMatchRating.league_id == league_id,
        )
    ).all())
    if not rows:
        rows = list(session.scalars(
            select(PlayerMatchRating).where(
                PlayerMatchRating.fixture_id.in_(fixture_ids),
                PlayerMatchRating.formula_version == version,
                PlayerMatchRating.athlete_id.is_not(None),
                PlayerMatchRating.league_id.is_(None),
            )
        ).all())

    for row in rows:
        if row.athlete_id is None:
            continue
        fixture = fixture_by_id.get(row.fixture_id)
        prior = snapshots.get(row.athlete_id, _PlayerScoreSnapshot())
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
        snapshots[row.athlete_id] = _PlayerScoreSnapshot(
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
        )
    return snapshots


def _build_side(
    session: Session,
    *,
    membership: LeagueMembership,
    team: FantasyTeam | None,
    fantasy_round: FantasyRound | None,
    scores_by_athlete: dict[UUID, _PlayerScoreSnapshot],
    persisted_total: float | None,
    persisted_goals: int | None,
) -> H2HSideLineupResponse:
    display_name = membership.user.display_name
    if team is None or fantasy_round is None:
        return H2HSideLineupResponse(
            fantasyTeamId=str(team.id) if team is not None else None,
            teamName=team.name if team is not None else None,
            displayName=display_name,
            module=None,
            lineupSource="none",
            totalScore=persisted_total,
            fantasyGoals=persisted_goals,
            starters=[],
            bench=[],
        )

    effective = session.execute(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == fantasy_round.id,
            EffectiveLineup.fantasy_team_id == team.id,
        )
    ).scalar_one_or_none()
    submission = session.execute(
        select(LineupSubmission)
        .where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == team.id,
        )
        .options(selectinload(LineupSubmission.players).selectinload(LineupPlayer.athlete))
    ).scalar_one_or_none()

    if effective is not None and submission is not None:
        return _side_from_effective(
            effective=effective,
            submission=submission,
            team=team,
            display_name=display_name,
            scores_by_athlete=scores_by_athlete,
            persisted_total=persisted_total,
            persisted_goals=persisted_goals,
            session=session,
        )

    if submission is not None:
        return _side_from_submission(
            submission=submission,
            team=team,
            display_name=display_name,
            scores_by_athlete=scores_by_athlete,
            persisted_total=persisted_total,
            persisted_goals=persisted_goals,
        )

    return H2HSideLineupResponse(
        fantasyTeamId=str(team.id),
        teamName=team.name,
        displayName=display_name,
        module=None,
        lineupSource="none",
        totalScore=persisted_total,
        fantasyGoals=persisted_goals,
        starters=[],
        bench=[],
    )


def _side_from_effective(
    *,
    effective: EffectiveLineup,
    submission: LineupSubmission,
    team: FantasyTeam,
    display_name: str,
    scores_by_athlete: dict[UUID, _PlayerScoreSnapshot],
    persisted_total: float | None,
    persisted_goals: int | None,
    session: Session,
) -> H2HSideLineupResponse:
    players_by_id = {player.athlete_id: player for player in submission.players}
    starter_ids = [UUID(item) for item in effective.effective_starter_ids]
    missing_ids = [athlete_id for athlete_id in starter_ids if athlete_id not in players_by_id]
    athletes_by_id: dict[UUID, Athlete] = {}
    if missing_ids:
        athletes_by_id = {
            row.id: row
            for row in session.scalars(select(Athlete).where(Athlete.id.in_(missing_ids))).all()
        }
    starters: list[H2HPlayerScoreResponse] = []
    for athlete_id in starter_ids:
        player = players_by_id.get(athlete_id)
        athlete = player.athlete if player is not None else athletes_by_id.get(athlete_id)
        role = player.role.value if player is not None else "C"
        starters.append(
            _player_score_response(
                athlete_id=athlete_id,
                name=_athlete_name(athlete, athlete_id),
                photo_url=athlete.photo_url if athlete is not None else None,
                role=role,
                snapshot=scores_by_athlete.get(athlete_id),
                is_effective_starter=True,
                is_bench=False,
            )
        )
    bench: list[H2HPlayerScoreResponse] = []
    for player in sorted(
        (row for row in submission.players if row.slot_kind == LineupSlotKind.BENCH),
        key=lambda row: row.sort_order,
    ):
        if player.athlete_id in starter_ids:
            continue
        bench.append(
            _player_score_response(
                athlete_id=player.athlete_id,
                name=_athlete_name(player.athlete, player.athlete_id),
                photo_url=player.athlete.photo_url if player.athlete is not None else None,
                role=player.role.value,
                snapshot=scores_by_athlete.get(player.athlete_id),
                is_effective_starter=False,
                is_bench=True,
            )
        )
    total = persisted_total
    if total is None:
        total = sum(score or 0.0 for score in (row.fantasy_score for row in starters))
    return H2HSideLineupResponse(
        fantasyTeamId=str(team.id),
        teamName=team.name,
        displayName=display_name,
        module=effective.module.value,
        lineupSource="effective",
        totalScore=total,
        fantasyGoals=persisted_goals,
        starters=starters,
        bench=bench,
    )


def _side_from_submission(
    *,
    submission: LineupSubmission,
    team: FantasyTeam,
    display_name: str,
    scores_by_athlete: dict[UUID, _PlayerScoreSnapshot],
    persisted_total: float | None,
    persisted_goals: int | None,
) -> H2HSideLineupResponse:
    starters: list[H2HPlayerScoreResponse] = []
    bench: list[H2HPlayerScoreResponse] = []
    for player in sorted(
        submission.players,
        key=lambda row: (0 if row.slot_kind == LineupSlotKind.STARTER else 1, row.sort_order),
    ):
        is_starter = player.slot_kind == LineupSlotKind.STARTER
        payload = _player_score_response(
            athlete_id=player.athlete_id,
            name=_athlete_name(player.athlete, player.athlete_id),
            photo_url=player.athlete.photo_url if player.athlete is not None else None,
            role=player.role.value,
            snapshot=scores_by_athlete.get(player.athlete_id),
            is_effective_starter=is_starter,
            is_bench=not is_starter,
        )
        if is_starter:
            starters.append(payload)
        else:
            bench.append(payload)
    total = persisted_total
    if total is None:
        total = sum(score or 0.0 for score in (row.fantasy_score for row in starters))
    return H2HSideLineupResponse(
        fantasyTeamId=str(team.id),
        teamName=team.name,
        displayName=display_name,
        module=submission.module.value,
        lineupSource="submitted",
        totalScore=total,
        fantasyGoals=persisted_goals,
        starters=starters,
        bench=bench,
    )


def _athlete_name(athlete: Athlete | None, athlete_id: UUID) -> str:
    if athlete is not None and athlete.canonical_name:
        return athlete.canonical_name
    return f"Calciatore {str(athlete_id)[:8]}"


def _player_score_response(
    *,
    athlete_id: UUID,
    name: str,
    photo_url: str | None,
    role: str,
    snapshot: _PlayerScoreSnapshot | None,
    is_effective_starter: bool,
    is_bench: bool,
) -> H2HPlayerScoreResponse:
    score = snapshot or _PlayerScoreSnapshot()
    return H2HPlayerScoreResponse(
        athleteId=str(athlete_id),
        name=name,
        photoUrl=photo_url,
        role=role,  # type: ignore[arg-type]
        fantasyScore=score.fantasy_score,
        baseScore=score.base_score,
        bonusTotal=score.bonus_total,
        malusTotal=score.malus_total,
        bonusMalus=list(score.bonus_malus),
        realTeamName=score.real_team_name,
        fixtureStatus=score.fixture_status,
        fixtureStatusLabel=score.fixture_status_label,
        scoreFinal=score.score_final,
        isEffectiveStarter=is_effective_starter,
        isBench=is_bench,
    )
