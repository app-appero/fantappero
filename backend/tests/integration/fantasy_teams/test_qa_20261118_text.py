"""QA 18/11: NUL e surrogati UTF-16 isolati nei campi di testo davano 500."""

from __future__ import annotations

import json
import re
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.session import create_session_factory
from leagues.models.competition import Competition
from mail.capture import get_captured_emails

LONE_SURROGATE = "\ud83d"


def _owner_with_league(client: TestClient, db_url: str) -> tuple[dict[str, str], str]:
    email = f"qa1811.text.{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": "Testo"},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    engine = create_engine_for_url(db_url)
    session: Session = create_session_factory(engine)()
    try:
        competition_ids = [
            str(row.id)
            for row in session.scalars(select(Competition).order_by(Competition.name)).all()[:3]
        ]
    finally:
        session.close()
        engine.dispose()
    league = client.post(
        "/leagues",
        headers=headers,
        json={"name": "Lega Testo", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert league.status_code == 201, league.text
    return headers, league.json()["id"]


def test_invalid_characters_in_text_fields_are_422_not_500(client: TestClient, db_url: str) -> None:
    headers, league_id = _owner_with_league(client, db_url)
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["id"]
    athlete_path = f"/leagues/{league_id}/amministrazione/listone/{uuid.uuid4()}/ruolo"

    cases = [
        ("PUT", athlete_path, {"role": "A", "reason": "motivo\x00nul"}),
        ("PUT", athlete_path, {"role": "A", "reason": f"motivo {LONE_SURROGATE}"}),
        (
            "POST",
            f"/leagues/{league_id}/amministrazione/import-csv/anteprima-testo",
            {"csvText": f"squadra,provider_id,nome,crediti\nX,,{LONE_SURROGATE},1\n"},
        ),
        (
            "PUT",
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
            {"athleteId": LONE_SURROGATE, "purchaseCredits": 1},
        ),
        (
            "POST",
            f"/leagues/{league_id}/amministrazione/crediti/movimenti",
            {
                "fantasyTeamId": team_id,
                "amount": 5,
                "transactionId": f"tx-{LONE_SURROGATE}",
                "note": "ok",
            },
        ),
        (
            "POST",
            f"/leagues/{league_id}/amministrazione/crediti/movimenti",
            {
                "fantasyTeamId": team_id,
                "amount": 5,
                "transactionId": "tx-ok",
                "note": f"nota {LONE_SURROGATE}",
            },
        ),
    ]
    for method, path, body in cases:
        # json.dumps (ensure_ascii) scrive "\ud83d" come fa un client reale; httpx
        # con `json=` proverebbe a codificarlo in UTF-8 e fallirebbe lato test.
        response = client.request(
            method,
            path,
            headers={**headers, "Content-Type": "application/json"},
            content=json.dumps(body).encode("ascii"),
        )
        assert response.status_code == 422, (path, body, response.status_code, response.text)
        assert response.json()["code"] == "validation_error"
