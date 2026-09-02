"""Analista: explain an athlete's form, risk and reliability (EP10-04).

Every answer carries the ``as_of`` timestamp it was computed against and an
explicit reliability caveat when the sample of recent matches is thin —
"Risposta mostra timestamp, motivazione e limiti" (EP10-04 acceptance).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from ai_assistant.audit_service import AiAuditService, find_cached_interaction
from ai_assistant.feature_store import build_athlete_features
from ai_assistant.generation import MODEL_VERSION, format_minutes, format_rating
from authorization.context import LeagueAccess
from database.enums import AiAssistantFeature

PROMPT_KEY = "analista.spiegazione_giocatore"
PROMPT_VERSION = 1
RELIABLE_SAMPLE_SIZE = 3


@dataclass(frozen=True)
class AnalystExplanation:
    athlete_id: UUID
    athlete_name: str
    as_of: datetime
    explanation: str
    limits: str
    sample_size: int
    interaction_id: UUID
    cached: bool


class AnalistaService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def explain(self, league_access: LeagueAccess, athlete_id: UUID) -> AnalystExplanation | None:
        input_payload = {"athleteId": str(athlete_id)}
        cached = find_cached_interaction(
            self._session,
            user_id=league_access.user.id,
            feature=AiAssistantFeature.ANALISTA,
            prompt_key=PROMPT_KEY,
            input_payload=input_payload,
        )
        if cached is not None and cached.output_json is not None:
            return AnalystExplanation(
                athlete_id=athlete_id,
                athlete_name=str(cached.output_json.get("athleteName", "")),
                as_of=cached.created_at,
                explanation=cached.output_text,
                limits=str(cached.output_json.get("limits", "")),
                sample_size=int(cached.output_json.get("sampleSize", 0)),
                interaction_id=cached.id,
                cached=True,
            )

        as_of = datetime.now(UTC)
        features = build_athlete_features(
            self._session, athlete_id, as_of=as_of, league_id=league_access.league.id
        )
        if features is None:
            return None

        sample_size = len(features.recent_ratings)
        risk_bits = []
        if features.injured:
            risk_bits.append("segnalato infortunato")
        if features.recent_minutes_avg is not None and features.recent_minutes_avg < 45:
            risk_bits.append("minutaggio recente basso")
        risk_text = ", ".join(risk_bits) if risk_bits else "nessun segnale di rischio rilevato"

        opponent_text = (
            f"Prossimo avversario: {features.next_opponent_name}."
            if features.next_opponent_name
            else "Nessuna partita futura programmata trovata."
        )
        minutes_text = format_minutes(features.recent_minutes_avg)
        explanation = (
            f"{features.canonical_name}: forma media {format_rating(features.avg_rating)} "
            f"su {sample_size} partite considerate, minuti medi {minutes_text}. "
            f"Rischio: {risk_text}. {opponent_text}"
        )
        limits = (
            f"Dati calcolati al {as_of.isoformat()}."
            if sample_size >= RELIABLE_SAMPLE_SIZE
            else (
                f"Dati calcolati al {as_of.isoformat()}. Campione ridotto "
                f"({sample_size} partite): affidabilità limitata."
            )
        )

        interaction = AiAuditService(self._session).record(
            user_id=league_access.user.id,
            league_id=league_access.league.id,
            feature=AiAssistantFeature.ANALISTA,
            input_payload=input_payload,
            prompt_key=PROMPT_KEY,
            prompt_version=PROMPT_VERSION,
            model_version=MODEL_VERSION,
            output_text=explanation,
            output_payload={
                "sampleSize": sample_size,
                "limits": limits,
                "athleteName": features.canonical_name,
            },
        )
        self._session.commit()

        return AnalystExplanation(
            athlete_id=athlete_id,
            athlete_name=features.canonical_name,
            as_of=as_of,
            explanation=explanation,
            limits=limits,
            sample_size=sample_size,
            interaction_id=interaction.id,
            cached=False,
        )
