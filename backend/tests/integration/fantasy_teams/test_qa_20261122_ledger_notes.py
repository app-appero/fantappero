"""QA 21→22/11: nomi dei calciatori rovinati nelle note dello storico crediti.

«Assegnazione L. JovanoviÄ», «D. O&apos;Shea», «Acquisto N. Kovač \\u008d»: le note
si scrivevano con il nome com'era salvato, e la riparazione alla lettura del 21/11
(`AthleteNameStr`) non toccava le note del registro.
"""

from __future__ import annotations

import re
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import CreditLedgerReason, FantasyRole
from database.session import create_session_factory
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import CreditAccount, CreditLedgerEntry
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

# Come arrivavano dal fornitore e come vanno mostrati.
JOVANOVIC = ("L. JovanoviÄ\u0087", "L. Jovanović")
OSHEA = ("D. O&apos;Shea", "D. O'Shea")
KOVAC = ("N. Kovač \u008d", "N. Kovač")


def _register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"]


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create_league(client: TestClient, token: str, db_session: Session, name: str) -> str:
    competition_ids = [
        str(row.id)
        for row in db_session.scalars(select(Competition).order_by(Competition.name)).all()[:3]
    ]
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _seed_athlete(db_session: Session, name: str, role: FantasyRole) -> Athlete:
    athlete = Athlete(provider_id=uuid.uuid4().int % 900_000_000 + 100_000_000, canonical_name=name)
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


def _stored_notes(db_session: Session, team_id: str) -> list[tuple[CreditLedgerReason, str]]:
    db_session.expire_all()
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    entries = db_session.scalars(
        select(CreditLedgerEntry)
        .where(CreditLedgerEntry.account_id == account.id)
        .order_by(CreditLedgerEntry.created_at, CreditLedgerEntry.id)
    ).all()
    return [
        (entry.reason, entry.note)
        for entry in entries
        if entry.reason != CreditLedgerReason.INITIAL_ALLOCATION and entry.note is not None
    ]


def _shown_notes(client: TestClient, token: str, league_id: str) -> dict[str, str | None]:
    response = client.get(
        f"/leagues/{league_id}/crediti/movimenti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return {entry["transactionId"]: entry["note"] for entry in response.json()["entries"]}


def test_ledger_notes_are_written_with_repaired_athlete_names(
    client: TestClient, db_session: Session
) -> None:
    token = _register_and_login(client, "qa2211.ledger.write@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    league_id = _create_league(client, token, db_session, "Lega Note Pulite")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()
    team_id = rosa["id"]
    jovanovic = _seed_athlete(db_session, JOVANOVIC[0], FantasyRole.A)
    oshea = _seed_athlete(db_session, OSHEA[0], FantasyRole.D)
    kovac = _seed_athlete(db_session, KOVAC[0], FantasyRole.C)
    slot_path = f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot"

    # Acquisto, rettifica del prezzo e rimborso (l'amministratore corregge la rosa).
    for price in (20, 25):
        assigned = client.put(
            f"{slot_path}/0",
            headers=headers,
            json={"athleteId": str(jovanovic.id), "purchaseCredits": price},
        )
        assert assigned.status_code == 200, assigned.text
    assert client.delete(f"{slot_path}/0", headers=headers).status_code == 200

    # Svincolo dal mercato.
    assigned = client.put(
        f"{slot_path}/1", headers=headers, json={"athleteId": str(oshea.id), "purchaseCredits": 30}
    )
    assert assigned.status_code == 200, assigned.text
    released = client.post(
        f"/leagues/{league_id}/mercato/svincolo/1", headers=headers, json={"reason": "voluntary"}
    )
    assert released.status_code == 200, released.text

    # Assegnazione da import delle rose.
    csv_body = (
        f"squadra,provider_id,nome,crediti\n{rosa['name']},{kovac.provider_id},Kovač,10\n"
    ).encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=headers,
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{preview.json()['importId']}/conferma",
        headers=headers,
        json={"resolutions": []},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 1

    expected = [
        (CreditLedgerReason.ROSTER_PURCHASE, f"Acquisto {JOVANOVIC[1]}"),
        (CreditLedgerReason.ROSTER_PURCHASE, f"Rettifica prezzo {JOVANOVIC[1]}"),
        (CreditLedgerReason.ROSTER_RELEASE_REFUND, f"Rimborso {JOVANOVIC[1]}"),
        (CreditLedgerReason.ROSTER_PURCHASE, f"Acquisto {OSHEA[1]}"),
        (CreditLedgerReason.MARKET_RELEASE_REFUND, f"Svincolo {OSHEA[1]} (voluntary, 50%)"),
        (CreditLedgerReason.ROSTER_PURCHASE, f"Assegnazione {KOVAC[1]}"),
    ]
    # Salvate già pulite nel registro, e così arrivano a web e app.
    assert _stored_notes(db_session, team_id) == expected
    shown = _shown_notes(client, token, league_id).values()
    assert sorted(note for note in shown if note and not note.startswith("Allocazione")) == sorted(
        note for _, note in expected
    )


def test_broken_notes_already_stored_are_shown_repaired_admin_note_untouched(
    client: TestClient, db_session: Session
) -> None:
    token = _register_and_login(client, "qa2211.ledger.read@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    league_id = _create_league(client, token, db_session, "Lega Note Vecchie")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["id"]

    # Movimenti scritti la notte del 21→22/11, prima della correzione.
    account = find_account_for_team(db_session, UUID(team_id), for_update=True)
    assert account is not None
    stored = {
        "qa2211-assegnazione": (
            CreditLedgerReason.ROSTER_PURCHASE,
            f"Assegnazione {JOVANOVIC[0]}",
            f"Assegnazione {JOVANOVIC[1]}",
        ),
        "qa2211-acquisto": (
            CreditLedgerReason.ROSTER_PURCHASE,
            f"Acquisto {KOVAC[0]}",
            f"Acquisto {KOVAC[1]}",
        ),
        "qa2211-svincolo": (
            CreditLedgerReason.MARKET_RELEASE_REFUND,
            f"Svincolo {OSHEA[0]} (voluntary, 50%)",
            f"Svincolo {OSHEA[1]} (voluntary, 50%)",
        ),
    }
    for transaction_id, (reason, note, _shown) in stored.items():
        amount = 5 if reason == CreditLedgerReason.MARKET_RELEASE_REFUND else -5
        apply_ledger_movement(
            db_session,
            account,
            amount=amount,
            reason=reason,
            transaction_id=transaction_id,
            note=note,
        )
    db_session.commit()

    # La nota libera dell'amministratore resta com'è scritta, anche se somiglia a un nome
    # rovinato o a un riferimento dell'HTML.
    admin_note = "Bonus R&amp;D per JovanoviÄ\u0087"
    adjusted = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers=headers,
        json={
            "fantasyTeamId": team_id,
            "amount": 7,
            "transactionId": "qa2211-nota-admin",
            "note": admin_note,
        },
    )
    assert adjusted.status_code == 200, adjusted.text

    shown = _shown_notes(client, token, league_id)
    for transaction_id, (_reason, _note, expected) in stored.items():
        assert shown[transaction_id] == expected
    assert shown["qa2211-nota-admin"] == admin_note
    # Il registro non si riscrive: nel database restano com'erano.
    assert [note for _, note in _stored_notes(db_session, team_id)] == [
        *(note for _reason, note, _shown in stored.values()),
        admin_note,
    ]
