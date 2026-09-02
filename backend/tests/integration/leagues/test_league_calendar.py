"""Integration coverage for EP03-06 H2H calendar."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueCalendarStatus
from database.session import create_session_factory
from fantasy_turns.rules import weekend_window
from leagues.calendar_service import LeagueCalendarService
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar
from mail.capture import get_captured_emails
from tests.integration.fantasy_turns.test_fantasy_turns import (
    _seed_weekend_fixtures,
    _set_min_fixtures,
)


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
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


def _standard_rules_payload(participant_count: int) -> dict[str, object]:
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
        "totalCredits": 1000,
        "options": {"allowTrades": True, "allowManualInvites": True},
    }


def _create_league_with_members(
    client: TestClient,
    competition_ids: list[str],
    *,
    size: int,
    prefix: str,
) -> tuple[str, str, list[str]]:
    owner_token, _ = _register_and_login(client, f"{prefix}.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": f"Lega Calendario {prefix}",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = created.json()["id"]

    rules = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=_standard_rules_payload(size),
    )
    assert rules.status_code == 200

    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    member_tokens: list[str] = []
    for index in range(size - 1):
        token, _ = _register_and_login(client, f"{prefix}.member{index}@example.com")
        accepted = client.post(
            "/leagues/inviti/accetta",
            headers={"Authorization": f"Bearer {token}"},
            json={"token": invite.json()["token"]},
        )
        assert accepted.status_code == 200
        member_tokens.append(token)

    configuring = client.post(
        f"/leagues/{league_id}/amministrazione/stato",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"targetState": "configuring"},
    )
    assert configuring.status_code == 200
    return league_id, owner_token, member_tokens


def _seed_turns(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    league_id: str,
    token: str,
    anchors: list[date],
    id_offset: int,
) -> None:
    """Semina le partite e genera i Turni Europei per quelle finestre.

    Il Calendario fantallenatori si genera **dai** Turni Europei: senza turni
    non c'è niente da cui derivare le giornate, quindi ogni test che genera un
    calendario deve prima far esistere i turni.
    """
    for index, anchor in enumerate(anchors):
        kickoff = datetime(anchor.year, anchor.month, anchor.day, 15, 0, tzinfo=UTC)
        _seed_weekend_fixtures(
            db_session,
            competition_ids,
            count=10,
            kickoff=kickoff,
            id_offset=id_offset + index * 1_000,
            clubs_offset=770_000,
            league_id=league_id,
        )
        created = client.post(
            f"/leagues/{league_id}/turni",
            headers={"Authorization": f"Bearer {token}"},
            json={"kind": "weekend", "anchorDate": anchor.isoformat()},
        )
        assert created.status_code == 201, created.text


def test_generate_confirm_calendar_is_audited_and_clears_blocker(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    league_id, owner_token, member_tokens = _create_league_with_members(
        client,
        competition_ids,
        size=4,
        prefix="cal.ok",
    )
    _set_min_fixtures(db_session, league_id, 10)
    _seed_turns(
        client,
        db_session,
        competition_ids,
        league_id=league_id,
        token=owner_token,
        anchors=[date(2026, 12, 4), date(2026, 12, 11), date(2026, 12, 18)],
        id_offset=960_000,
    )

    empty = client.get(
        f"/leagues/{league_id}/amministrazione/calendario",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert empty.status_code == 200
    assert empty.json() is None

    forbidden = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {member_tokens[0]}"},
    )
    assert forbidden.status_code == 403

    generated = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["status"] == "draft"
    assert body["format"] == "single_round_robin"
    assert body["participantCount"] == 4
    assert body["roundCount"] == 3
    assert body["matchupCount"] == 6
    assert body["byeCount"] == 0
    assert len(body["rounds"]) == 3

    public_before = client.get(
        f"/leagues/{league_id}/calendario",
        headers={"Authorization": f"Bearer {member_tokens[0]}"},
    )
    assert public_before.status_code == 200
    assert public_before.json() is None

    confirmed = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/conferma",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    noop = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/conferma",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert noop.status_code == 200
    assert noop.json()["status"] == "confirmed"

    public_after = client.get(
        f"/leagues/{league_id}/calendario",
        headers={"Authorization": f"Bearer {member_tokens[0]}"},
    )
    assert public_after.status_code == 200
    assert public_after.json()["status"] == "confirmed"

    auction = client.post(
        f"/leagues/{league_id}/amministrazione/stato",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"targetState": "auction"},
    )
    assert auction.status_code == 200
    assert "calendar_not_configured" not in {
        row["code"] for row in auction.json()["blockers"]
    }
    assert {row["code"] for row in auction.json()["blockers"]} == {
        "fantasy_teams_not_configured",
    }

    db_session.expire_all()
    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == UUID(league_id))
    ).first()
    assert calendar is not None
    assert calendar.status == LeagueCalendarStatus.CONFIRMED
    audits = db_session.scalars(
        select(LeagueAuditEvent)
        .where(LeagueAuditEvent.league_id == UUID(league_id))
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    actions = [audit.action for audit in audits]
    assert LeagueAuditAction.LEAGUE_CALENDAR_GENERATED in actions
    assert LeagueAuditAction.LEAGUE_CALENDAR_CONFIRMED in actions
    assert actions.count(LeagueAuditAction.LEAGUE_CALENDAR_CONFIRMED) == 1


def test_calendar_generation_requires_exact_participant_count(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "cal.mismatch.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Lega Calendario Mismatch",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    assert (
        client.post(
            f"/leagues/{league_id}/amministrazione/stato",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"targetState": "configuring"},
        ).status_code
        == 200
    )

    response = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "participant_count_mismatch"


def test_odd_participant_calendar_uses_explicit_byes(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    league_id, owner_token, _ = _create_league_with_members(
        client,
        competition_ids,
        size=5,
        prefix="cal.odd",
    )
    _set_min_fixtures(db_session, league_id, 10)
    _seed_turns(
        client,
        db_session,
        competition_ids,
        league_id=league_id,
        token=owner_token,
        anchors=[
            date(2027, 1, 8),
            date(2027, 1, 15),
            date(2027, 1, 22),
            date(2027, 1, 29),
            date(2027, 2, 5),
        ],
        id_offset=965_000,
    )
    generated = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["participantCount"] == 5
    assert body["roundCount"] == 5
    assert body["matchupCount"] == 10
    assert body["byeCount"] == 5
    bye_rounds = [
        matchup
        for round_row in body["rounds"]
        for matchup in round_row["matchups"]
        if matchup["isBye"]
    ]
    assert len(bye_rounds) == 5
    assert all(matchup["awayUserId"] is None for matchup in bye_rounds)


def test_build_windows_excludes_windows_already_started_before_league_creation(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """A league created mid-season must not retroactively claim already-elapsed
    windows as its "Turno 1" (EP-turni-numerazione §1/§3)."""
    owner_token, _ = _register_and_login(client, "cal.created.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Lega Data Creazione",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    _set_min_fixtures(db_session, league_id, 10)

    before_creation = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    after_creation = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=before_creation, id_offset=990_000,
        clubs_offset=770_000,
        league_id=league_id,
    )
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=after_creation, id_offset=991_000,
        clubs_offset=770_000,
        league_id=league_id,
    )

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    # Simulate a league that was actually created once the August window had
    # already started (fixtures for it existed before the league did).
    league.created_at = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
    db_session.commit()
    db_session.expire(league)

    # I Turni Europei coprono l'intera stagione, quindi entrambe le finestre
    # esistono come turni; è l'eleggibilità a distinguerle.
    for anchor in (date(2026, 8, 15), date(2026, 9, 5)):
        created = client.post(
            f"/leagues/{league_id}/turni",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"kind": "weekend", "anchorDate": anchor.isoformat()},
        )
        assert created.status_code == 201, created.text

    windows = LeagueCalendarService(db_session).build_windows(league)
    eligible_bounds = {
        (window.start_at, window.end_at) for window in windows if window.eligible
    }

    excluded_window = weekend_window(date(2026, 8, 15))
    included_window = weekend_window(date(2026, 9, 5))
    # La finestra di agosto è iniziata prima della lega: resta come turno
    # (segnaposto) ma non può ospitare una giornata H2H.
    assert (excluded_window.start_at, excluded_window.end_at) not in eligible_bounds
    assert (included_window.start_at, included_window.end_at) in eligible_bounds


def test_h2h_round_numbers_match_absolute_european_turn_numbers(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Turno 1 del Calendario fantallenatori deve coincidere con il Turno 1
    dei Turni Europei; se la lega è creata dopo, i turni precedenti diventano
    segnaposto "Lega creata dopo questo turno" invece di essere rinumerati."""
    league_id, owner_token, _ = _create_league_with_members(
        client,
        competition_ids,
        size=4,
        prefix="cal.align",
    )
    _set_min_fixtures(db_session, league_id, 10)

    # Turno europeo "storico": materializzato prima della creazione della lega
    # (come farebbe il backfill stagionale di Turni Europei).
    historical_kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=historical_kickoff, id_offset=992_000,
        clubs_offset=770_000,
        league_id=league_id,
    )
    historical = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert historical.status_code == 201
    assert historical.json()["number"] == 1

    # La lega viene creata dopo quel turno.
    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.created_at = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    db_session.commit()
    db_session.expire(league)

    # 4 partecipanti → cycle_length 3: tre finestre successive alla
    # creazione bastano per un girone completo.
    for offset, id_offset in ((0, 993_000), (7, 994_000), (14, 995_000)):
        anchor = date(2026, 8, 22) + timedelta(days=offset)
        kickoff = datetime(anchor.year, anchor.month, anchor.day, 15, 0, tzinfo=UTC)
        _seed_weekend_fixtures(
            db_session, competition_ids, count=10, kickoff=kickoff, id_offset=id_offset,
            clubs_offset=770_000,
            league_id=league_id,
        )
        # Il calendario H2H deriva dai Turni Europei: vanno creati prima.
        turn = client.post(
            f"/leagues/{league_id}/turni",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"kind": "weekend", "anchorDate": anchor.isoformat()},
        )
        assert turn.status_code == 201, turn.text

    generated = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert generated.status_code == 200
    assert generated.json()["roundCount"] == 3

    confirmed = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/conferma",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert confirmed.status_code == 200

    h2h = client.get(
        f"/leagues/{league_id}/calendario/h2h",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert h2h.status_code == 200
    body = h2h.json()
    rounds = body["rounds"]

    # Turno 1 (storico, 15 agosto) compare come segnaposto, non come giornata H2H.
    placeholder = next(row for row in rounds if row["roundNumber"] == 1)
    assert placeholder["beforeLeagueCreation"] is True
    assert placeholder["matchups"] == []

    # Le tre giornate H2H reali portano i numeri assoluti 2, 3, 4 — non 1, 2, 3.
    real_rounds = [row for row in rounds if not row["beforeLeagueCreation"]]
    assert sorted(row["roundNumber"] for row in real_rounds) == [2, 3, 4]
    assert all(len(row["matchups"]) > 0 for row in real_rounds)


def test_a_window_that_is_not_a_valid_turn_produces_no_h2h_round(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Una finestra che non diventa Turno Europeo non genera giornata H2H.

    Prima una finestra sotto soglia diventava un turno "Non disputato"
    numerato, e nel calendario H2H compariva con l'etichetta sbagliata dei
    turni davvero storici. Ora non nasce alcun turno, quindi la garanzia e'
    piu' forte: le giornate H2H sono esattamente i Turni Europei, e i soli
    segnaposto sono i turni precedenti alla creazione della lega.
    """
    league_id, owner_token, _ = _create_league_with_members(
        client,
        competition_ids,
        size=4,
        prefix="cal.threshold",
    )
    _set_min_fixtures(db_session, league_id, 10)

    # Date scelte in una settimana non usata da nessun altro test del file:
    # `_seed_weekend_fixtures` aggiunge fixture condivise dalle stesse 3
    # competizioni/stagione per ogni test in questo modulo, quindi una data
    # riusata accumulerebbe le fixture di piu' test nella stessa finestra
    # reale, falsando la soglia.
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10,
        kickoff=datetime(2026, 11, 7, 15, 0, tzinfo=UTC), id_offset=996_000,
        clubs_offset=770_000,
        league_id=league_id,
    )
    historical = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"kind": "weekend", "anchorDate": "2026-11-07"},
    )
    assert historical.status_code == 201

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.created_at = datetime(2026, 11, 12, 0, 0, tzinfo=UTC)
    db_session.commit()
    db_session.expire(league)

    # Finestra successiva alla creazione ma con troppe poche partite: non
    # supera la soglia, quindi non diventa un turno affatto.
    # Niente `league_id`: seminare le rose anche qui darebbe ai fantallenatori
    # 11 giocatori proprio nei pochi club di questa finestra, cioe' copertura
    # piena — l'opposto di quello che il test vuole verificare.
    _seed_weekend_fixtures(
        db_session, competition_ids, count=2,
        kickoff=datetime(2026, 11, 14, 15, 0, tzinfo=UTC), id_offset=997_000,
        clubs_offset=770_000,
    )
    rejected = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"kind": "weekend", "anchorDate": "2026-11-14"},
    )
    assert rejected.status_code == 400

    for offset, id_offset in ((0, 998_000), (7, 999_000), (14, 999_500)):
        anchor = date(2026, 11, 21) + timedelta(days=offset)
        _seed_weekend_fixtures(
            db_session, competition_ids, count=10,
            kickoff=datetime(anchor.year, anchor.month, anchor.day, 15, 0, tzinfo=UTC),
            id_offset=id_offset,
            clubs_offset=770_000,
            league_id=league_id,
        )
        turn = client.post(
            f"/leagues/{league_id}/turni",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"kind": "weekend", "anchorDate": anchor.isoformat()},
        )
        assert turn.status_code == 201, turn.text

    generated = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert generated.status_code == 200
    confirmed = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/conferma",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert confirmed.status_code == 200

    h2h = client.get(
        f"/leagues/{league_id}/calendario/h2h",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert h2h.status_code == 200
    rounds = h2h.json()["rounds"]

    # Le giornate mostrate sono esattamente i Turni Europei della lega.
    turns = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()
    assert {row["roundNumber"] for row in rounds} == {row["number"] for row in turns}

    # L'unico segnaposto e' il turno precedente alla creazione della lega.
    placeholders = [row["roundNumber"] for row in rounds if row["beforeLeagueCreation"]]
    assert placeholders == [historical.json()["number"]]
