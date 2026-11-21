"""Il mercato si apre solo a lega al completo (decisione di Rosario del 20/11/2026).

Iscritti = partecipanti del regolamento. Finché la lega non è al completo restano fermi
l'inserimento in rosa del partecipante, le aste (buste, rilanci, svincolati) e gli scambi;
le operazioni dell'amministratore sulle rose no, nemmeno a interruttore spento: prepara le
rose in anticipo e si ferma solo a turno in corso. L'interruttore non si accende a lega
incompleta, una lega nuova nasce col mercato chiuso e, quando entra l'ultimo partecipante,
l'amministratore riceve un solo avviso «La lega è al completo: puoi aprire il mercato».

Questi test girano senza la compatibilità dei test precedenti (``tests/integration/conftest.py``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_rules import LeagueRules
from leagues.models.named_league_invite import NamedLeagueInvite
from mail.capture import get_captured_emails
from notifications.models import Notification
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

pytestmark = pytest.mark.league_capacity_rule

NOT_FULL_CODE = "league_not_full"


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def _create_league(
    client: TestClient,
    db_session: Session,
    token: str,
    competition_ids: list[str],
    name: str,
    *,
    participants: int = 4,
) -> str:
    response = client.post(
        "/leagues",
        headers=_auth(token),
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    league_id = response.json()["id"]
    _set_participants(db_session, league_id, participants)
    return league_id


def _set_participants(db_session: Session, league_id: str, participants: int) -> None:
    db_session.execute(
        update(LeagueRules)
        .where(LeagueRules.league_id == UUID(league_id))
        .values(participant_count=participants)
    )
    db_session.commit()


def _store_market_switch(db_session: Session, league_id: str, open_flag: bool) -> None:
    """Interruttore già salvato, come in una lega esistente prima della regola del 20/11."""
    db_session.execute(
        update(League).where(League.id == UUID(league_id)).values(market_open=open_flag)
    )
    db_session.commit()


def _join_with_code(client: TestClient, admin_token: str, league_id: str, token: str) -> str:
    """Ingresso reale col codice d'invito; restituisce l'id della squadra creata."""
    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers=_auth(admin_token),
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    accepted = client.post(
        "/leagues/inviti/accetta", headers=_auth(token), json={"code": invite.json()["code"]}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["alreadyMember"] is False
    return _team_id(client, league_id, token)


def _team_id(client: TestClient, league_id: str, token: str) -> str:
    rosa = client.get(f"/leagues/{league_id}/rosa", headers=_auth(token))
    assert rosa.status_code == 200
    return rosa.json()["id"]


def _seed_athlete(
    db_session: Session, provider_id: int, name: str, *, role: FantasyRole = FantasyRole.D
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=2026,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _assign(
    client: TestClient,
    league_id: str,
    token: str,
    team_id: str,
    slot_index: int,
    athlete: Athlete,
    credits: int = 1,
):
    return client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers=_auth(token),
        json={"athleteId": str(athlete.id), "purchaseCredits": credits},
    )


def _gate(client: TestClient, league_id: str, token: str) -> dict[str, object]:
    response = client.get(f"/leagues/{league_id}/mercato/stato", headers=_auth(token))
    assert response.status_code == 200
    return response.json()


def _assert_not_full(response, members: int, participants: int) -> None:
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == NOT_FULL_CODE
    assert body["message"] == (
        f"Il mercato si apre quando la lega è al completo ({members}/{participants} partecipanti)."
    )


def _window() -> dict[str, str]:
    now = datetime.now(UTC)
    return {
        "opensAt": (now - timedelta(minutes=1)).isoformat(),
        "closesAt": (now + timedelta(hours=2)).isoformat(),
    }


def _live_payload() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "opensAt": now.isoformat(),
        "closesAt": (now + timedelta(hours=2)).isoformat(),
        "nominationMode": "manual",
        "minIncrementCredits": 1,
        "softCloseSeconds": 5,
        "lotDurationSeconds": 300,
    }


def _trade(
    client: TestClient, league_id: str, token: str, recipient_team_id: str, offered, requested
):
    return client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_auth(token),
        json={
            "recipientTeamId": recipient_team_id,
            "offeredAthleteIds": [str(offered.id)],
            "requestedAthleteIds": [str(requested.id)],
            "offeredCredits": 0,
            "requestedCredits": 0,
            "expiresAt": None,
        },
    )


def _league_full_notifications(db_session: Session, user_id: UUID) -> list[Notification]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.template_key == "lega.al_completo",
            )
        ).all()
    )


def test_new_league_starts_with_market_closed_and_reports_capacity(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "full.new.admin@example.com")
    created = client.post(
        "/leagues",
        headers=_auth(token),
        json={"name": "Lega Nuova Chiusa", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["marketOpen"] is False
    assert body["memberCount"] == 1
    assert body["participantCount"] == 8
    assert body["leagueFull"] is False
    assert body["marketBlockedReason"] == NOT_FULL_CODE

    gate = _gate(client, body["id"], token)
    assert gate == {
        "marketOpen": False,
        "memberCount": 1,
        "participantCount": 8,
        "leagueFull": False,
        "marketBlockedReason": NOT_FULL_CODE,
        "pendingInviteCount": 0,
    }
    stored = db_session.scalar(select(League.market_open).where(League.id == UUID(body["id"])))
    assert stored is False
    # Anche il default della colonna (migrazione): una riga senza valore nasce chiusa.
    column_default = db_session.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'leagues' AND column_name = 'market_open'"
        )
    ).scalar_one()
    assert column_default == "false"


def test_switch_cannot_open_until_full_but_can_always_close(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "full.switch.admin@example.com")
    first_token, _ = _register_and_login(client, "full.switch.one@example.com")
    second_token, _ = _register_and_login(client, "full.switch.two@example.com")
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Switch")
    _join_with_code(client, admin_token, league_id, first_token)
    _join_with_code(client, admin_token, league_id, second_token)

    blocked = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    _assert_not_full(blocked, 3, 4)
    assert db_session.scalar(select(League.market_open).where(League.id == UUID(league_id))) is (
        False
    )

    # Lega esistente con l'interruttore già acceso: si spegne anche se non è al completo.
    _store_market_switch(db_session, league_id, True)
    closed = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": False}
    )
    assert closed.status_code == 200
    assert closed.json()["marketOpen"] is False
    assert closed.json()["memberCount"] == 3
    assert closed.json()["participantCount"] == 4
    assert closed.json()["marketBlockedReason"] == NOT_FULL_CODE


def test_new_league_admin_prepares_rosters_while_not_full_and_switch_off(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Lega nuova, 2/4 e interruttore spento: l'amministratore assegna e importa, il
    partecipante no (decisione del 20/11: l'amministratore prepara le rose in anticipo)."""
    admin_token, _ = _register_and_login(client, "full.prep.admin@example.com")
    member_token, _ = _register_and_login(client, "full.prep.member@example.com")
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Prep")
    admin_team_id = _team_id(client, league_id, admin_token)
    member_team_id = _join_with_code(client, admin_token, league_id, member_token)
    gate = _gate(client, league_id, admin_token)
    assert gate["marketOpen"] is False
    assert gate["memberCount"] == 2
    assert gate["marketBlockedReason"] == NOT_FULL_CODE

    member_pick = _seed_athlete(db_session, 97601, "Prep Scelta Membro")
    admin_pick = _seed_athlete(db_session, 97602, "Prep Scelta Admin")
    imported = _seed_athlete(db_session, 97603, "Prep Import", role=FantasyRole.A)

    # Il partecipante non si inserisce calciatori.
    _assert_not_full(_assign(client, league_id, member_token, member_team_id, 0, member_pick), 2, 4)

    # L'amministratore assegna su ogni squadra, rettifica il prezzo e svincola.
    assigned = _assign(client, league_id, admin_token, member_team_id, 0, member_pick, credits=4)
    assert assigned.status_code == 200, assigned.text
    corrected = _assign(client, league_id, admin_token, member_team_id, 0, member_pick, credits=2)
    assert corrected.status_code == 200, corrected.text
    own = _assign(client, league_id, admin_token, admin_team_id, 0, admin_pick)
    assert own.status_code == 200, own.text
    # Il partecipante non svincola il calciatore che l'amministratore gli ha dato.
    _assert_not_full(
        client.delete(
            f"/leagues/{league_id}/amministrazione/squadre/{member_team_id}/slot/0",
            headers=_auth(member_token),
        ),
        2,
        4,
    )
    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{admin_team_id}/slot/0",
        headers=_auth(admin_token),
    )
    assert released.status_code == 200, released.text

    # Import delle rose dell'amministratore, sempre a interruttore spento.
    member_team_name = client.get(f"/leagues/{league_id}/rosa", headers=_auth(member_token)).json()[
        "name"
    ]
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=_auth(admin_token),
        files={
            "file": (
                "rose.csv",
                (
                    "squadra,provider_id,nome,crediti\n"
                    f"{member_team_name},{imported.provider_id},{imported.canonical_name},6\n"
                ).encode(),
                "text/csv",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{preview.json()['importId']}/conferma",
        headers=_auth(admin_token),
        json={"resolutions": []},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 1

    # L'interruttore non si è mosso e un'asta resta ferma anche per l'amministratore.
    assert _gate(client, league_id, admin_token)["marketOpen"] is False
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/asta/sessioni",
            headers=_auth(admin_token),
            json=_window(),
        ),
        2,
        4,
    )


