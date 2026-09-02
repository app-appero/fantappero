"""Formazione mancante alla chiusura del turno (EP-turni-calcolo).

Priorità, per ogni squadra della lega priva di una `LineupSubmission` per il
turno che si sta chiudendo: (b) bozza salvata, rivalidata contro la rosa
attuale; (c) l'ultima formazione valida schierata in un turno precedente,
rivalidata; (d) nessuna delle due — formazione vuota, 0 punti fantasy.

Va chiamato da `round_calculation_service.calculate_league_round` **solo**
quando il turno è concluso (`evaluate_round_readiness(...).all_fixtures_finished`),
mai a metà turno: prima di quel momento un fantallenatore ha ancora tempo per
schierare da sé, e materializzare una copia anticipata gli toglierebbe quel
tempo. Una volta creata una LineupSubmission (anche vuota),
`compute_round_effective_lineups`/`compute_round_results` non hanno bisogno
di alcuna modifica: una formazione vuota produce già 0 punti e un risultato
H2H reale (non uno "skip") per pura composizione del codice esistente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.enums import (
    FantasyModule,
    FantasyRole,
    LeagueAuditAction,
    LineupAutoResolutionSource,
    LineupSlotKind,
)
from fantasy_lineups.models import LineupDraft, LineupPlayer, LineupSubmission
from fantasy_lineups.rules import LineupPlayerRef, copy_previous_lineup, evaluate_lineup, parse_module
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from observability.context import get_correlation_id
from observability.logging import get_logger

logger = get_logger(__name__)

#: Nessun impatto sul punteggio quando la formazione non ha titolari: serve
#: solo a soddisfare la colonna NOT NULL di LineupSubmission.module.
DEFAULT_FALLBACK_MODULE = FantasyModule.M433


@dataclass(frozen=True)
class LineupFallbackResult:
    round_id: UUID
    league_id: UUID
    resolved_from_draft: int = 0
    resolved_from_previous_round: int = 0
    resolved_as_zero: int = 0

    @property
    def total_resolved(self) -> int:
        return (
            self.resolved_from_draft + self.resolved_from_previous_round + self.resolved_as_zero
        )


def ensure_lineup_submissions_for_round(
    session: Session,
    *,
    round_id: UUID,
    league_id: UUID,
    actor_id: UUID | None,
) -> LineupFallbackResult:
    """Garantisce una LineupSubmission per ogni squadra della lega in questo turno."""
    fantasy_round = session.get(FantasyRound, round_id)
    league = session.get(League, league_id)
    if fantasy_round is None or league is None:
        return LineupFallbackResult(round_id=round_id, league_id=league_id)

    teams = list(
        session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.league_id == league_id)
            .options(selectinload(FantasyTeam.slots))
        ).all()
    )
    if not teams:
        return LineupFallbackResult(round_id=round_id, league_id=league_id)

    existing_team_ids = set(
        session.scalars(
            select(LineupSubmission.fantasy_team_id).where(
                LineupSubmission.round_id == round_id,
                LineupSubmission.fantasy_team_id.in_([team.id for team in teams]),
            )
        ).all()
    )
    missing_teams = [team for team in teams if team.id not in existing_team_ids]
    if not missing_teams:
        return LineupFallbackResult(round_id=round_id, league_id=league_id)

    now = datetime.now(UTC)
    resolved_from_draft = 0
    resolved_from_previous_round = 0
    resolved_as_zero = 0

    for team in missing_teams:
        membership = session.execute(
            select(LeagueMembership).where(LeagueMembership.id == team.membership_id)
        ).scalar_one_or_none()
        if membership is None:
            # Nessun proprietario risolvibile: submitted_by_user_id è
            # obbligatorio, non c'è a chi attribuire la submission sintetizzata.
            logger.warning(
                "fallback_lineup_no_membership",
                extra={"fantasy_team_id": str(team.id), "round_id": str(round_id)},
            )
            continue

        roster_athlete_ids = [slot.athlete_id for slot in team.slots if slot.athlete_id is not None]
        effective_roles = resolve_effective_athlete_roles(
            session,
            league_id=league_id,
            athlete_ids=roster_athlete_ids,
            season_year=league.season_year,
        )
        roles_by_id: dict[str, FantasyRole | None] = {
            str(athlete_id): (
                effective_roles[athlete_id].role if athlete_id in effective_roles else None
            )
            for athlete_id in roster_athlete_ids
        }
        roster_str_ids = [str(athlete_id) for athlete_id in roster_athlete_ids]

        resolution = _resolve_team_lineup(
            session,
            team=team,
            fantasy_round=fantasy_round,
            roster_str_ids=roster_str_ids,
            roles_by_id=roles_by_id,
        )

        if resolution is None:
            source = LineupAutoResolutionSource.ZERO_FALLBACK
            _create_submission(
                session,
                league_id=league_id,
                round_id=round_id,
                team_id=team.id,
                submitted_by_user_id=membership.user_id,
                module=DEFAULT_FALLBACK_MODULE,
                starter_ids=[],
                bench_ids=[],
                roles_by_id={},
                now=now,
                source=source,
            )
            resolved_as_zero += 1
        else:
            module, starter_ids, bench_ids, source = resolution
            _create_submission(
                session,
                league_id=league_id,
                round_id=round_id,
                team_id=team.id,
                submitted_by_user_id=membership.user_id,
                module=module,
                starter_ids=starter_ids,
                bench_ids=bench_ids,
                roles_by_id=roles_by_id,
                now=now,
                source=source,
            )
            if source == LineupAutoResolutionSource.DRAFT:
                resolved_from_draft += 1
            else:
                resolved_from_previous_round += 1

        session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_LINEUP_AUTO_RESOLVED,
                correlation_id=get_correlation_id(),
                details={
                    "roundId": str(round_id),
                    "fantasyTeamId": str(team.id),
                    "source": source.value,
                },
            )
        )

    session.flush()
    return LineupFallbackResult(
        round_id=round_id,
        league_id=league_id,
        resolved_from_draft=resolved_from_draft,
        resolved_from_previous_round=resolved_from_previous_round,
        resolved_as_zero=resolved_as_zero,
    )


def _resolve_team_lineup(
    session: Session,
    *,
    team: FantasyTeam,
    fantasy_round: FantasyRound,
    roster_str_ids: list[str],
    roles_by_id: dict[str, FantasyRole | None],
) -> tuple[FantasyModule, list[str], list[str], LineupAutoResolutionSource] | None:
    draft = session.execute(
        select(LineupDraft).where(
            LineupDraft.round_id == fantasy_round.id,
            LineupDraft.fantasy_team_id == team.id,
        )
    ).scalar_one_or_none()
    if draft is not None:
        starter_ids = [str(item) for item in draft.starter_athlete_ids if item not in {None, ""}]
        bench_ids = [str(item) for item in draft.bench_athlete_ids if item not in {None, ""}]
        evaluation = evaluate_lineup(
            module=draft.module.value,
            starters=[
                LineupPlayerRef(athlete_id=athlete_id, role=roles_by_id.get(athlete_id))
                for athlete_id in starter_ids
            ],
            bench=[
                LineupPlayerRef(athlete_id=athlete_id, role=roles_by_id.get(athlete_id))
                for athlete_id in bench_ids
            ],
            roster_athlete_ids=roster_str_ids,
        )
        if evaluation.valid:
            return draft.module, starter_ids, bench_ids, LineupAutoResolutionSource.DRAFT

    previous = _load_previous_submission(session, team_id=team.id, current_round=fantasy_round)
    if previous is not None:
        # Nessun lock passato deliberatamente: "locked" ha senso solo per un
        # editing umano in corso, non per un ripristino di sistema a turno
        # già chiuso — passarli marcherebbe ogni titolare come indisponibile,
        # dato che a turno concluso ogni kickoff reale è già trascorso.
        copied = copy_previous_lineup(
            previous_module=previous.module.value,
            previous_starter_ids=_starter_order(previous),
            previous_bench_ids=_bench_order(previous),
            roster_athlete_ids=roster_str_ids,
            role_by_athlete_id=roles_by_id,
        )
        if copied.can_confirm:
            module = parse_module(copied.module)
            assert module is not None
            starter_ids = [str(item) for item in copied.starter_ids if item not in {None, ""}]
            bench_ids = [str(item) for item in copied.bench_ids if item not in {None, ""}]
            return module, starter_ids, bench_ids, LineupAutoResolutionSource.PREVIOUS_ROUND

    return None


def _load_previous_submission(
    session: Session,
    *,
    team_id: UUID,
    current_round: FantasyRound,
) -> LineupSubmission | None:
    """Stessa query di `FantasyLineupService._load_previous_submission`.

    Duplicata deliberatamente invece di riusare il metodo privato del
    servizio dell'utente finale: questo modulo non ha (né deve avere) un
    `LeagueAccess`, stesso approccio già seguito da `ai_service.py`.
    """
    stmt = (
        select(LineupSubmission)
        .join(FantasyRound, LineupSubmission.round_id == FantasyRound.id)
        .where(
            LineupSubmission.fantasy_team_id == team_id,
            FantasyRound.league_id == current_round.league_id,
            FantasyRound.number < current_round.number,
        )
        .options(selectinload(LineupSubmission.players))
        .order_by(FantasyRound.number.desc())
    )
    return session.scalars(stmt).first()


def _starter_order(submission: LineupSubmission) -> list[str]:
    starters = [
        player for player in submission.players if player.slot_kind == LineupSlotKind.STARTER
    ]
    starters.sort(key=lambda row: row.sort_order)
    return [str(player.athlete_id) for player in starters]


def _bench_order(submission: LineupSubmission) -> list[str]:
    bench = [player for player in submission.players if player.slot_kind == LineupSlotKind.BENCH]
    bench.sort(key=lambda row: row.sort_order)
    return [str(player.athlete_id) for player in bench]


def _create_submission(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
    submitted_by_user_id: UUID,
    module: FantasyModule,
    starter_ids: list[str],
    bench_ids: list[str],
    roles_by_id: dict[str, FantasyRole | None],
    now: datetime,
    source: LineupAutoResolutionSource,
) -> LineupSubmission:
    submission = LineupSubmission(
        league_id=league_id,
        round_id=round_id,
        fantasy_team_id=team_id,
        module=module,
        revision=1,
        submitted_at=now,
        submitted_by_user_id=submitted_by_user_id,
        auto_resolution_source=source,
    )
    session.add(submission)
    session.flush()

    rows: list[LineupPlayer] = []
    for index, athlete_id in enumerate(starter_ids):
        role = roles_by_id.get(athlete_id)
        if role is None:
            continue
        rows.append(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=UUID(athlete_id),
                slot_kind=LineupSlotKind.STARTER,
                role=role,
                sort_order=index,
            )
        )
    for index, athlete_id in enumerate(bench_ids):
        role = roles_by_id.get(athlete_id)
        if role is None:
            continue
        rows.append(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=UUID(athlete_id),
                slot_kind=LineupSlotKind.BENCH,
                role=role,
                sort_order=index,
            )
        )
    if rows:
        session.add_all(rows)
        session.flush()
    return submission


__all__ = ["LineupFallbackResult", "ensure_lineup_submissions_for_round"]
