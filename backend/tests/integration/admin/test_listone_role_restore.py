# ruff: noqa: F811
"""«Ripristina i ruoli cambiati da un aggiornamento» dal pannello operatore (pilota 22/11).

Il 21/11 su pilota «Aggiorna listone» ha cambiato ruoli già nelle rose (C→A, A→C): rose
complete e valide finite fuori quota, calendario non generabile. Il ruolo di prima si
ricostruisce dalle risposte del fornitore salvate in ``provider_snapshots`` prima dell'ora
indicata, con lo stesso mapping del listone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _register_and_login,
    _trade_league,
    competition_ids,
    db_session,
)
from tests.integration.fantasy_turns.test_fantasy_turns import _promote_to_operator

from database.enums import FantasyRole, LeagueAuditAction, RosterCompositionStatus
from fantasy_teams.composition_service import resync_team_compositions
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league_audit_event import LeagueAuditEvent
from sports_data.catalog.models import Club
from sports_data.listone.models import RoleAssignment
from sports_data.provider.envelope import parse_envelope
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.roster.models import Athlete

URL = "/admin/listone/ripristina-ruoli"
FIRST_MIDFIELDER_SLOT = 14


def _store_squad(
    db_session: Session,
    club: Club,
    players: list[tuple[Athlete, str]],
    *,
    fetched_at: datetime,
) -> None:
    payload: dict[str, Any] = {
        "errors": [],
        "get": "players/squads",
        "parameters": {"team": str(club.provider_id)},
        "paging": {"current": 1, "total": 1},
        "results": 1,
        "response": [
            {
                "team": {"id": club.provider_id, "name": club.name},
                "players": [
                    {"id": athlete.provider_id, "name": athlete.canonical_name, "position": pos}
                    for athlete, pos in players
                ],
            }
        ],
    }
    envelope = parse_envelope(payload, endpoint="/players/squads", http_status=200)
    store_provider_snapshot(db_session, envelope, fetched_at=fetched_at)


def _slot_athlete(db_session: Session, team_id: str, slot_index: int) -> Athlete:
    slot = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == slot_index,
        )
    ).one()
    athlete = db_session.get(Athlete, slot.athlete_id)
    assert athlete is not None
    return athlete


def _assignment(db_session: Session, athlete: Athlete) -> RoleAssignment:
    db_session.expire_all()
    return db_session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == athlete.id, RoleAssignment.season_year == 2026
        )
    ).one()


def _team(db_session: Session, team_id: str) -> FantasyTeam:
    db_session.expire_all()
    team = db_session.get(FantasyTeam, UUID(team_id))
    assert team is not None
    return team


def _flagged(db_session: Session, team_id: str) -> list[int]:
    db_session.expire_all()
    return sorted(
        slot.slot_index
        for slot in db_session.scalars(
            select(FantasyRosterSlot).where(FantasyRosterSlot.fantasy_team_id == UUID(team_id))
        ).all()
        if slot.exceeds_role_quota
    )


def _bad_refresh(db_session: Session, setup: dict) -> tuple[Athlete, Athlete, datetime]:
    """Un C della squadra A diventa A dopo l'ora indicata, come il 21/11."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=1)
    # Il database è condiviso dai test del modulo: le assegnazioni già presenti risalgono a
    # prima, così contano solo i cambi di questo test.
    old = now - timedelta(days=10)
    db_session.execute(update(RoleAssignment).values(created_at=old, updated_at=old))
    moved = _slot_athlete(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT)
    assignment = _assignment(db_session, moved)
    club = db_session.get(Club, assignment.club_id)
    assert club is not None
    # La rosa del club salvata prima dell'aggiornamento lo dava centrocampista; quella
    # dell'aggiornamento attaccante.
    _store_squad(db_session, club, [(moved, "Midfielder")], fetched_at=now - timedelta(hours=2))
    _store_squad(db_session, club, [(moved, "Attacker")], fetched_at=now)
    assignment.role = FantasyRole.A
    assignment.provider_position_raw = "Attacker"
    # Un difensore della squadra B già nel listone prima: nessuna risposta salvata lo elenca.
    unknown = _slot_athlete(db_session, setup["team_b"], 3)
    db_session.execute(
        update(RoleAssignment)
        .where(RoleAssignment.athlete_id == unknown.id)
        .values(created_at=now - timedelta(hours=3), updated_at=now)
    )
    db_session.commit()
    resync_team_compositions(db_session, athlete_ids={moved.id}, season_year=2026)
    db_session.commit()
    return moved, unknown, cutoff


def _body(cutoff: datetime, *, dry_run: bool, athlete_ids: list[str] | None = None) -> dict:
    body: dict[str, Any] = {"seasonYear": 2026, "before": cutoff.isoformat(), "dryRun": dry_run}
    if athlete_ids is not None:
        body["athleteIds"] = athlete_ids
    return body