def test_not_full_blocks_participant_market_but_not_admin_roster_operations(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "full.block.admin@example.com")
    member_token, _ = _register_and_login(client, "full.block.member@example.com")
    other_token, _ = _register_and_login(client, "full.block.other@example.com")
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Ferma")
    admin_team_id = _team_id(client, league_id, admin_token)
    member_team_id = _join_with_code(client, admin_token, league_id, member_token)
    _join_with_code(client, admin_token, league_id, other_token)
    # Lega esistente con l'interruttore acceso: blocca solo la regola «al completo» (3/4).
    _store_market_switch(db_session, league_id, True)
    assert _gate(client, league_id, member_token)["marketBlockedReason"] == NOT_FULL_CODE

    own_pick = _seed_athlete(db_session, 97001, "Scelta Propria")
    admin_pick = _seed_athlete(db_session, 97002, "Scelta Admin")
    admin_own = _seed_athlete(db_session, 97003, "Rosa Admin")
    imported = _seed_athlete(db_session, 97004, "Import Excel", role=FantasyRole.A)

    _assert_not_full(_assign(client, league_id, member_token, member_team_id, 0, own_pick), 3, 4)

    # L'amministratore assegna, rettifica il prezzo e svincola su ogni squadra.
    assigned = _assign(client, league_id, admin_token, member_team_id, 0, admin_pick, credits=5)
    assert assigned.status_code == 200, assigned.text
    corrected = _assign(client, league_id, admin_token, member_team_id, 0, admin_pick, credits=3)
    assert corrected.status_code == 200, corrected.text
    assert (
        client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{admin_team_id}/slot/0",
            headers=_auth(admin_token),
            json={"athleteId": str(admin_own.id), "purchaseCredits": 1},
        ).status_code
        == 200
    )

    # Lo svincolo del partecipante resta fermo, quello dell'amministratore no.
    _assert_not_full(
        client.delete(
            f"/leagues/{league_id}/amministrazione/squadre/{member_team_id}/slot/0",
            headers=_auth(member_token),
        ),
        3,
        4,
    )
    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{member_team_id}/slot/0",
        headers=_auth(admin_token),
    )
    assert released.status_code == 200, released.text

    # Import delle rose dell'amministratore.
    member_team_name = client.get(f"/leagues/{league_id}/rosa", headers=_auth(member_token)).json()[
        "name"
    ]
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=_auth(admin_token),
        files={
            "file": (
                "rose.csv",
                (
                    "squadra,provider_id,nome,crediti\n"
                    f"{member_team_name},{imported.provider_id},{imported.canonical_name},7\n"
                ).encode(),
                "text/csv",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{preview.json()['importId']}/conferma",
        headers=_auth(admin_token),
        json={"resolutions": []},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 1

    # Aste, svincolati e scambi: fermi per tutti.
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/asta/sessioni",
            headers=_auth(admin_token),
            json=_window(),
        ),
        3,
        4,
    )
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/asta-live/sessioni",
            headers=_auth(admin_token),
            json=_live_payload(),
        ),
        3,
        4,
    )
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/svincoli/sessioni",
            headers=_auth(admin_token),
            json=_window(),
        ),
        3,
        4,
    )
    _assert_not_full(
        _trade(client, league_id, member_token, admin_team_id, imported, admin_own), 3, 4
    )


