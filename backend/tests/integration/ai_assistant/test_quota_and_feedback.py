"""Integration tests for AI daily quota and feedback (EP10-05)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_assistant.exceptions import AiInteractionNotFoundError, AiQuotaExceededError
from ai_assistant.feedback_service import record_feedback
from ai_assistant.models import AiInteraction
from ai_assistant.quota_service import check_daily_quota
from database.enums import AiAssistantFeature, AiFeedbackRating
from mail.capture import get_captured_emails


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


def _seed_interaction(db_session: Session, user_id: UUID) -> AiInteraction:
    interaction = AiInteraction(
        user_id=user_id,
        league_id=None,
        feature=AiAssistantFeature.ANALISTA,
        input_json={"athleteId": str(uuid4())},
        prompt_key="analista.spiegazione_giocatore",
        prompt_version=1,
        model_version="deterministic-rules-v1",
        output_text="Testo di prova",
    )
    db_session.add(interaction)
    db_session.commit()
    return interaction


def test_quota_raises_once_daily_limit_is_reached(client: TestClient, db_session: Session) -> None:
    _, user_id = _register_and_login(client, "quota-basic@example.com")
    for _ in range(3):
        _seed_interaction(db_session, user_id)

    check_daily_quota(db_session, user_id, limit=5)
    with pytest.raises(AiQuotaExceededError):
        for _ in range(3):
            _seed_interaction(db_session, user_id)
        check_daily_quota(db_session, user_id, limit=5)


def test_feedback_recorded_and_ownership_enforced(client: TestClient, db_session: Session) -> None:
    _, owner_id = _register_and_login(client, "feedback-owner@example.com")
    _, intruder_id = _register_and_login(client, "feedback-intruder@example.com")
    interaction = _seed_interaction(db_session, owner_id)

    with pytest.raises(AiInteractionNotFoundError):
        record_feedback(
            db_session,
            user_id=intruder_id,
            interaction_id=interaction.id,
            rating=AiFeedbackRating.DOWN,
        )

    updated = record_feedback(
        db_session, user_id=owner_id, interaction_id=interaction.id, rating=AiFeedbackRating.UP
    )
    assert updated.feedback_rating == AiFeedbackRating.UP
    assert updated.feedback_at is not None
    assert updated.feedback_at <= datetime.now(UTC)
