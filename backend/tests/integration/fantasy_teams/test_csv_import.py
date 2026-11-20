"""Integration tests for CSV roster import preview/confirm (EP05-04)."""

from __future__ import annotations

import io
import random
import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import FantasyRosterSlot, RosterImportSession
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


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


def _create_league(
    client: TestClient,
    token: str,
    competition_ids: list[str],
    name: str,
) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_athlete(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole = FantasyRole.A,
    season_year: int = 2026,
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def test_csv_template_and_preview_does_not_write_roster(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "csv.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    team_name = rosa.json()["name"]
    athlete = _seed_athlete(db_session, 9001, "CSV Player")

    template = client.get(
        f"/leagues/{league_id}/amministrazione/import-csv/modello",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert template.status_code == 200
    assert "text/csv" in template.headers["content-type"]
    assert b"squadra,provider_id,nome,crediti" in template.content

    csv_body = (
        f"squadra,provider_id,nome,crediti\n"
        f"{team_name},{athlete.provider_id},{athlete.canonical_name},15\n"
    ).encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["canConfirm"] is True
    assert body["errorCount"] == 0
    assert body["rows"][0]["status"] == "ok"
    assert body["rows"][0]["athleteId"] == str(athlete.id)

    filled = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.league_id == UUID(league_id),
            FantasyRosterSlot.athlete_id == athlete.id,
        )
    )
    assert filled is None


def test_csv_confirm_atomic_and_idempotent(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "csv.confirm@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Confirm")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    team_name = rosa.json()["name"]
    team_id = rosa.json()["id"]
    a1 = _seed_athlete(db_session, 9101, "Import One")
    a2 = _seed_athlete(db_session, 9102, "Import Two")

    csv_body = (
        "squadra,provider_id,nome,crediti\n"
        f"{team_name},{a1.provider_id},{a1.canonical_name},20\n"
        f"{team_name},{a2.provider_id},{a2.canonical_name},30\n"
    ).encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200
    import_id = preview.json()["importId"]

    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{import_id}/conferma",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolutions": []},
    )
    assert confirm.status_code == 200
    assert confirm.json()["assignedCount"] == 2
    assert confirm.json()["status"] == "confirmed"

    slots = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.athlete_id.is_not(None),
        )
    ).all()
    assert len(slots) == 2
    assert {slot.athlete_id for slot in slots} == {a1.id, a2.id}

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert credits.status_code == 200
    assert credits.json()["balance"] == 1000 - 50

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_CSV_IMPORTED,
        )
    ).all()
    assert len(audit) == 1

    again = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{import_id}/conferma",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolutions": []},
    )
    assert again.status_code == 200
    assert again.json()["assignedCount"] == 2
    audit_again = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_CSV_IMPORTED,
        )
    ).all()
    assert len(audit_again) == 1


def test_csv_preview_row_errors_and_member_forbidden(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "csv.admin2@example.com")
    member_token, member_id = _register_and_login(client, "csv.member2@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega CSV Err")
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=member_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()

    # Ensure owner team exists
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {owner_token}"})

    bad = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {owner_token}"},
        files={
            "file": (
                "bad.csv",
                b"squadra,provider_id,nome,crediti\nGhost,99999,Nobody,5\n",
                "text/csv",
            )
        },
    )
    assert bad.status_code == 200
    assert bad.json()["canConfirm"] is False
    assert bad.json()["errorCount"] >= 1
    assert bad.json()["rows"][0]["status"] == "error"

    forbidden = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers={"Authorization": f"Bearer {member_token}"},
        files={"file": ("x.csv", b"squadra,provider_id,nome,crediti\nA,1,B,1\n", "text/csv")},
    )
    assert forbidden.status_code in {403, 401}

    sessions = db_session.scalars(
        select(RosterImportSession).where(RosterImportSession.league_id == UUID(league_id))
    ).all()
    assert len(sessions) >= 1
    assert all(row.status.value == "draft" for row in sessions)


