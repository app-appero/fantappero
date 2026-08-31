"""Generazione della formazione automatica per fantallenatori IA (EP13-P05).

Implementa ADR-0005. Scrive **esclusivamente** su squadre la cui membership ha
``user_type == UserType.AI``: una formazione di un utente manuale non viene
mai toccata, nemmeno se vuota.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from database.enums import (
    FantasyModule,
    FantasyRole,
    FantasyTurnStatus,
    LeagueState,
    LineupSlotKind,
    UserType,
)
from fantasy_lineups.ai_selection import (
    AI_LINEUP_ALGORITHM_VERSION,
    EXCLUSION_LABELS,
    CandidateInput,
    LineupPlan,
    build_lineup_plan,
    official_starter_signal,
)
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.rules import (
    DEFAULT_LINEUP_LOCK_MARGIN_MINUTES,
    LineupPlayerRef,
    evaluate_lineup,
    is_athlete_kickoff_locked,
    module_counts,
)
from fantasy_ratings.config import DEFAULT_FORMULA_VERSION
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.fixtures.models import (
    Fixture,
    OfficialLineup,
    OfficialLineupEntry,
)
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

#: Modulo di default quando nessun altro è imposto dal regolamento.
DEFAULT_MODULE = FantasyModule.M433

#: Giornate concluse considerate per la forma recente (ADR-0005 §2).
RECENT_FORM_WINDOW = 5


@dataclass(frozen=True)
class AiLineupResult:
    fantasy_team_id: UUID
    round_id: UUID
    outcome: str  # created | updated | unchanged | skipped_not_ai | skipped_locked | incomplete
    fantasy_team_name: str = ""
    plan: LineupPlan | None = None
    message: str | None = None


def generate_ai_lineup(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    fantasy_team_id: UUID,
    module: FantasyModule = DEFAULT_MODULE,
    now: datetime | None = None,
    dry_run: bool = False,
) -> AiLineupResult:
    """Costruisce e persiste la formazione automatica di una squadra IA."""
    decided_at = now or datetime.now(UTC)

    league = session.get(League, league_id)
    if league is None:
        raise ValidationAuthError("Lega non trovata.", code="league_not_found")

    fantasy_round = session.execute(
        select(FantasyRound).where(
            FantasyRound.id == round_id,
            FantasyRound.league_id == league_id,
        )
    ).scalar_one_or_none()
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")

    team = session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == fantasy_team_id,
            FantasyTeam.league_id == league_id,
        )
    ).scalar_one_or_none()
    if team is None:
        raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")

    membership = session.execute(
        select(LeagueMembership)
        .where(LeagueMembership.id == team.membership_id)
        .options(selectinload(LeagueMembership.user))
    ).scalar_one_or_none()
    if membership is None or membership.user is None:
        raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")

    # Guard centrale: mai scrivere su una squadra umana (ADR-0005 §7).
    if membership.user.user_type != UserType.AI:
        return AiLineupResult(
            fantasy_team_id=fantasy_team_id,
            round_id=round_id,
            outcome="skipped_not_ai",
            fantasy_team_name=team.name,
            message="La formazione automatica è riservata ai fantallenatori IA.",
        )

    if fantasy_round.status == FantasyTurnStatus.SKIPPED:
        return AiLineupResult(
            fantasy_team_id=fantasy_team_id,
            round_id=round_id,
            outcome="skipped_locked",
            fantasy_team_name=team.name,
            message="Turno non disputato.",
        )

    existing = session.execute(
        select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == fantasy_team_id,
        )
    ).scalar_one_or_none()
    if existing is not None and not existing.system_generated_ai:
        return AiLineupResult(
            fantasy_team_id=fantasy_team_id,
            round_id=round_id,
            outcome="skipped_manual",
            fantasy_team_name=team.name,
            message="La formazione già salvata manualmente resta invariata.",
        )

    candidates = _collect_candidates(
        session,
        league_id=league_id,
        round_id=round_id,
        team_id=fantasy_team_id,
        season_year=league.season_year,
        decided_at=decided_at,
    )
    # Creazione retroattiva consentita (decisione prodotto EP13-P04-bis): una
    # formazione IA può essere generata la prima volta anche a turno iniziato
    # o concluso, usando i candidati disponibili senza filtro sul kickoff.

    # Lock progressivo (ADR-0005 §6): se esiste già una formazione automatica
    # e almeno un suo calciatore ha la partita iniziata, non si tocca più
    # nulla. Il piano escluderebbe i bloccati, quindi ricostruirlo qui
    # significherebbe cancellarli dalla formazione.
    if existing is not None and existing.system_generated_ai:
        locked_ids = {
            candidate.athlete_id for candidate in candidates if candidate.kickoff_locked
        }
        if any(player.athlete_id in locked_ids for player in existing.players):
            return AiLineupResult(
                fantasy_team_id=fantasy_team_id,
                round_id=round_id,
                outcome="skipped_locked",
                fantasy_team_name=team.name,
                message="Lock progressivo iniziato: la formazione resta invariata.",
            )

    counts = module_counts(module)
    role_targets = [
        (FantasyRole.P, counts.goalkeepers),
        (FantasyRole.D, counts.defenders),
        (FantasyRole.C, counts.midfielders),
        (FantasyRole.A, counts.forwards),
    ]
    plan = build_lineup_plan(candidates, role_targets, decided_at=decided_at)

    roles_by_id = {candidate.athlete_id: candidate.role for candidate in candidates}
    roster_ids = list(
        session.scalars(
            select(FantasyRosterSlot.athlete_id).where(
                FantasyRosterSlot.fantasy_team_id == fantasy_team_id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all()
    )
    validation = evaluate_lineup(
        module=module.value,
        starters=[
            LineupPlayerRef(athlete_id=athlete_id, role=roles_by_id.get(athlete_id))
            for athlete_id in plan.starters
        ],
        bench=[
            LineupPlayerRef(athlete_id=athlete_id, role=roles_by_id.get(athlete_id))
            for athlete_id in plan.bench
        ],
        roster_athlete_ids=roster_ids,
    )

    if not plan.is_complete or not validation.valid:
        # Rosa insufficiente: lo diciamo invece di persistere una formazione
        # illegale che il motore di validazione rifiuterebbe comunque.
        get_metrics().incr("ai_lineup_generated_total", labels={"result": "incomplete"})
        issue_message = " ".join(issue.message for issue in validation.issues[:2])
        return AiLineupResult(
            fantasy_team_id=fantasy_team_id,
            round_id=round_id,
            outcome="incomplete",
            fantasy_team_name=team.name,
            plan=plan,
            message=issue_message or "Rosa insufficiente per completare il modulo.",
        )

    if dry_run:
        return AiLineupResult(
            fantasy_team_id=fantasy_team_id,
            round_id=round_id,
            outcome="preview",
            fantasy_team_name=team.name,
            plan=plan,
        )

    outcome = _persist(
        session,
        league_id=league_id,
        fantasy_round=fantasy_round,
        team=team,
        actor_user_id=membership.user_id,
        module=module,
        plan=plan,
        candidates=candidates,
    )
    get_metrics().incr("ai_lineup_generated_total", labels={"result": outcome})
    logger.info(
        "ai_lineup_generated",
        extra={
            "result": outcome,
            "algorithm_version": plan.algorithm_version,
            "used_fallback": plan.used_fallback,
            "starters": len(plan.starters),
        },
    )
    return AiLineupResult(
        fantasy_team_id=fantasy_team_id,
        round_id=round_id,
        outcome=outcome,
        fantasy_team_name=team.name,
        plan=plan,
    )


def _collect_candidates(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
    season_year: int,
    decided_at: datetime,
) -> list[CandidateInput]:
    """Raccoglie i soli segnali ammessi da ADR-0005 per la rosa posseduta."""
    slots = list(
        session.scalars(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team_id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
            .options(selectinload(FantasyRosterSlot.athlete))
        ).all()
    )
    if not slots:
        return []

    athlete_ids = [slot.athlete_id for slot in slots if slot.athlete_id is not None]
    fixtures_by_club = _round_fixtures_by_club(session, round_id=round_id)
    starters = _official_starters(session, round_id=round_id)
    form = _recent_form(session, league_id=league_id, athlete_ids=athlete_ids)
    lock_margin = _lineup_lock_margin_for_league(session, league_id=league_id)
    # Stesso risolutore usato dal percorso umano: tiene conto degli override
    # di ruolo della lega e porta con sé il club di appartenenza.
    effective_roles = resolve_effective_athlete_roles(
        session,
        league_id=league_id,
        athlete_ids=athlete_ids,
        season_year=season_year,
    )

    candidates: list[CandidateInput] = []
    for slot in slots:
        athlete: Athlete | None = slot.athlete
        if athlete is None or slot.athlete_id is None:
            continue

        resolved = effective_roles.get(slot.athlete_id)
        if resolved is None:
            # Senza ruolo effettivo non sappiamo dove schierarlo.
            continue

        fixture = fixtures_by_club.get(resolved.club_id) if resolved.club_id is not None else None
        locked = (
            False
            if fixture is None
            else is_athlete_kickoff_locked(
                now=decided_at,
                kickoff_at=fixture.kickoff_at,
                status_short=fixture.status_short,
                margin_minutes=lock_margin,
            )
        )
        raw_starter, fetched_at = starters.get(slot.athlete_id, (None, None))
        average, appearances = form.get(slot.athlete_id, (None, 0))

        candidates.append(
            CandidateInput(
                athlete_id=slot.athlete_id,
                role=resolved.role,
                injured=bool(athlete.injured),
                official_starter=official_starter_signal(
                    is_starter=raw_starter,
                    fetched_at=fetched_at,
                    decided_at=decided_at,
                    athlete_kickoff_locked=locked,
                ),
                recent_form=average,
                recent_appearances=appearances,
                has_fixture=fixture is not None,
                kickoff_locked=locked,
            )
        )
    return candidates


def _lineup_lock_margin_for_league(session: Session, *, league_id: UUID) -> int:
    """Stesso margine per-lega usato dal percorso umano (fantasy_lineups/service.py)."""
    margin = session.execute(
        select(LeagueRules.lineup_lock_margin_minutes).where(LeagueRules.league_id == league_id)
    ).scalar_one_or_none()
    return margin if margin is not None else DEFAULT_LINEUP_LOCK_MARGIN_MINUTES


def _round_fixtures_by_club(session: Session, *, round_id: UUID) -> dict[UUID, Fixture]:
    fixtures = list(
        session.scalars(
            select(Fixture)
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
    )
    by_club: dict[UUID, Fixture] = {}
    for fixture in fixtures:
        by_club[fixture.home_club_id] = fixture
        by_club[fixture.away_club_id] = fixture
    return by_club


def _official_starters(
    session: Session,
    *,
    round_id: UUID,
) -> dict[UUID, tuple[bool | None, datetime | None]]:
    """Titolarità ufficiale con la sua provenienza, per atleta."""
    rows = session.execute(
        select(
            OfficialLineupEntry.athlete_id,
            OfficialLineupEntry.is_starter,
            OfficialLineup.fetched_at,
        )
        .join(OfficialLineup, OfficialLineup.id == OfficialLineupEntry.lineup_id)
        .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == OfficialLineup.fixture_id)
        .where(
            FantasyRoundFixture.round_id == round_id,
            FantasyRoundFixture.excluded_at.is_(None),
            OfficialLineupEntry.athlete_id.is_not(None),
        )
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


def _recent_form(
    session: Session,
    *,
    league_id: UUID,
    athlete_ids: list[UUID],
) -> dict[UUID, tuple[float | None, int]]:
    """Media fantavoto e presenze sulle ultime giornate **concluse**.

    Solo fixture terminate: una partita in corso non è un segnale disponibile
    al momento della decisione.
    """
    if not athlete_ids:
        return {}

    buckets: dict[UUID, list[float]] = {}

    def append_rows(*, scoped_league_id: UUID | None, selected_ids: list[UUID]) -> None:
        if not selected_ids:
            return
        scope_filter = (
            PlayerMatchRating.league_id == scoped_league_id
            if scoped_league_id is not None
            else PlayerMatchRating.league_id.is_(None)
        )
        rows = session.execute(
            select(PlayerMatchRating.athlete_id, PlayerMatchRating.fantasy_score)
            .join(Fixture, Fixture.id == PlayerMatchRating.fixture_id)
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .join(FantasyRound, FantasyRound.id == FantasyRoundFixture.round_id)
            .where(
                FantasyRound.league_id == league_id,
                PlayerMatchRating.athlete_id.in_(selected_ids),
                PlayerMatchRating.fantasy_score.is_not(None),
                PlayerMatchRating.formula_version == DEFAULT_FORMULA_VERSION,
                scope_filter,
                Fixture.status_short.in_(("FT", "AET", "PEN")),
            )
            .order_by(Fixture.kickoff_at.desc())
        ).all()
        for athlete_id, score in rows:
            bucket = buckets.setdefault(athlete_id, [])
            if len(bucket) < RECENT_FORM_WINDOW:
                bucket.append(float(score))

    # I voti dipendono dalla soglia-minuti della lega: usa sempre prima lo
    # snapshot isolato per lega. Il fallback globale mantiene leggibili i
    # dati storici creati prima dell'introduzione dello scope ``league_id``.
    append_rows(scoped_league_id=league_id, selected_ids=athlete_ids)
    legacy_ids = [athlete_id for athlete_id in athlete_ids if athlete_id not in buckets]
    append_rows(scoped_league_id=None, selected_ids=legacy_ids)

    return {
        athlete_id: (sum(scores) / len(scores), len(scores))
        for athlete_id, scores in buckets.items()
        if scores
    }


def _persist(
    session: Session,
    *,
    league_id: UUID,
    fantasy_round: FantasyRound,
    team: FantasyTeam,
    actor_user_id: UUID,
    module: FantasyModule,
    plan: LineupPlan,
    candidates: list[CandidateInput],
) -> str:
    roles_by_id = {candidate.athlete_id: candidate.role for candidate in candidates}
    decision_log = _decision_log(plan)

    submission = session.execute(
        select(LineupSubmission).where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == team.id,
        )
    ).scalar_one_or_none()

    if submission is None:
        submission = LineupSubmission(
            league_id=league_id,
            round_id=fantasy_round.id,
            fantasy_team_id=team.id,
            module=module,
            revision=1,
            submitted_at=plan.decided_at,
            submitted_by_user_id=actor_user_id,
            system_generated_ai=True,
            ai_algorithm_version=plan.algorithm_version,
            ai_decided_at=plan.decided_at,
            ai_decision_log=decision_log,
        )
        session.add(submission)
        session.flush()
        outcome = "created"
    else:
        if not submission.system_generated_ai:
            # Una formazione già schierata a mano non viene sovrascritta:
            # l'automazione supplisce a un'assenza, non corregge una scelta.
            return "skipped_manual"

        existing_starters = tuple(
            player.athlete_id
            for player in sorted(
                (
                    row
                    for row in submission.players
                    if row.slot_kind == LineupSlotKind.STARTER
                ),
                key=lambda row: row.sort_order,
            )
        )
        existing_bench = tuple(
            player.athlete_id
            for player in sorted(
                (row for row in submission.players if row.slot_kind == LineupSlotKind.BENCH),
                key=lambda row: row.sort_order,
            )
        )
        if (
            submission.module == module
            and existing_starters == plan.starters
            and existing_bench == plan.bench
        ):
            # True idempotence: an identical admin click does not bump the
            # revision or replace rows/timestamps merely because it ran again.
            return "unchanged"

        submission.module = module
        submission.revision += 1
        submission.submitted_at = plan.decided_at
        submission.ai_algorithm_version = plan.algorithm_version
        submission.ai_decided_at = plan.decided_at
        submission.ai_decision_log = decision_log
        session.execute(delete(LineupPlayer).where(LineupPlayer.submission_id == submission.id))
        session.flush()
        outcome = "updated"

    for order, athlete_id in enumerate(plan.starters):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athlete_id,
                slot_kind=LineupSlotKind.STARTER,
                role=roles_by_id[athlete_id],
                sort_order=order,
            )
        )
    for order, athlete_id in enumerate(plan.bench):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athlete_id,
                slot_kind=LineupSlotKind.BENCH,
                role=roles_by_id[athlete_id],
                sort_order=order,
            )
        )
    session.flush()
    return outcome


def _decision_log(plan: LineupPlan) -> dict[str, object]:
    """Log ispezionabile: score, segnali usati e motivi di esclusione."""
    return {
        "algorithmVersion": plan.algorithm_version,
        "decidedAt": plan.decided_at.isoformat(),
        "usedFallback": plan.used_fallback,
        "candidates": [
            {
                "athleteId": str(item.athlete_id),
                "role": item.role.value,
                "score": round(item.score, 4),
                "sources": [source.value for source in item.sources],
                "excludedReason": (
                    None if item.excluded_reason is None else item.excluded_reason.value
                ),
                "excludedLabel": (
                    None if item.excluded_reason is None else EXCLUSION_LABELS[item.excluded_reason]
                ),
            }
            for item in plan.candidates
        ],
    }


__all__ = [
    "AI_LINEUP_ALGORITHM_VERSION",
    "AiLineupResult",
    "generate_ai_lineup",
    "run_ai_lineups_for_round",
]


def run_ai_lineups_for_round(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[AiLineupResult]:
    """Genera (o simula) le formazioni di tutte le squadre IA di un turno.

    Idempotente: rieseguirla con gli stessi input produce lo stesso esito, e
    non tocca né le squadre umane né le formazioni già schierate a mano.
    """
    team_ids = list(
        session.scalars(
            select(FantasyTeam.id)
            .join(LeagueMembership, LeagueMembership.id == FantasyTeam.membership_id)
            .join(User, User.id == LeagueMembership.user_id)
            .where(
                FantasyTeam.league_id == league_id,
                User.user_type == UserType.AI,
            )
            .order_by(FantasyTeam.id.asc())
        ).all()
    )
    return [
        generate_ai_lineup(
            session,
            league_id=league_id,
            round_id=round_id,
            fantasy_team_id=team_id,
            now=now,
            dry_run=dry_run,
        )
        for team_id in team_ids
    ]


#: Stati turno per cui ha senso schierare: prima del lock definitivo.
_OPEN_TURN_STATUSES = (FantasyTurnStatus.SCHEDULED, FantasyTurnStatus.OPEN)


def generate_ai_lineups_for_active_leagues(session: Session) -> dict[str, int]:
    """Schiera le squadre IA dei turni aperti di tutte le leghe attive.

    Corpo puro, riusato sia dal task Celery periodico (`fantasy_lineups.
    generate_ai`) sia dal pulsante massivo dell'operatore in `/admin`: stessa
    logica, due modi di innescarla.
    """
    rounds_processed = 0
    teams_updated = 0
    teams_skipped = 0

    rows = session.execute(
        select(FantasyRound.id, FantasyRound.league_id)
        .join(League, League.id == FantasyRound.league_id)
        .where(
            League.state == LeagueState.ACTIVE,
            FantasyRound.status.in_(_OPEN_TURN_STATUSES),
        )
        .order_by(FantasyRound.league_id.asc(), FantasyRound.number.asc())
    ).all()

    for round_id, league_id in rows:
        results = run_ai_lineups_for_round(session, league_id=league_id, round_id=round_id)
        rounds_processed += 1
        for item in results:
            if item.outcome in {"created", "updated"}:
                teams_updated += 1
            else:
                teams_skipped += 1

    return {
        "rounds": rounds_processed,
        "teamsUpdated": teams_updated,
        "teamsSkipped": teams_skipped,
    }