def test_sealed_bid_and_trades_stop_when_the_league_is_no_longer_full(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "full.stop.admin@example.com")
    tokens = [
        _register_and_login(client, f"full.stop.member{index}@example.com")[0] for index in range(3)
    ]
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Buste")
    admin_team_id = _team_id(client, league_id, admin_token)
    team_ids = [_join_with_code(client, admin_token, league_id, token) for token in tokens]
    db_session.execute(
        update(LeagueRules)
        .where(LeagueRules.league_id == UUID(league_id))
        .values(require_trade_approval=True)
    )
    db_session.commit()
    opened = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["marketBlockedReason"] is None

    admin_player = _seed_athlete(db_session, 97101, "Buste Admin")
    member_player = _seed_athlete(db_session, 97102, "Buste Membro")
    other_player = _seed_athlete(db_session, 97103, "Buste Altro")
    free_agent = _seed_athlete(db_session, 97104, "Buste Libero")
    for team_id, athlete in (
        (admin_team_id, admin_player),
        (team_ids[0], member_player),
        (team_ids[1], other_player),
    ):
        assert _assign(client, league_id, admin_token, team_id, 0, athlete).status_code == 200

    session = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni", headers=_auth(admin_token), json=_window()
    )
    assert session.status_code == 201, session.text
    to_accept = _trade(client, league_id, admin_token, team_ids[0], admin_player, member_player)
    assert to_accept.status_code == 201, to_accept.text
    to_approve = _trade(client, league_id, tokens[1], team_ids[0], other_player, member_player)
    assert to_approve.status_code == 201, to_approve.text
    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{to_approve.json()['id']}/accetta",
        headers=_auth(tokens[0]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "pending_approval"

    # Il regolamento passa a 5 partecipanti: la lega non è più al completo (4/5).
    _set_participants(db_session, league_id, 5)

    _assert_not_full(
        client.put(
            f"/leagues/{league_id}/mercato/asta/sessioni/{session.json()['id']}/offerte/{free_agent.id}",
            headers=_auth(tokens[2]),
            json={"amountCredits": 10},
        ),
        4,
        5,
    )
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{to_accept.json()['id']}/accetta",
            headers=_auth(tokens[0]),
        ),
        4,
        5,
    )
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{to_accept.json()['id']}/controproponi",
            headers=_auth(tokens[0]),
            json={
                "offeredAthleteIds": [str(member_player.id)],
                "requestedAthleteIds": [str(admin_player.id)],
                "offeredCredits": 0,
                "requestedCredits": 0,
                "expiresAt": None,
            },
        ),
        4,
        5,
    )
    _assert_not_full(
        client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{to_approve.json()['id']}/amministrazione/approva",
            headers=_auth(admin_token),
        ),
        4,
        5,
    )
    # Rifiutare resta possibile: non sposta nulla.
    rejected = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{to_accept.json()['id']}/rifiuta",
        headers=_auth(tokens[0]),
    )
    assert rejected.status_code == 200, rejected.text


