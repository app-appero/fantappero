"""Osservatore: compare athletes and suggest free-agent targets (EP10-03).

Suggestions only — the user still submits a bid/waiver themselves through
the existing market flow (EP08). Free-agent candidates are filtered by
official role and, when the caller's own team is resolvable, by whether
their current credit balance can plausibly afford the cheapest slot (a
coarse eligibility signal, not a bid amount).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.audit_service import AiAuditService
from ai_assistant.feature_store import AthleteFeatures, build_athlete_features
from ai_assistant.generation import MODEL_VERSION, format_rating
from ai_assistant.team_resolution import resolve_my_team
from authorization.context import LeagueAccess
from database.enums import AiAssistantFeature, FantasyRole
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot
from sports_data.listone.models import RoleAssignment

PROMPT_KEY_COMPARE = "osservatore.confronto"
PROMPT_KEY_TARGETS = "osservatore.obiettivi_svincolati"
PROMPT_VERSION = 1
MAX_COMPARISON_ATHLETES = 6
DEFAULT_TARGET_LIMIT = 5
MAX_TARGET_LIMIT = 20


@dataclass(frozen=True)
class AthleteComparisonRow:
    athlete_id: UUID
    name: str
    role: str | None
    avg_rating: float | None
    recent_minutes_avg: float | None
    injured: bool | None
    is_free_agent_in_league: bool | None
    next_opponent_name: str | None


@dataclass(frozen=True)
class OsservatoreResult:
    rows: tuple[AthleteComparisonRow, ...]
    interaction_id: UUID


def _to_row(features: AthleteFeatures) -> AthleteComparisonRow:
    return AthleteComparisonRow(
        athlete_id=features.athlete_id,
        name=features.canonical_name,
        role=features.role.value if features.role else None,
        avg_rating=features.avg_rating,
        recent_minutes_avg=features.recent_minutes_avg,
        injured=features.injured,
        is_free_agent_in_league=features.is_free_agent_in_league,
        next_opponent_name=features.next_opponent_name,
    )


class OsservatoreService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compare(self, league_access: LeagueAccess, athlete_ids: list[UUID]) -> OsservatoreResult:
        as_of = datetime.now(UTC)
        rows: list[AthleteComparisonRow] = []
        for athlete_id in athlete_ids[:MAX_COMPARISON_ATHLETES]:
            features = build_athlete_features(
                self._session, athlete_id, as_of=as_of, league_id=league_access.league.id
            )
            if features is not None:
                rows.append(_to_row(features))

        output_text = (
            "; ".join(f"{row.name}: forma {format_rating(row.avg_rating)}" for row in rows)
            or "Nessun giocatore trovato."
        )
        interaction = AiAuditService(self._session).record(
            user_id=league_access.user.id,
            league_id=league_access.league.id,
            feature=AiAssistantFeature.OSSERVATORE,
            input_payload={"athleteIds": [str(a) for a in athlete_ids]},
            prompt_key=PROMPT_KEY_COMPARE,
            prompt_version=PROMPT_VERSION,
            model_version=MODEL_VERSION,
            output_text=output_text,
        )
        self._session.commit()
        return OsservatoreResult(tuple(rows), interaction.id)

    def suggest_free_agent_targets(
        self,
        league_access: LeagueAccess,
        *,
        role: FantasyRole,
        season_year: int,
        limit: int = DEFAULT_TARGET_LIMIT,
    ) -> OsservatoreResult:
        limit = max(1, min(limit, MAX_TARGET_LIMIT))
        occupied_ids = set(
            self._session.scalars(
                select(FantasyRosterSlot.athlete_id).where(
                    FantasyRosterSlot.league_id == league_access.league.id,
                    FantasyRosterSlot.athlete_id.is_not(None),
                )
            ).all()
        )
        candidate_ids = self._session.scalars(
            select(RoleAssignment.athlete_id).where(
                RoleAssignment.role == role,
                RoleAssignment.season_year == season_year,
            )
        ).all()

        team = resolve_my_team(self._session, league_access)
        balance = None
        if team is not None:
            account = find_account_for_team(self._session, team.id)
            balance = account.balance if account is not None else None

        as_of = datetime.now(UTC)
        rows: list[AthleteComparisonRow] = []
        for athlete_id in candidate_ids:
            if athlete_id in occupied_ids:
                continue
            if balance is not None and balance < 1:
                continue
            features = build_athlete_features(
                self._session, athlete_id, as_of=as_of, league_id=league_access.league.id
            )
            if features is not None:
                rows.append(_to_row(features))

        rows.sort(key=lambda row: row.avg_rating or 0.0, reverse=True)
        rows = rows[:limit]

        output_text = (
            "; ".join(f"{row.name}: forma {format_rating(row.avg_rating)}" for row in rows)
            or "Nessuno svincolato disponibile per questo ruolo."
        )
        interaction = AiAuditService(self._session).record(
            user_id=league_access.user.id,
            league_id=league_access.league.id,
            feature=AiAssistantFeature.OSSERVATORE,
            input_payload={"role": role.value, "seasonYear": season_year, "limit": limit},
            prompt_key=PROMPT_KEY_TARGETS,
            prompt_version=PROMPT_VERSION,
            model_version=MODEL_VERSION,
            output_text=output_text,
        )
        self._session.commit()
        return OsservatoreResult(tuple(rows), interaction.id)