def test_dry_run_lists_the_roles_reconstructed_from_snapshots_before_the_cutoff(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rr.anteprima", id_offset=8_710_000
    )
    moved, unknown, cutoff = _bad_refresh(db_session, setup)
    assert _team(db_session, setup["team_a"]).composition_status == RosterCompositionStatus.INVALID
    token, user_id = _register_and_login(client, "rr.anteprima.op@example.com")
    _promote_to_operator(db_session, user_id)

    response = client.post(URL, headers=_headers(token), json=_body(cutoff, dry_run=True))

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["dryRun"] is True
    entries = {entry["athleteId"]: entry for entry in data["entries"]}
    restored = entries[str(moved.id)]
    assert restored["currentRole"] == "A"
    assert restored["restoredRole"] == "C"
    assert restored["reconstructible"] is True
    assert restored["restoredPosition"] == "Midfielder"
    assert restored["restoredSource"] == "squads"
    assert restored["inRosters"] == ["Lega rr.anteprima"]
    assert restored["name"] == moved.canonical_name
    missing = entries[str(unknown.id)]
    assert missing["reconstructible"] is False
    assert missing["restoredRole"] is None
    assert missing["currentRole"] == "D"
    assert data["counts"] == {
        "toRestore": 1,
        "notReconstructible": 1,
        "restored": 0,
        "rostersOverQuotaNow": 1,
        "rostersOverQuotaAfter": 0,
        "rostersResynced": 0,
    }
    # L'anteprima non scrive nulla.
    assert _assignment(db_session, moved).role == FantasyRole.A
    assert _team(db_session, setup["team_a"]).composition_status == RosterCompositionStatus.INVALID

    # Con un'ora precedente a ogni risposta salvata niente è ricostruibile: nessun ripristino.
    early = client.post(
        URL,
        headers=_headers(token),
        json=_body(cutoff - timedelta(hours=5), dry_run=True),
    )
    assert early.status_code == 200
    assert early.json()["counts"]["toRestore"] == 0


def test_apply_restores_the_roles_resyncs_the_rosters_and_is_idempotent(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rr.ripristino", id_offset=8_720_000
    )
    moved, unknown, cutoff = _bad_refresh(db_session, setup)
    assert _team(db_session, setup["team_a"]).composition_status == RosterCompositionStatus.INVALID
    assert _flagged(db_session, setup["team_a"]) != []
    token, user_id = _register_and_login(client, "rr.ripristino.op@example.com")
    _promote_to_operator(db_session, user_id)

    preview = client.post(URL, headers=_headers(token), json=_body(cutoff, dry_run=True)).json()
    to_apply = [entry["athleteId"] for entry in preview["entries"] if entry["reconstructible"]]
    applied = client.post(
        URL, headers=_headers(token), json=_body(cutoff, dry_run=False, athlete_ids=to_apply)
    )

    assert applied.status_code == 200, applied.json()
    counts = applied.json()["counts"]
    assert counts["restored"] == 1
    assert counts["rostersResynced"] >= 1
    restored = _assignment(db_session, moved)
    assert restored.role == FantasyRole.C
    assert restored.provider_position_raw == "Midfielder"
    # Il non ricostruibile resta com'è.
    assert _assignment(db_session, unknown).role == FantasyRole.D
    team_a = _team(db_session, setup["team_a"])
    assert team_a.composition_status == RosterCompositionStatus.VALIDATED
    assert _flagged(db_session, setup["team_a"]) == []
    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_LISTONE_REFRESHED,
            LeagueAuditEvent.league_id.is_(None),
            LeagueAuditEvent.actor_id == user_id,
        )
    ).all()
    assert len(audit) == 1
    assert audit[0].details is not None
    assert audit[0].details["operation"] == "listone_roles_restored"
    assert audit[0].details["changes"] == [{"athleteId": str(moved.id), "from": "A", "to": "C"}]

    # Idempotente: una seconda volta non trova più nulla da ripristinare.
    again = client.post(URL, headers=_headers(token), json=_body(cutoff, dry_run=False))
    assert again.status_code == 200
    assert again.json()["counts"]["toRestore"] == 0
    assert again.json()["counts"]["restored"] == 0
    assert _assignment(db_session, moved).role == FantasyRole.C
    assert (
        _team(db_session, setup["team_a"]).composition_status == RosterCompositionStatus.VALIDATED
    )


def test_restore_is_forbidden_to_a_league_admin_and_to_a_normal_user(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rr.vietato", id_offset=8_730_000
    )
    moved, _unknown, cutoff = _bad_refresh(db_session, setup)
    # token_a è il proprietario (admin) della lega, token_b un partecipante.
    for token in (setup["token_a"], setup["token_b"]):
        for dry_run in (True, False):
            response = client.post(
                URL, headers=_headers(token), json=_body(cutoff, dry_run=dry_run)
            )
            assert response.status_code == 403
    assert _assignment(db_session, moved).role == FantasyRole.A
