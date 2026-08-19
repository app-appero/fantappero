"""Viceallenatore: suggest a starter<->bench swap for injured starters (EP10-02).

Advisory only — never writes to the lineup. The caller must apply any swap
themselves through the existing lineup endpoints (EP06-03), which re-validate
everything (module, cutoff, ownership) independently of this suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.audit_service import AiAuditService
from ai_assistant.feature_store import build_athlete_features
from ai_assistant.generation import MODEL_VERSION, format_rating
from ai_assistant.team_resolution import resolve_my_team
from authorization.context import LeagueAccess
from database.enums import AiAssistantFeature, LineupSlotKind
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.rules import is_lineup_modification_allowed
from fantasy_turns.models import FantasyRound
from sports_data.roster.models import Athlete

PROMPT_KEY = "viceallenatore.suggerimento_formazione"
PROMPT_VERSION = 1


@dataclass(frozen=True)
class LineupSuggestion:
    starter_athlete_id: UUID
    starter_name: str
    bench_athlete_id: UUID
    bench_name: str
    reason: str


@dataclass(frozen=True)
class ViceallenatoreAdvice:
    suggestions: tuple[LineupSuggestion, ...]
    modification_allowed: bool
    message: str | None
    interaction_id: UUID | None = None


class ViceallenatoreService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def suggest(self, league_access: LeagueAccess, round_id: UUID) -> ViceallenatoreAdvice:
        team = resolve_my_team(self._session, league_access)
        fantasy_round = self._session.get(FantasyRound, round_id)
        if team is None or fantasy_round is None:
            return ViceallenatoreAdvice((), False, "Squadra o turno non trovati.")

        submission = self._session.scalar(
            select(LineupSubmission)
            .where(
                LineupSubmission.round_id == round_id,
                LineupSubmission.fantasy_team_id == team.id,
            )
            .order_by(LineupSubmission.revision.desc())
        )
        modification_allowed = is_lineup_modification_allowed(stored=fantasy_round.status)
        if submission is None:
            return ViceallenatoreAdvice(
                (), modification_allowed, "Nessuna formazione salvata per questo turno."
            )

        players = self._session.scalars(
            select(LineupPlayer).where(LineupPlayer.submission_id == submission.id)
        ).all()
        starters = [p for p in players if p.slot_kind == LineupSlotKind.STARTER]
        bench = [p for p in players if p.slot_kind == LineupSlotKind.BENCH]

        as_of = datetime.now(UTC)
        suggestions: list[LineupSuggestion] = []
        for starter in starters:
            starter_athlete = self._session.get(Athlete, starter.athlete_id)
            if starter_athlete is None or not starter_athlete.injured:
                continue
            starter_features = build_athlete_features(
                self._session, starter.athlete_id, as_of=as_of
            )
            best: tuple[float, Athlete] | None = None
            for bench_player in bench:
                bench_athlete = self._session.get(Athlete, bench_player.athlete_id)
                if bench_athlete is None:
                    continue
                bench_features = build_athlete_features(
                    self._session, bench_player.athlete_id, as_of=as_of
                )
                if bench_features is None:
                    continue
                if starter_features is not None and bench_features.role != starter_features.role:
                    continue
                score = bench_features.avg_rating or 0.0
                if best is None or score > best[0]:
                    best = (score, bench_athlete)
            if best is None:
                continue
            score, bench_athlete = best
            suggestions.append(
                LineupSuggestion(
                    starter_athlete_id=starter.athlete_id,
                    starter_name=starter_athlete.canonical_name,
                    bench_athlete_id=bench_athlete.id,
                    bench_name=bench_athlete.canonical_name,
                    reason=(
                        f"{starter_athlete.canonical_name} risulta infortunato: valuta "
                        f"{bench_athlete.canonical_name} (forma media {format_rating(score)})."
                    ),
                )
            )

        output_text = (
            "\n".join(s.reason for s in suggestions)
            if suggestions
            else "Nessun cambio consigliato: nessun titolare a rischio rilevato."
        )
        interaction = AiAuditService(self._session).record(
            user_id=league_access.user.id,
            league_id=league_access.league.id,
            feature=AiAssistantFeature.VICEALLENATORE,
            input_payload={"roundId": str(round_id), "teamId": str(team.id)},
            prompt_key=PROMPT_KEY,
            prompt_version=PROMPT_VERSION,
            model_version=MODEL_VERSION,
            output_text=output_text,
            output_payload={"suggestionsCount": len(suggestions)},
        )
        self._session.commit()

        return ViceallenatoreAdvice(
            tuple(suggestions),
            modification_allowed,
            None if suggestions else "Nessun cambio consigliato.",
            interaction.id,
        )
