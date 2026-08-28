"""Read-only H2H calendar + matchup detail for /turni (matchday:view).

Abbinamento giornata ↔ turno europeo in ``leagues.calendar_round_mapping``:
esplicito per finestra sui calendari ancorati (EP13-P03), per numero
progressivo su quelli generati prima (EP07-05).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from database.enums import (
    FantasyRoundHomologationStatus,
    FantasyTurnStatus,
    LeagueCalendarStatus,
    LineupSlotKind,
)
from fantasy_lineups.models import EffectiveLineup, LineupPlayer, LineupSubmission
from fantasy_ratings.config import default_formula_config
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import derive_effective_status
from leagues.calendar_round_mapping import round_for_h2h_number, rounds_by_h2h_number
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
from sports_data.roster.models import Athlete

LIVE_TURN_STATUSES = frozenset({FantasyTurnStatus.OPEN, FantasyTurnStatus.LOCKED})


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
    for round_number in sorted(rounds_map):
        fantasy_round = rounds_by_number.get(round_number)
        european_status = None
        homologation = None
        fantasy_round_id = None
        if fantasy_round is not None:
            fantasy_round_id = str(fantasy_round.id)
            european_status = _effective_turn_status(fantasy_round)
            homologation = fantasy_round.homologation_status.value
            if _is_round_live(fantasy_round, european_status):
                any_live = True

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
    if fantasy_round is not None:
        fantasy_round_id = str(fantasy_round.id)
        european_status = _effective_turn_status(fantasy_round)
        homologation = fantasy_round.homologation_status.value
        live = _is_round_live(fantasy_round, european_status)

    home_team = _team_for_membership(session, slot.home_membership_id)
    away_team = _team_for_membership(session, slot.away_membership_id)

    scores_by_athlete: dict[UUID, float | None] = {}
    if fantasy_round is not None:
        scores_by_athlete = _round_athlete_scores(session, fantasy_round.id)

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


def _is_round_live(fantasy_round: FantasyRound, european_status: str) -> bool:
    if fantasy_round.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED:
        return False
    return european_status in {status.value for status in LIVE_TURN_STATUSES}


def _team_for_membership(session: Session, membership_id: UUID | None) -> FantasyTeam | None:
    if membership_id is None:
        return None
    return session.execute(
        select(FantasyTeam).where(FantasyTeam.membership_id == membership_id)
    ).scalar_one_or_none()


def _round_athlete_scores(session: Session, round_id: UUID) -> dict[UUID, float | None]:
    version = default_formula_config().version
    fixture_ids = list(
        session.scalars(
            select(FantasyRoundFixture.fixture_id).where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
    )
    if not fixture_ids:
        return {}
    rows = session.scalars(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id.in_(fixture_ids),
            PlayerMatchRating.formula_version == version,
            PlayerMatchRating.athlete_id.is_not(None),
        )
    ).all()
    scores: dict[UUID, float | None] = {}
    for row in rows:
        if row.athlete_id is None:
            continue
        current = scores.get(row.athlete_id)
        if current is None and row.fantasy_score is not None:
            scores[row.athlete_id] = row.fantasy_score
        elif current is not None and row.fantasy_score is not None:
            scores[row.athlete_id] = current + row.fantasy_score
        elif row.athlete_id not in scores:
            scores[row.athlete_id] = row.fantasy_score
    return scores


def _build_side(
    session: Session,
    *,
    membership: LeagueMembership,
    team: FantasyTeam | None,
    fantasy_round: FantasyRound | None,
    scores_by_athlete: dict[UUID, float | None],
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
    scores_by_athlete: dict[UUID, float | None],
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
            H2HPlayerScoreResponse(
                athleteId=str(athlete_id),
                name=_athlete_name(athlete, athlete_id),
                role=role,  # type: ignore[arg-type]
                fantasyScore=scores_by_athlete.get(athlete_id),
                isEffectiveStarter=True,
                isBench=False,
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
            H2HPlayerScoreResponse(
                athleteId=str(player.athlete_id),
                name=_athlete_name(player.athlete, player.athlete_id),
                role=player.role.value,  # type: ignore[arg-type]
                fantasyScore=scores_by_athlete.get(player.athlete_id),
                isEffectiveStarter=False,
                isBench=True,
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
    scores_by_athlete: dict[UUID, float | None],
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
        payload = H2HPlayerScoreResponse(
            athleteId=str(player.athlete_id),
            name=_athlete_name(player.athlete, player.athlete_id),
            role=player.role.value,  # type: ignore[arg-type]
            fantasyScore=scores_by_athlete.get(player.athlete_id),
            isEffectiveStarter=is_starter,
            isBench=not is_starter,
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
