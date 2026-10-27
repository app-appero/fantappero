"""League creation integration tests (EP03-01)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueMemberRole, LeagueState
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture


def _extract_token_from_email_body(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else None


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    token = _extract_token_from_email_body(get_captured_emails()[-1].message.text_body)
    assert token
    client.post("/auth/verify-email", json={"token": token})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    user_id = UUID(login.json()["user"]["id"])
    return login.json()["accessToken"], user_id


def _standard_rules_payload(
    *,
    participant_count: int = 8,
    total_credits: int = 1000,
) -> dict[str, object]:
    return {
        "presetName": "standard",
        "participantCount": participant_count,
        "roster": {
            "rosterSize": 35,
            "goalkeepers": 3,
            "defenders": 11,
            "midfielders": 11,
            "forwards": 10,
        },
        "totalCredits": total_credits,
        "options": {
            "allowTrades": True,
            "allowManualInvites": True,
        },
    }


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _seed_competition_rounds(
    db_session: Session,
    *,
    competition_id: UUID,
    season_year: int,
    total_rounds: int,
    finished_rounds: int,
) -> None:
    """Semina una SportSeason con ``total_rounds`` giornate (TASK 9).

    Le prime ``finished_rounds`` giornate sono ``FT`` con kickoff nel
    passato; le restanti sono ``NS`` con kickoff nel futuro. Riusa le stesse
    due squadre per ogni giornata: qui interessano solo round_label/status/
    kickoff, non un calendario round-robin plausibile.
    """
    season = SportSeason(competition_id=competition_id, year=season_year, is_current=True)
    db_session.add(season)
    db_session.flush()

    seed = f"{competition_id}-{season_year}"
    home = Club(provider_id=abs(hash(f"{seed}-home")) % 1_000_000 + 1, name=f"Home {seed}")
    away = Club(provider_id=abs(hash(f"{seed}-away")) % 1_000_000 + 1, name=f"Away {seed}")
    db_session.add_all([home, away])
    db_session.flush()

    now = datetime.now(UTC)
    provider_base = (abs(hash(seed)) % 1_000_000) * 1_000
    for round_number in range(1, total_rounds + 1):
        finished = round_number <= finished_rounds
        kickoff = (
            now - timedelta(days=(finished_rounds - round_number + 1))
            if finished
            else now + timedelta(days=(round_number - finished_rounds))
        )
        db_session.add(
            Fixture(
                provider_id=provider_base + round_number,
                sport_season_id=season.id,
                home_club_id=home.id,
                away_club_id=away.id,
                kickoff_at=kickoff,
                status_short="FT" if finished else "NS",
                round_label=f"Regular Season - {round_number}",
            )
        )
    db_session.commit()


def test_list_competitions_returns_mvp_catalog(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "catalog.user@example.com")
    response = client.get(
        "/leagues/competitions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 5
    assert all("providerId" in row and "name" in row for row in payload)
    returned_ids = {row["id"] for row in payload}
    assert set(competition_ids).issubset(returned_ids)


def test_create_league_persists_draft_with_admin_and_audit(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, user_id = _register_and_login(client, "creator@example.com")
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Privata",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Lega Privata"
    assert body["seasonYear"] == 2026
    assert body["state"] == "configuring"
    assert body["viewerRole"] == "league_admin"
    assert len(body["competitions"]) == 3

    league_id = UUID(body["id"])
    league = db_session.get(League, league_id)
    assert league is not None
    assert league.state == LeagueState.CONFIGURING

    membership = db_session.scalars(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league_id,
            LeagueMembership.user_id == user_id,
        ),
    ).first()
    assert membership is not None
    assert membership.role == LeagueMemberRole.OWNER

    # La creazione lega provisiona anche squadra fantasy e conto crediti per
    # l'owner (M3-1): filtra sull'azione di interesse invece di contare tutte
    # le righe di audit della lega.
    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == league_id,
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_CREATED,
        ),
    ).all()
    assert len(audit) == 1
    assert audit[0].actor_id == user_id

    rules = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == league_id),
    ).first()
    assert rules is not None
    assert rules.preset_name == "standard"
    assert rules.participant_count == 8
    assert rules.roster_size == 35
    assert rules.goalkeepers == 3
    assert rules.defenders == 11
    assert rules.midfielders == 11
    assert rules.forwards == 10
    assert rules.total_credits == 1000


def test_create_league_rejects_insufficient_competitions(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "too.few@example.com")
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Incompleta",
            "seasonYear": 2026,
            "competitionIds": competition_ids[:2],
        },
    )
    assert response.status_code == 422


def test_create_league_allowed_when_second_leg_not_started(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """TASK 9: girone di ritorno non iniziato → creazione permessa.

    ``season_year`` è dedicato a questo test (non 2026, usato da quasi tutti
    gli altri test del file): la SportSeason seminata qui è per
    ``competition_ids[0]``, condiviso con gli altri test TASK9 — un
    ``season_year`` comune farebbe collidere l'unique constraint
    ``(competition_id, year)`` fra test diversi dello stesso modulo (la DB
    non viene ripulita fra una funzione di test e l'altra, solo fra moduli).
    """
    competition_id = UUID(competition_ids[0])
    _seed_competition_rounds(
        db_session,
        competition_id=competition_id,
        season_year=2021,
        total_rounds=38,
        finished_rounds=10,  # ben prima della giornata 20 (inizio ritorno).
    )

    token, _ = _register_and_login(client, "second.leg.allowed@example.com")
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Ritorno Non Iniziato",
            "seasonYear": 2021,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 201


def test_create_league_blocked_when_second_leg_started(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """TASK 9: girone di ritorno già iniziato → creazione bloccata con errore italiano.

    ``season_year`` dedicato (v. nota in ``test_create_league_allowed_when_second_leg_not_started``).
    """
    competition_id = UUID(competition_ids[0])
    _seed_competition_rounds(
        db_session,
        competition_id=competition_id,
        season_year=2022,
        total_rounds=38,
        finished_rounds=25,  # oltre la giornata 20 (inizio ritorno).
    )
    competition_name = db_session.get(Competition, competition_id).name

    token, _ = _register_and_login(client, "second.leg.blocked@example.com")
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Ritorno Iniziato",
            "seasonYear": 2022,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "competition_second_leg_started"
    assert competition_name in body["message"]
    assert "girone di ritorno" in body["message"]


def test_create_league_blocked_when_one_of_several_competitions_started_second_leg(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """TASK 9: selezione mista (una bloccante, le altre senza dati) → bloccata interamente.

    ``season_year`` dedicato (v. nota in ``test_create_league_allowed_when_second_leg_not_started``).
    """
    blocked_competition_id = UUID(competition_ids[0])
    _seed_competition_rounds(
        db_session,
        competition_id=blocked_competition_id,
        season_year=2023,
        total_rounds=38,
        finished_rounds=30,
    )
    # Le altre due competizioni non hanno dati di calendario per la stagione:
    # da sole sarebbero selezionabili (nessun segnale di ritorno iniziato).

    token, _ = _register_and_login(client, "second.leg.mixed@example.com")
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Selezione Mista",
            "seasonYear": 2023,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "competition_second_leg_started"


def test_available_competitions_marks_second_leg_started_as_not_selectable(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """TASK 9: l'elenco espone selectable/secondLegStarted per disabilitare in anticipo.

    ``season_year`` dedicato (v. nota in ``test_create_league_allowed_when_second_leg_not_started``).
    """
    blocked_id = UUID(competition_ids[0])
    allowed_id = competition_ids[1]
    _seed_competition_rounds(
        db_session,
        competition_id=blocked_id,
        season_year=2024,
        total_rounds=38,
        finished_rounds=30,
    )

    token, _ = _register_and_login(client, "available.competitions@example.com")
    response = client.get(
        "/leagues/available-competitions",
        params={"seasonYear": 2024},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    rows_by_id = {row["id"]: row for row in response.json()}

    blocked_row = rows_by_id[str(blocked_id)]
    assert blocked_row["selectable"] is False
    assert blocked_row["secondLegStarted"] is True
    assert blocked_row["currentRound"] == 30
    assert blocked_row["totalRounds"] == 38

    allowed_row = rows_by_id[allowed_id]
    assert allowed_row["selectable"] is True
    assert allowed_row["secondLegStarted"] is False


def test_create_league_rejects_invalid_name(client: TestClient, competition_ids: list[str]) -> None:
    token, _ = _register_and_login(client, "empty.name@example.com")
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "   ",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_league_name"


def test_create_league_requires_authentication(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    response = client.post(
        "/leagues",
        json={
            "name": "Senza Auth",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 401


def test_create_league_appears_in_mine_listing(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "mine.list@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Elenco",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201

    listing = client.get("/leagues/mine", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200
    names = {row["name"] for row in listing.json()}
    assert "Lega Elenco" in names


def test_update_league_rules_persists_and_audits(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, user_id = _register_and_login(client, "rules.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Regole",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = created.json()["id"]

    updated = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=_standard_rules_payload(participant_count=10, total_credits=1200),
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["presetName"] == "standard"
    assert body["participantCount"] == 10
    assert body["totalCredits"] == 1200

    persisted = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)),
    ).first()
    assert persisted is not None
    assert persisted.participant_count == 10
    assert persisted.total_credits == 1200

    # La creazione lega provisiona anche squadra fantasy e conto crediti per
    # l'owner (M3-1): filtra sulle due azioni di interesse per questo test.
    audit = db_session.scalars(
        select(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action.in_(
                [LeagueAuditAction.LEAGUE_CREATED, LeagueAuditAction.LEAGUE_RULES_UPDATED]
            ),
        )
        .order_by(LeagueAuditEvent.created_at.asc()),
    ).all()
    assert [event.action for event in audit] == [
        LeagueAuditAction.LEAGUE_CREATED,
        LeagueAuditAction.LEAGUE_RULES_UPDATED,
    ]
    assert audit[-1].actor_id == user_id


def test_update_league_rules_persists_minutes_threshold(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rules.minutes@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Soglia Minuti",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = created.json()["id"]
    payload = _standard_rules_payload()
    payload["minutesThreshold"] = 20

    updated = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert updated.status_code == 200
    assert updated.json()["minutesThreshold"] == 20

    persisted = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)),
    ).first()
    assert persisted is not None
    assert persisted.minutes_threshold == 20


def test_update_league_rules_rejects_invalid_minutes_threshold(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rules.minutes.invalid@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Soglia Invalida",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = created.json()["id"]
    payload = _standard_rules_payload()
    payload["minutesThreshold"] = 0

    updated = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert updated.status_code == 400
    assert updated.json()["code"] == "invalid_minutes_threshold"


def test_update_league_rules_persists_max_automatic_substitutions(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rules.subs@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Sostituzioni",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = created.json()["id"]

    payload = _standard_rules_payload()
    payload["maxAutomaticSubstitutions"] = 3

    updated = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert updated.status_code == 200
    assert updated.json()["maxAutomaticSubstitutions"] == 3

    persisted = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)),
    ).first()
    assert persisted is not None
    assert persisted.max_automatic_substitutions == 3


def test_update_league_rules_rejects_invalid_max_automatic_substitutions(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rules.subs.invalid@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Sostituzioni Invalide",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = created.json()["id"]
    payload = _standard_rules_payload()
    payload["maxAutomaticSubstitutions"] = 6

    updated = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert updated.status_code == 400
    assert updated.json()["code"] == "invalid_max_automatic_substitutions"


def test_update_league_rules_rejects_invalid_participants(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rules.invalid@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Regole Invalide",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = created.json()["id"]

    updated = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=_standard_rules_payload(participant_count=3),
    )
    assert updated.status_code == 400
    assert updated.json()["code"] == "invalid_participant_count"


def test_update_league_rules_is_idempotent_for_same_payload(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rules.idempotent@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Idempotente",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = created.json()["id"]
    payload = _standard_rules_payload(participant_count=9, total_credits=1100)

    first = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    second = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_RULES_UPDATED,
        )
    ).all()
    assert len(audit) == 1


def test_update_league_rules_requires_admin_role(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "rules.admin.owner@example.com")
    member_token, member_id = _register_and_login(client, "rules.admin.member@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Lega Permessi",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    league_id = UUID(created.json()["id"])
    db_session.add(
        LeagueMembership(
            league_id=league_id,
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        ),
    )
    db_session.commit()

    forbidden = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {member_token}"},
        json=_standard_rules_payload(participant_count=9),
    )
    allowed = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=_standard_rules_payload(participant_count=9),
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "forbidden"
    assert allowed.status_code == 200