def test_live_raise_and_waiver_bid_stop_when_the_league_is_no_longer_full(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "full.live.admin@example.com")
    tokens = [
        _register_and_login(client, f"full.live.member{index}@example.com")[0] for index in range(3)
    ]
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Rilanci")
    team_ids = [_join_with_code(client, admin_token, league_id, token) for token in tokens]
    opened = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    assert opened.status_code == 200, opened.text

    owned = _seed_athlete(db_session, 97201, "Rilanci Svincolabile")
    on_the_block = _seed_athlete(db_session, 97202, "Rilanci Lotto")
    waiver_target = _seed_athlete(db_session, 97203, "Rilanci Svincolato")
    assert _assign(client, league_id, admin_token, team_ids[0], 0, owned).status_code == 200

    waiver = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni",
        headers=_auth(admin_token),
        json=_window(),
    )
    assert waiver.status_code == 201, waiver.text
    live = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers=_auth(admin_token),
        json=_live_payload(),
    )
    assert live.status_code == 201, live.text
    live_id = live.json()["id"]
    started = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/avvia",
        headers=_auth(admin_token),
    )
    assert started.status_code == 200, started.text
    lot = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/lotti/nomina",
        headers=_auth(admin_token),
        json={"athleteId": str(on_the_block.id)},
    )
    assert lot.status_code == 201, lot.text

    _set_participants(db_session, league_id, 5)

    _assert_not_full(
        client.put(
            f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_id}/lotti/{lot.json()['id']}/rilanci",
            headers=_auth(tokens[1]),
            json={"amountCredits": 10},
        ),
        4,
        5,
    )
    _assert_not_full(
        client.put(
            f"/leagues/{league_id}/mercato/svincoli/sessioni/{waiver.json()['id']}/offerte/{waiver_target.id}",
            headers=_auth(tokens[0]),
            json={"amountCredits": 10, "releaseAthleteId": str(owned.id)},
        ),
        4,
        5,
    )