def test_csv_preview_oversized_numbers_and_nul_byte_are_errors_not_500(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "csv.huge@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega CSV Enormi")
    headers = {"Authorization": f"Bearer {owner_token}"}
    url = f"/leagues/{league_id}/amministrazione/import-csv/anteprima"

    huge = client.post(
        url,
        headers=headers,
        files={
            "file": (
                "huge.csv",
                b"squadra,provider_id,nome,crediti\nA,99999999999999999999,B,5\nA,1,B,99999999999\n",
                "text/csv",
            )
        },
    )
    assert huge.status_code == 200
    assert huge.json()["canConfirm"] is False
    assert all(row["status"] == "error" for row in huge.json()["rows"])

    nul = client.post(
        url,
        headers=headers,
        files={
            "file": ("nul.csv", b"squadra,provider_id,nome,crediti\nA,1,B\x00C,1\n", "text/csv")
        },
    )
    assert nul.status_code == 400
    assert nul.json()["code"] == "csv_invalid_encoding"


def test_slot_edge_values_are_clean_errors_not_500(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "csv.edge@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Valori Limite")
    headers = {"Authorization": f"Bearer {owner_token}"}
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["id"]
    base = f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot"

    too_costly = client.put(
        f"{base}/0", headers=headers, json={"athleteId": "x", "purchaseCredits": 3_000_000_000}
    )
    assert too_costly.status_code == 422
    huge_index = client.delete(f"{base}/99999999999", headers=headers)
    assert huge_index.status_code == 400
    assert huge_index.json()["code"] == "slot_not_found"


def test_csv_reimport_after_release_charges_again_and_preview_flags_role_quota(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "csv.reimport@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Reimport")
    headers = {"Authorization": f"Bearer {token}"}
    rosa = client.get(f"/leagues/{league_id}/rosa", headers=headers)
    team_name = rosa.json()["name"]
    team_id = rosa.json()["id"]
    player = _seed_athlete(db_session, 9301, "Reimport One")
    csv_body = (
        f"squadra,provider_id,nome,crediti\n{team_name},{player.provider_id},"
        f"{player.canonical_name},10\n"
    ).encode()

    def import_once() -> None:
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

    def balance() -> int:
        return client.get(f"/leagues/{league_id}/crediti", headers=headers).json()["balance"]

    start = balance()
    import_once()
    assert balance() == start - 10
    slot_index = db_session.scalar(
        select(FantasyRosterSlot.slot_index).where(FantasyRosterSlot.athlete_id == player.id)
    )
    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers=headers,
    )
    assert released.status_code == 200
    assert balance() == start  # l'admin restituisce l'intero prezzo
    import_once()
    assert balance() == start - 10  # il secondo import addebita di nuovo


def test_csv_preview_flags_rows_over_the_role_quota(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "csv.quota@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Quota")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    lines = ["squadra,provider_id,nome,crediti"]
    for index in range(4):  # il limite di portieri è 3
        keeper = _seed_athlete(
            db_session,
            random.randint(100_000_000, 2_000_000_000),
            f"Portiere Quota {index}",
            role=FantasyRole.P,
        )
        lines.append(f"{team_name},{keeper.provider_id},{keeper.canonical_name},5")
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=headers,
        files={"file": ("rose.csv", "\n".join(lines).encode(), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["canConfirm"] is False
    flagged = [
        row
        for row in body["rows"]
        if any(i["code"] == "role_quota_exceeded" for i in row["issues"])
    ]
    assert len(flagged) == 1


def test_csv_rows_over_quota_do_not_take_slots_from_valid_rows(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 18/11: le righe oltre la quota di ruolo occupavano slot e le righe
    valide successive ricevevano `roster_full`."""
    token, _ = _register_and_login(client, "csv.quota.slots@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Quota Slot")
    headers = {"Authorization": f"Bearer {token}"}
    rosa = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()
    team_name = rosa["name"]
    roster_size = len(rosa["slots"])
    lines = ["squadra,provider_id,nome,crediti"]
    # Tutti portieri tranne l'ultimo slot: oltre il terzo sono fuori quota.
    for index in range(roster_size - 1):
        keeper = _seed_athlete(
            db_session,
            random.randint(100_000_000, 2_000_000_000),
            f"Portiere Slot {index}",
            role=FantasyRole.P,
        )
        lines.append(f"{team_name},{keeper.provider_id},{keeper.canonical_name},1")
    forwards = [
        _seed_athlete(
            db_session,
            random.randint(100_000_000, 2_000_000_000),
            f"Attaccante Slot {index}",
            role=FantasyRole.A,
        )
        for index in range(3)
    ]
    for forward in forwards:
        lines.append(f"{team_name},{forward.provider_id},{forward.canonical_name},1")
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=headers,
        files={"file": ("rose.csv", "\n".join(lines).encode(), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    forward_ids = {str(forward.id) for forward in forwards}
    forward_rows = [row for row in rows if row["athleteId"] in forward_ids]
    assert len(forward_rows) == 3
    for row in forward_rows:
        assert row["status"] == "ok", row
        assert not any(issue["code"] == "roster_full" for issue in row["issues"])
    keeper_rows = [row for row in rows if row["athleteId"] not in forward_ids]
    assert sum(1 for row in keeper_rows if row["status"] == "ok") == 3
    assert all(
        any(issue["code"] == "role_quota_exceeded" for issue in row["issues"])
        for row in keeper_rows
        if row["status"] != "ok"
    )


def test_csv_ambiguous_name_can_be_resolved_on_confirm(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 18/11: il nome ambiguo era un errore bloccante e la conferma con la
    scelta del candidato rispondeva `import_has_errors`."""
    token, _ = _register_and_login(client, "csv.ambiguous@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Ambiguo")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    surname = f"Omonimo{random.randint(100_000, 999_999)}"
    first = _seed_athlete(db_session, random.randint(100_000_000, 2_000_000_000), f"P. {surname}")
    _seed_athlete(db_session, random.randint(100_000_000, 2_000_000_000), f"S. {surname}")
    csv_body = f"squadra,provider_id,nome,crediti\n{team_name},,{surname},12\n".encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=headers,
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    assert row["status"] == "ambiguous", row["issues"]
    assert len(row["candidates"]) == 2
    ambiguity = next(i for i in row["issues"] if i["code"] == "ambiguous_athlete_name")
    assert ambiguity["severity"] == "warning"
    assert preview.json()["canConfirm"] is False

    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{preview.json()['importId']}/conferma",
        headers=headers,
        json={"resolutions": [{"rowNumber": row["rowNumber"], "athleteId": str(first.id)}]},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 1
    owned = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.league_id == UUID(league_id),
            FantasyRosterSlot.athlete_id == first.id,
        )
    )
    assert owned is not None


def test_csv_matches_names_with_double_spaces_accents_and_turkish_i(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA emulatore 18/11: "J.  McGinn" (doppio spazio nel listone) ed
    "E. İlkhan" (İ turca) risultavano `athlete_not_found`."""
    token, _ = _register_and_login(client, "csv.names.unicode@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Nomi")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    tag = random.randint(100_000, 999_999)
    spaced = _seed_athlete(
        db_session, random.randint(100_000_000, 2_000_000_000), f"J.  McGinnQa{tag}"
    )
    turkish = _seed_athlete(
        db_session, random.randint(100_000_000, 2_000_000_000), f"E. İlkhanQa{tag}"
    )
    accented = _seed_athlete(
        db_session, random.randint(100_000_000, 2_000_000_000), f"A. DembéléQa{tag}"
    )
    csv_body = (
        "squadra,provider_id,nome,crediti\n"
        f"{team_name},,J. McGinnQa{tag},1\n"
        f"{team_name},,E. İlkhanQa{tag},1\n"
        f"{team_name},,A. DembeleQa{tag},1\n"
    ).encode()
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=headers,
        files={"file": ("rose.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert [row["athleteId"] for row in rows] == [
        str(spaced.id),
        str(turkish.id),
        str(accented.id),
    ], [row["issues"] for row in rows]


def _random_provider_id() -> int:
    return random.randint(100_000_000, 2_000_000_000)


def _seed_catalog_only_athlete(db_session: Session, name: str) -> Athlete:
    """Calciatore del catalogo senza ruolo in nessun listone."""
    athlete = Athlete(provider_id=_random_provider_id(), canonical_name=name)
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _seed_athlete_outside_league_competitions(db_session: Session, name: str) -> Athlete:
    """Calciatore nel listone 2026 ma di un club che gioca in un campionato fuori dalla lega."""
    provider_id = _random_provider_id()
    competition = Competition(
        provider_id=provider_id, name=f"Campionato Escluso {provider_id}", country="XX"
    )
    club = Club(provider_id=provider_id, name=f"Club Escluso {provider_id}")
    db_session.add_all([competition, club])
    db_session.flush()
    season = SportSeason(competition_id=competition.id, year=2026)
    db_session.add(season)
    db_session.flush()
    db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=2026,
            role=FantasyRole.A,
            mapping_version="v1.0.0",
            provider_position_raw="A",
            club_id=club.id,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def test_csv_name_search_is_limited_to_the_league_listone(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19/11: "A. Bamba", "A. Buksa" e "A. Cissè", unici nel listone della lega,
    risultavano `ambiguous` con candidati presi da tutto il catalogo; sceglierne uno
    fuori listone faceva fallire la conferma con `role_unresolved`."""
    token, _ = _register_and_login(client, "csv.names.listone@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Listone")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    tag = random.randint(100_000, 999_999)
    bamba = _seed_athlete(db_session, _random_provider_id(), f"A. Bamba{tag}")
    buksa = _seed_athlete(db_session, _random_provider_id(), f"A. Buksa{tag}")
    cisse = _seed_athlete(db_session, _random_provider_id(), f"A. Cissè{tag}")
    kone = _seed_athlete(db_session, _random_provider_id(), f"K. Koné{tag}")
    # Omonimi fuori dal listone della lega: senza ruolo, di un'altra stagione o di un
    # club che gioca in un campionato che la lega non ha scelto.
    _seed_catalog_only_athlete(db_session, f"A. Bamba{tag}")
    _seed_athlete(db_session, _random_provider_id(), f"A. Bamba{tag}", season_year=2025)
    _seed_athlete_outside_league_competitions(db_session, f"A. Bamba{tag}")
    _seed_catalog_only_athlete(db_session, f"A. Buksa{tag}")
    _seed_athlete_outside_league_competitions(db_session, f"A. Cissè{tag}")
    # "K. Kone" senza accento passa dal confronto in Python (stessa stagione, altro campionato).
    _seed_athlete_outside_league_competitions(db_session, f"K. Koné{tag}")
    _seed_catalog_only_athlete(db_session, f"Z. Fuori{tag}")

    url = f"/leagues/{league_id}/amministrazione/import-csv/anteprima-testo"
    csv_text = (
        "squadra,provider_id,nome,crediti\n"
        f"{team_name},,A. Bamba{tag},1\n"
        f"{team_name},,A. Buksa{tag},1\n"
        f"{team_name},,A. Cissè{tag},1\n"
        f"{team_name},,K. Kone{tag},1\n"
    )
    preview = client.post(url, headers=headers, json={"csvText": csv_text})
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert [row["status"] for row in rows] == ["ok"] * 4, [
        (row["issues"], row["candidates"]) for row in rows
    ]
    assert [row["athleteId"] for row in rows] == [
        str(bamba.id),
        str(buksa.id),
        str(cisse.id),
        str(kone.id),
    ]
    assert preview.json()["canConfirm"] is True

    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{preview.json()['importId']}/conferma",
        headers=headers,
        json={"resolutions": []},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 4

    # Un nome che esiste solo fuori dal listone non si trova più (prima era
    # `athlete_not_on_listone` su un calciatore che la conferma rifiutava).
    outside = client.post(
        url,
        headers=headers,
        json={"csvText": f"squadra,provider_id,nome,crediti\n{team_name},,Z. Fuori{tag},1\n"},
    )
    assert outside.status_code == 200, outside.text
    outside_row = outside.json()["rows"][0]
    assert outside_row["athleteId"] is None
    assert [issue["code"] for issue in outside_row["issues"]] == ["athlete_not_found"]


def _seed_athlete_at_club(
    db_session: Session,
    name: str,
    *,
    competition_id: str,
    club_name: str,
    role: FantasyRole,
) -> Athlete:
    """Calciatore del listone 2026 di un club che gioca in un campionato della lega."""
    provider_id = _random_provider_id()
    season = db_session.scalar(
        select(SportSeason).where(
            SportSeason.competition_id == UUID(competition_id), SportSeason.year == 2026
        )
    )
    if season is None:
        season = SportSeason(competition_id=UUID(competition_id), year=2026)
        db_session.add(season)
        db_session.flush()
    club = Club(provider_id=provider_id, name=club_name)
    db_session.add(club)
    db_session.flush()
    db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
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
            club_id=club.id,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _competition_name(db_session: Session, competition_id: str) -> str:
    competition = db_session.get(Competition, UUID(competition_id))
    assert competition is not None
    return competition.name


def test_csv_homonym_written_without_accent_is_ambiguous_with_role_and_club(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19-20/11: "toni fernandez" finiva in silenzio su Toni Fernández del
    Barcelona, mentre nel listone c'è anche il Toni Fernández del Venezia. La
    ricerca SQL "come scritto" trovava solo l'omonimo senza accento e il confronto
    senza accenti non partiva. Decisione: riga ambigua con ruolo, squadra e
    campionato di ogni candidato."""
    token, _ = _register_and_login(client, "csv.homonyms@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Omonimi")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    tag = random.randint(100_000, 999_999)
    barcelona = _seed_athlete_at_club(
        db_session,
        f"Toni Fernandez{tag}",
        competition_id=competition_ids[0],
        club_name=f"Barcelona {tag}",
        role=FantasyRole.C,
    )
    venezia = _seed_athlete_at_club(
        db_session,
        f"Toni Fernández{tag}",
        competition_id=competition_ids[1],
        club_name=f"Venezia {tag}",
        role=FantasyRole.A,
    )

    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima-testo",
        headers=headers,
        json={"csvText": f"squadra,provider_id,nome,crediti\n{team_name},,toni fernandez{tag},3\n"},
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    assert row["status"] == "ambiguous", (row["athleteName"], row["issues"])
    assert row["athleteId"] is None
    candidates = {candidate["athleteId"]: candidate for candidate in row["candidates"]}
    assert set(candidates) == {str(barcelona.id), str(venezia.id)}
    assert candidates[str(barcelona.id)]["role"] == "C"
    assert candidates[str(barcelona.id)]["clubName"] == f"Barcelona {tag}"
    assert candidates[str(barcelona.id)]["competitionName"] == _competition_name(
        db_session, competition_ids[0]
    )
    assert candidates[str(venezia.id)]["role"] == "A"
    assert candidates[str(venezia.id)]["clubName"] == f"Venezia {tag}"
    assert candidates[str(venezia.id)]["competitionName"] == _competition_name(
        db_session, competition_ids[1]
    )

    # Si conferma scegliendo il candidato giusto; ruolo e squadra restano nella
    # sessione salvata (la conferma la rilegge).
    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{preview.json()['importId']}/conferma",
        headers=headers,
        json={"resolutions": [{"rowNumber": row["rowNumber"], "athleteId": str(venezia.id)}]},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 1
    owned = db_session.scalar(
        select(FantasyRosterSlot.athlete_id).where(
            FantasyRosterSlot.league_id == UUID(league_id),
            FantasyRosterSlot.athlete_id.in_([barcelona.id, venezia.id]),
        )
    )
    assert owned == venezia.id


def test_csv_ambiguous_rows_are_not_counted_as_errors(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19-20/11: le righe ambigue finivano in `errorCount`. Sono avvisi da
    risolvere: `ambiguousCount` le conta, e la conferma senza scelta le rifiuta."""
    token, _ = _register_and_login(client, "csv.ambiguous.count@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Conteggi")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    surname = f"Gemello{random.randint(100_000, 999_999)}"
    _seed_athlete(db_session, _random_provider_id(), f"P. {surname}")
    _seed_athlete(db_session, _random_provider_id(), f"S. {surname}")
    unique = _seed_athlete(db_session, _random_provider_id(), f"U. Unico{surname}")
    url = f"/leagues/{league_id}/amministrazione/import-csv/anteprima-testo"

    preview = client.post(
        url,
        headers=headers,
        json={
            "csvText": (
                "squadra,provider_id,nome,crediti\n"
                f"{team_name},,{unique.canonical_name},2\n"
                f"{team_name},,{surname},3\n"
            )
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert [row["status"] for row in body["rows"]] == ["ok", "ambiguous"]
    assert body["errorCount"] == 0
    assert body["ambiguousCount"] == 1
    assert body["warningCount"] >= 1
    assert body["canConfirm"] is False

    blocked = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{body['importId']}/conferma",
        headers=headers,
        json={"resolutions": []},
    )
    assert blocked.status_code == 400, blocked.text
    assert blocked.json()["code"] == "import_has_ambiguities"
    assert (
        db_session.scalar(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.league_id == UUID(league_id),
                FantasyRosterSlot.athlete_id == unique.id,
            )
        )
        is None
    )

    # Con un errore vero l'errore si conta, l'ambiguità resta a parte.
    with_error = client.post(
        url,
        headers=headers,
        json={
            "csvText": (
                "squadra,provider_id,nome,crediti\n"
                f"{team_name},,{surname},3\n"
                f"{team_name},,Inesistente{surname},1\n"
            )
        },
    )
    assert with_error.status_code == 200, with_error.text
    assert with_error.json()["errorCount"] == 1
    assert with_error.json()["ambiguousCount"] == 1


def test_csv_matches_dotless_turkish_i(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19-20/11: "A. Bayindir" non trovava "A. Bayındır" (ı turca senza punto)."""
    token, _ = _register_and_login(client, "csv.names.dotless@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega CSV Bayindir")
    headers = {"Authorization": f"Bearer {token}"}
    team_name = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["name"]
    tag = random.randint(100_000, 999_999)
    keeper = _seed_athlete(db_session, _random_provider_id(), f"A. Bayındır{tag}")
    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima-testo",
        headers=headers,
        json={"csvText": f"squadra,provider_id,nome,crediti\n{team_name},,A. Bayindir{tag},1\n"},
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    assert row["status"] == "ok", row["issues"]
    assert row["athleteId"] == str(keeper.id)


def test_excel_ambiguous_name_is_kept_to_choose_instead_of_ignored(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Decisione 19-20/11: anche nell'Excel (web e app) il nome di più calciatori
    non si ignora più: la riga resta da scegliere, con ruolo e squadra dei
    candidati. Il nome che non esiste resta ignorato."""
    from openpyxl import Workbook

    token, _ = _register_and_login(client, "xlsx.homonyms@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Excel Omonimi")
    headers = {"Authorization": f"Bearer {token}"}
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=headers).json()["id"]
    tag = random.randint(100_000, 999_999)
    first = _seed_athlete_at_club(
        db_session,
        f"Toni Fernández{tag}",
        competition_id=competition_ids[0],
        club_name=f"Barcelona {tag}",
        role=FantasyRole.C,
    )
    _seed_athlete_at_club(
        db_session,
        f"Toni Fernández{tag}",
        competition_id=competition_ids[1],
        club_name=f"Venezia {tag}",
        role=FantasyRole.A,
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Calciatore", "Crediti"])
    sheet.append([f"toni fernandez{tag}", 3])
    sheet.append([f"Nessuno{tag}", 1])
    buffer = io.BytesIO()
    workbook.save(buffer)

    preview = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/anteprima",
        headers=headers,
        params={"teamId": team_id},
        files={
            "file": (
                "rosa.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    ambiguous, missing = body["rows"]
    assert ambiguous["status"] == "ambiguous", ambiguous["issues"]
    assert sorted(candidate["clubName"] for candidate in ambiguous["candidates"]) == [
        f"Barcelona {tag}",
        f"Venezia {tag}",
    ]
    assert all(candidate["role"] for candidate in ambiguous["candidates"])
    assert missing["status"] == "skipped"
    assert body["errorCount"] == 0
    assert body["ambiguousCount"] == 1

    confirm = client.post(
        f"/leagues/{league_id}/amministrazione/import-csv/{body['importId']}/conferma",
        headers=headers,
        json={"resolutions": [{"rowNumber": ambiguous["rowNumber"], "athleteId": str(first.id)}]},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["assignedCount"] == 1