def test_last_member_joining_notifies_the_admin_once_and_the_market_stays_closed(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, admin_id = _register_and_login(client, "full.notify.admin@example.com")
    tokens = [
        _register_and_login(client, f"full.notify.member{index}@example.com")[0]
        for index in range(3)
    ]
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Avviso")
    _join_with_code(client, admin_token, league_id, tokens[0])
    _join_with_code(client, admin_token, league_id, tokens[1])
    assert _league_full_notifications(db_session, admin_id) == []

    last_team_id = _join_with_code(client, admin_token, league_id, tokens[2])

    notifications = _league_full_notifications(db_session, admin_id)
    assert len(notifications) == 1
    assert notifications[0].title == "La lega è al completo: puoi aprire il mercato"
    assert notifications[0].deep_link == f"/lega/amministrazione?lega={league_id}"
    assert notifications[0].dedup_key == f"league_full:{league_id}:{admin_id}"

    # Il mercato non si apre da solo.
    gate = _gate(client, league_id, admin_token)
    assert gate["leagueFull"] is True
    assert gate["memberCount"] == 4
    assert gate["marketOpen"] is False
    assert gate["marketBlockedReason"] == "market_closed"
    athlete = _seed_athlete(db_session, 97301, "Avviso Calciatore")
    still_closed = _assign(client, league_id, tokens[2], last_team_id, 0, athlete)
    assert still_closed.status_code == 400
    assert still_closed.json()["code"] == "market_closed"

    # Un secondo passaggio (altro ingresso, sostituzione) non ripete l'avviso.
    from notifications.league_events import notify_league_full_if_needed

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    notify_league_full_if_needed(db_session, league=league)
    db_session.commit()
    assert len(_league_full_notifications(db_session, admin_id)) == 1

    opened = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["marketOpen"] is True
    assert opened.json()["marketBlockedReason"] is None


def test_full_league_with_open_switch_allows_self_assignment(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "full.open.admin@example.com")
    tokens = [
        _register_and_login(client, f"full.open.member{index}@example.com")[0] for index in range(3)
    ]
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Aperta")
    team_ids = [_join_with_code(client, admin_token, league_id, token) for token in tokens]
    athlete = _seed_athlete(db_session, 97401, "Scelta Libera")

    # Al completo ma con l'interruttore ancora spento: serve che l'amministratore lo accenda.
    before = _assign(client, league_id, tokens[0], team_ids[0], 0, athlete)
    assert before.status_code == 400
    assert before.json()["code"] == "market_closed"

    opened = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["leagueFull"] is True
    assert opened.json()["marketBlockedReason"] is None

    assigned = _assign(client, league_id, tokens[0], team_ids[0], 0, athlete)
    assert assigned.status_code == 200, assigned.text
    assert any(slot["athleteId"] == str(athlete.id) for slot in assigned.json()["slots"])


def test_member_removed_blocks_the_market_again_and_keeps_the_switch(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "full.leave.admin@example.com")
    members = [
        _register_and_login(client, f"full.leave.member{index}@example.com") for index in range(3)
    ]
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Uscita")
    team_ids = [_join_with_code(client, admin_token, league_id, token) for token, _ in members]
    opened = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    assert opened.status_code == 200, opened.text

    removed = client.delete(
        f"/leagues/{league_id}/amministrazione/partecipanti/{members[2][1]}",
        headers=_auth(admin_token),
    )
    assert removed.status_code == 200, removed.text

    gate = _gate(client, league_id, admin_token)
    assert gate["marketOpen"] is True  # l'interruttore salvato resta com'è
    assert gate["leagueFull"] is False
    assert gate["memberCount"] == 3
    assert gate["participantCount"] == 4
    assert gate["marketBlockedReason"] == NOT_FULL_CODE

    athlete = _seed_athlete(db_session, 97501, "Dopo Uscita")
    _assert_not_full(_assign(client, league_id, members[0][0], team_ids[0], 0, athlete), 3, 4)


# -- inviti nominativi in attesa accanto al conto (Rosario, 20/11) ----------------------------


def _named_invite(client: TestClient, league_id: str, admin_token: str, recipient_id: UUID) -> str:
    response = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers=_auth(admin_token),
        json={"recipientUserId": str(recipient_id)},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _expire_named_invite(db_session: Session, invite_id: str) -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    db_session.execute(
        update(NamedLeagueInvite)
        .where(NamedLeagueInvite.id == UUID(invite_id))
        .values(created_at=past - timedelta(days=7), expires_at=past)
    )
    db_session.commit()


def test_pending_named_invites_are_reported_next_to_the_member_count(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """«2/4 · 1 invito in attesa»: gli inviti nominativi in attesa e non scaduti, gli stessi che
    tengono il posto all'ingresso con il codice. La lega resta non al completo: contano solo gli
    iscritti."""
    admin_token, _ = _register_and_login(client, "pending.count.admin@example.com")
    member_token, _ = _register_and_login(client, "pending.count.member@example.com")
    invited = [
        _register_and_login(client, f"pending.count.invited{index}@example.com")
        for index in range(3)
    ]
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Inviti")
    gate = _gate(client, league_id, admin_token)
    assert (gate["memberCount"], gate["pendingInviteCount"]) == (1, 0)

    invite_ids = [_named_invite(client, league_id, admin_token, user_id) for _, user_id in invited]
    gate = _gate(client, league_id, admin_token)
    assert gate["memberCount"] == 1
    assert gate["participantCount"] == 4
    assert gate["pendingInviteCount"] == 3
    assert gate["leagueFull"] is False
    assert gate["marketBlockedReason"] == NOT_FULL_CODE

    # Non contano l'invito scaduto e quello rifiutato.
    _expire_named_invite(db_session, invite_ids[2])
    declined = client.post(
        f"/leagues/inviti-ricevuti/{invite_ids[1]}/rifiuta", headers=_auth(invited[1][0])
    )
    assert declined.status_code == 200, declined.text
    _join_with_code(client, admin_token, league_id, member_token)
    gate = _gate(client, league_id, admin_token)
    assert (gate["memberCount"], gate["pendingInviteCount"]) == (2, 1)

    # Lo stesso nel dettaglio della lega e nel messaggio del blocco.
    detail = client.get(f"/leagues/{league_id}", headers=_auth(admin_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["memberCount"] == 2
    assert detail.json()["pendingInviteCount"] == 1
    assert detail.json()["leagueFull"] is False
    blocked = client.post(
        f"/leagues/{league_id}/mercato/stato", headers=_auth(admin_token), json={"open": True}
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == NOT_FULL_CODE
    assert blocked.json()["message"] == (
        "Il mercato si apre quando la lega è al completo (2/4 partecipanti · 1 invito in attesa)."
    )

    # Accettato, l'invito diventa un iscritto.
    accepted = client.post(
        f"/leagues/inviti-ricevuti/{invite_ids[0]}/accetta", headers=_auth(invited[0][0])
    )
    assert accepted.status_code == 200, accepted.text
    gate = _gate(client, league_id, admin_token)
    assert (gate["memberCount"], gate["pendingInviteCount"]) == (3, 0)
    assert gate["leagueFull"] is False


def test_code_join_refused_because_pending_invites_hold_the_last_seats(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """3/4 con un invito nominativo in attesa: il codice non entra e il messaggio dice perché. A
    lega piena di iscritti il messaggio resta quello di sempre. Il codice è ``league_full``."""
    admin_token, _ = _register_and_login(client, "reserved.seats.admin@example.com")
    members = [
        _register_and_login(client, f"reserved.seats.member{index}@example.com")
        for index in range(2)
    ]
    invited_token, invited_id = _register_and_login(client, "reserved.seats.invited@example.com")
    outsider_token, _ = _register_and_login(client, "reserved.seats.outsider@example.com")
    league_id = _create_league(client, db_session, admin_token, competition_ids, "Lega Riservata")
    for token, _ in members:
        _join_with_code(client, admin_token, league_id, token)
    invite_id = _named_invite(client, league_id, admin_token, invited_id)
    link = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers=_auth(admin_token),
        json={"expiresInDays": 7},
    )
    assert link.status_code == 201, link.text
    code = link.json()["code"]

    reserved = client.post(
        "/leagues/inviti/accetta", headers=_auth(outsider_token), json={"code": code}
    )
    assert reserved.status_code == 400, reserved.text
    assert reserved.json()["code"] == "league_full"
    assert reserved.json()["message"] == (
        "La lega è al completo: i posti rimasti sono riservati a inviti in attesa."
    )

    # Chi ha l'invito entra anche con il codice; dopo la lega è piena di iscritti.
    joined = client.post(
        "/leagues/inviti/accetta", headers=_auth(invited_token), json={"code": code}
    )
    assert joined.status_code == 200, joined.text
    stored = db_session.get(NamedLeagueInvite, UUID(invite_id))
    assert stored is not None
    db_session.refresh(stored)
    assert stored.status.value == "accepted"
    full = client.post(
        "/leagues/inviti/accetta", headers=_auth(outsider_token), json={"code": code}
    )
    assert full.status_code == 400, full.text
    assert full.json()["code"] == "league_full"
    assert full.json()["message"] == "La lega ha raggiunto il numero massimo di partecipanti."
