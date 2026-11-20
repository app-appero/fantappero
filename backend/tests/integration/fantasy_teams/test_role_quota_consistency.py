# ruff: noqa: F811
"""Quote di ruolo: stessi ruoli all'assegnazione e nella valutazione, stato unico (QA 20/11).

Notte 19-20/11, lega QA-PREP-PARI su dev: qa-04 con 11 A su 10 e qa-08 con 12 D su 11, ma
``compositionStatus: validated`` in ``GET /squadre`` e ``invalid`` nella vista admin della
squadra, nessuno slot segnato in esubero. Tre cause:

1. il controllo di quota all'assegnazione risolveva i ruoli solo con il listone della stagione
   corrente, la valutazione della rosa anche con le stagioni precedenti e la posizione nel club:
   un attaccante uscito dal listone non contava e ne entrava uno in più;
2. override di lega e aggiornamento del listone cambiavano i ruoli senza ricalcolare la rosa;
3. ``/squadre`` leggeva lo stato salvato, ``/rosa`` e la vista admin lo ricalcolavano.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_payload,
    _lineup_url,
    _occupied_slots,
    _register_and_login,
    _trade,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import FantasyRole, LeagueState, RosterCompositionStatus
from fantasy_teams.composition_service import (
    resync_team_compositions,
    sync_team_composition_status,
)
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam, RosterOwnershipInterval
from fantasy_turns.models import FantasyRoundFixture
from leagues.models.league import League
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

#: Slot di `_fill_full_roster`: P 0-2, D 3-13, C 14-24, A 25-34.
FIRST_MIDFIELDER_SLOT = 14
FIRST_FORWARD_SLOT = 25
LAST_FORWARD_SLOT = 34


# --- helper -----------------------------------------------------------------------------------


def _new_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    created = client.post(
        "/leagues",
        headers=_headers(token),
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201, created.json()
    return created.json()["id"]


def _listone_athlete(
    db_session: Session, provider_id: int, name: str, role: FantasyRole
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
    return athlete


def _assign(client: TestClient, token: str, league_id: str, team_id: str, slot: int, athlete):
    return client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot}",
        headers=_headers(token),
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )


def _assignment(db_session: Session, athlete_id: UUID) -> RoleAssignment:
    return db_session.scalars(
        select(RoleAssignment).where(RoleAssignment.athlete_id == athlete_id)
    ).one()


def _slot(db_session: Session, team_id: str, slot_index: int) -> FantasyRosterSlot:
    db_session.expire_all()
    return db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == slot_index,
        )
    ).one()


def _flagged(db_session: Session, team_id: str) -> list[tuple[int, UUID | None]]:
    return sorted(
        (slot.slot_index, slot.athlete_id)
        for slot in _occupied_slots(db_session, team_id)
        if slot.exceeds_role_quota
    )


def _stored_status(db_session: Session, team_id: str) -> RosterCompositionStatus:
    db_session.expire_all()
    team = db_session.get(FantasyTeam, UUID(team_id))
    assert team is not None
    return team.composition_status


def _arrivals_with_newest(db_session: Session, setup: dict, newest_slot: int) -> None:
    """Possessi attivi per tutta la rosa di A: in ordine di slot, ``newest_slot`` per ultimo."""
    base = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    for slot in _occupied_slots(db_session, setup["team_a"]):
        acquired = (
            base + timedelta(days=10)
            if slot.slot_index == newest_slot
            else base + timedelta(minutes=slot.slot_index)
        )
        db_session.add(
            RosterOwnershipInterval(
                league_id=UUID(setup["league_id"]),
                fantasy_team_id=UUID(setup["team_a"]),
                athlete_id=slot.athlete_id,
                slot_index=slot.slot_index,
                purchase_credits=1,
                acquired_at=acquired,
            )
        )
    db_session.commit()


def _three_views(client: TestClient, setup: dict) -> dict[str, object]:
    """Stato della squadra A in `/squadre` (visto da B), `/rosa` e vista admin."""
    league_id, team_id = setup["league_id"], setup["team_a"]
    listed = client.get(f"/leagues/{league_id}/squadre", headers=_headers(setup["token_b"]))
    assert listed.status_code == 200, listed.json()
    rosa = client.get(f"/leagues/{league_id}/rosa", headers=_headers(setup["token_a"]))
    assert rosa.status_code == 200, rosa.json()
    admin = client.get(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}",
        headers=_headers(setup["token_a"]),
    )
    assert admin.status_code == 200, admin.json()
    return {
        "squadre": next(row for row in listed.json() if row["id"] == team_id)["compositionStatus"],
        "rosa": rosa.json()["compositionStatus"],
        "rosa_composition": rosa.json()["composition"]["status"],
        "admin": admin.json()["compositionStatus"],
        "admin_composition": admin.json()["composition"]["status"],
        "rosa_flags": sorted(
            slot["slotIndex"] for slot in rosa.json()["slots"] if slot["exceedsRoleQuota"]
        ),
    }


def _all(status: RosterCompositionStatus) -> dict[str, str]:
    return {
        key: status.value
        for key in ("squadre", "rosa", "rosa_composition", "admin", "admin_composition")
    }


def _statuses(views: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in views.items() if key != "rosa_flags"}


# --- 1. stessi ruoli all'assegnazione e nella valutazione ---------------------------------------


def test_eleventh_forward_is_refused_when_a_forward_has_only_an_older_season_role(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rq.fallback@example.com")
    league_id = _new_league(client, token, competition_ids, "Lega Quote Fallback")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_headers(token)).json()["id"]
    forwards = [
        _listone_athlete(db_session, 8_610_000 + index, f"RQ Attaccante {index + 1}", FantasyRole.A)
        for index in range(11)
    ]
    for slot, athlete in enumerate(forwards[:10]):
        assigned = _assign(client, token, league_id, team_id, slot, athlete)
        assert assigned.status_code == 200, assigned.json()

    # Il listone 2026 rigenerato non ha più il primo attaccante: resta solo il ruolo del 2025.
    _assignment(db_session, forwards[0].id).season_year = 2025
    db_session.commit()

    rosa = client.get(f"/leagues/{league_id}/rosa", headers=_headers(token))
    assert rosa.json()["composition"]["counts"]["A"] == 10

    # La valutazione lo conta tra gli attaccanti, quindi anche il controllo di quota.
    eleventh = _assign(client, token, league_id, team_id, 10, forwards[10])
    assert eleventh.status_code == 400, eleventh.json()
    assert eleventh.json()["code"] == "role_quota_exceeded"
    assert _slot(db_session, team_id, 10).athlete_id is None


def test_a_player_without_any_role_counts_against_the_incoming_role(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "rq.senzaruolo@example.com")
    league_id = _new_league(client, token, competition_ids, "Lega Quote Senza Ruolo")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_headers(token)).json()["id"]
    forwards = [
        _listone_athlete(db_session, 8_615_000 + index, f"RQ Punta {index + 1}", FantasyRole.A)
        for index in range(10)
    ]
    unknown = _listone_athlete(db_session, 8_615_100, "RQ Ruolo Ignoto", FantasyRole.D)
    keeper = _listone_athlete(db_session, 8_615_101, "RQ Portiere", FantasyRole.P)
    for slot, athlete in enumerate([*forwards[:9], unknown]):
        assigned = _assign(client, token, league_id, team_id, slot, athlete)
        assert assigned.status_code == 200, assigned.json()

    # Esce dal listone senza ruoli precedenti né posizione nel club: nessun ruolo risolvibile.
    db_session.delete(_assignment(db_session, unknown.id))
    db_session.commit()
    rosa = client.get(f"/leagues/{league_id}/rosa", headers=_headers(token)).json()
    assert rosa["compositionStatus"] == RosterCompositionStatus.INVALID.value
    assert "role_unresolved" in {issue["code"] for issue in rosa["composition"]["issues"]}

    # 9 attaccanti + 1 senza ruolo: un 10° attaccante potrebbe essere l'11°, si rifiuta.
    tenth = _assign(client, token, league_id, team_id, 10, forwards[9])
    assert tenth.status_code == 400, tenth.json()
    assert tenth.json()["code"] == "role_quota_exceeded"
    assert "RQ Ruolo Ignoto" in tenth.json()["message"]
    # Un portiere invece ci sta comunque (0 + 1 senza ruolo + 1 su 3).
    keeper_in = _assign(client, token, league_id, team_id, 10, keeper)
    assert keeper_in.status_code == 200, keeper_in.json()


def test_a_player_out_of_this_year_listone_is_traded_with_the_role_his_roster_counts(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rq.scambio", id_offset=8_625_000
    )
    # L'attaccante di A esce dal listone 2026 (resta il ruolo del 2025): la rosa di A lo conta
    # ancora tra gli attaccanti, e così anche lo scambio con un attaccante di B.
    leaving = setup["roles_a"][FantasyRole.A][0]
    arriving = setup["roles_b"][FantasyRole.A][0]
    _assignment(db_session, leaving).season_year = 2025
    db_session.commit()
    _trade(client, setup, offered=[leaving], requested=[arriving])

    for team_key in ("team_a", "team_b"):
        assert _flagged(db_session, setup[team_key]) == []
        assert _stored_status(db_session, setup[team_key]) == RosterCompositionStatus.VALIDATED
    rosa_b = client.get(f"/leagues/{setup['league_id']}/rosa", headers=_headers(setup["token_b"]))
    assert rosa_b.json()["composition"]["counts"] == {"P": 3, "D": 11, "C": 11, "A": 10}
    assert rosa_b.json()["compositionStatus"] == RosterCompositionStatus.VALIDATED.value


# --- 2. ricalcolo ai cambi di ruolo --------------------------------------------------------------


def test_league_role_override_recomputes_the_roster_and_every_view_agrees(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rq.override", id_offset=8_620_000
    )
    league = db_session.get(League, UUID(setup["league_id"]))
    assert league is not None
    league.state = LeagueState.AUCTION  # prima dell'avvio l'override vale subito
    db_session.commit()
    newest_forward_slot = 30
    _arrivals_with_newest(db_session, setup, newest_forward_slot)
    newest_forward = _slot(db_session, setup["team_a"], newest_forward_slot).athlete_id
    moved = _slot(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT).athlete_id
    assert _statuses(_three_views(client, setup)) == _all(RosterCompositionStatus.VALIDATED)

    override_url = f"/leagues/{setup['league_id']}/amministrazione/listone/{moved}/ruolo"
    response = client.put(override_url, headers=_headers(setup["token_a"]), json={"role": "A"})
    assert response.status_code == 200, response.json()

    # C 10, A 11: la rosa non è più valida e l'attaccante arrivato per ultimo è in esubero.
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.INVALID
    assert _flagged(db_session, setup["team_a"]) == [(newest_forward_slot, newest_forward)]
    views = _three_views(client, setup)
    assert _statuses(views) == _all(RosterCompositionStatus.INVALID)
    assert views["rosa_flags"] == [newest_forward_slot]

    # Tolto l'override si torna in quota: flag tolto e rosa di nuovo convalidata ovunque.
    cleared = client.delete(override_url, headers=_headers(setup["token_a"]))
    assert cleared.status_code == 200, cleared.json()
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.VALIDATED
    assert _flagged(db_session, setup["team_a"]) == []
    views = _three_views(client, setup)
    assert _statuses(views) == _all(RosterCompositionStatus.VALIDATED)
    assert views["rosa_flags"] == []


def test_listone_update_recomputes_the_rosters_of_every_league_of_the_season(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rq.listone", id_offset=8_650_000
    )
    concluded = _trade_league(
        client, db_session, competition_ids, prefix="rq.conclusa", id_offset=8_655_000
    )
    concluded_league = db_session.get(League, UUID(concluded["league_id"]))
    assert concluded_league is not None
    concluded_league.state = LeagueState.CONCLUDED
    db_session.commit()
    # Il listone aggiornato sposta un C di A tra gli attaccanti e uno della lega conclusa.
    moved = _slot(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT).athlete_id
    moved_concluded = _slot(db_session, concluded["team_a"], FIRST_MIDFIELDER_SLOT).athlete_id
    assert moved is not None and moved_concluded is not None
    for athlete_id in (moved, moved_concluded):
        _assignment(db_session, athlete_id).role = FantasyRole.A
    db_session.commit()

    refreshed = resync_team_compositions(
        db_session, athlete_ids={moved, moved_concluded}, season_year=2026
    )
    db_session.commit()

    assert refreshed == 1
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.INVALID
    excess = _slot(db_session, setup["team_a"], LAST_FORWARD_SLOT).athlete_id
    assert _flagged(db_session, setup["team_a"]) == [(LAST_FORWARD_SLOT, excess)]
    assert _stored_status(db_session, setup["team_b"]) == RosterCompositionStatus.VALIDATED
    # La lega conclusa non si tocca.
    assert _stored_status(db_session, concluded["team_a"]) == RosterCompositionStatus.VALIDATED
    assert _flagged(db_session, concluded["team_a"]) == []


# --- 3. nessun "validated" scaduto ---------------------------------------------------------------


def test_legacy_validated_roster_over_quota_is_corrected_by_the_roster_reads(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rq.legacy", id_offset=8_630_000
    )
    # Come qa-04 su dev: il listone ha spostato un C tra gli attaccanti (11 su 10) e lo stato
    # salvato è rimasto "validated", senza nessuno slot segnato.
    moved = _slot(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT).athlete_id
    assert moved is not None
    _assignment(db_session, moved).role = FantasyRole.A
    setup["role_of"][moved] = FantasyRole.A
    db_session.commit()
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.VALIDATED

    # La formazione non corregge lo stato salvato (turno in corso: vedi il test sulla
    # riclassificazione dopo il calcio d'inizio).
    context = client.get(_lineup_url(setup), headers=_headers(setup["token_a"]))
    assert context.status_code == 200, context.json()
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.VALIDATED

    # L'elenco squadre, letto da un altro partecipante, la corregge già: non più convalidata,
    # esubero segnato (nessun possesso registrato: lo slot più alto del ruolo).
    listed = client.get(
        f"/leagues/{setup['league_id']}/squadre", headers=_headers(setup["token_b"])
    )
    assert listed.status_code == 200, listed.json()
    by_id = {row["id"]: row["compositionStatus"] for row in listed.json()}
    assert by_id[setup["team_a"]] == RosterCompositionStatus.INVALID.value
    assert by_id[setup["team_b"]] == RosterCompositionStatus.VALIDATED.value
    excess = _slot(db_session, setup["team_a"], LAST_FORWARD_SLOT).athlete_id
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.INVALID
    assert _flagged(db_session, setup["team_a"]) == [(LAST_FORWARD_SLOT, excess)]
    views = _three_views(client, setup)
    assert _statuses(views) == _all(RosterCompositionStatus.INVALID)
    assert views["rosa_flags"] == [LAST_FORWARD_SLOT]

    # Senza il segnato la formazione si salva; con lui no.
    slots = _occupied_slots(db_session, setup["team_a"])
    saved = client.put(
        _lineup_url(setup),
        headers=_headers(setup["token_a"]),
        json=_lineup_payload(slots, setup["role_of"]),
    )
    assert saved.status_code == 200, saved.json()


def test_legacy_validated_roster_is_corrected_in_the_admin_team_view_too(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rq.admin", id_offset=8_635_000
    )
    # Come qa-08: 12 D su 11 (un C diventato D) con lo stato salvato "validated".
    moved = _slot(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT).athlete_id
    assert moved is not None
    _assignment(db_session, moved).role = FantasyRole.D
    db_session.commit()

    admin = client.get(
        f"/leagues/{setup['league_id']}/amministrazione/squadre/{setup['team_a']}",
        headers=_headers(setup["token_a"]),
    )
    assert admin.status_code == 200, admin.json()
    assert admin.json()["compositionStatus"] == RosterCompositionStatus.INVALID.value
    # Il difensore nello slot più alto è segnato; tra i D lui è il più alto (slot 14).
    assert _flagged(db_session, setup["team_a"]) == [(FIRST_MIDFIELDER_SLOT, moved)]
    listed = client.get(
        f"/leagues/{setup['league_id']}/squadre", headers=_headers(setup["token_b"])
    )
    by_id = {row["id"]: row["compositionStatus"] for row in listed.json()}
    assert by_id[setup["team_a"]] == RosterCompositionStatus.INVALID.value


# --- turno in corso: chi è già in campo resta schierabile -------------------------------------


def test_starter_flagged_after_kickoff_stays_in_the_lineup_of_the_current_turn(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Versione realistica (3 campionati) di `test_saving_is_not_blocked_by_a_role_reclassified_
    after_kickoff`: qui il ricalcolo della rosa avviene davvero e segna proprio il titolare
    riclassificato, già in campo e bloccato. Per questo turno resta dov'è e la formazione si
    salva; dal prossimo turno, se è ancora in esubero, non è schierabile."""
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rq.bloccato", id_offset=8_640_000
    )
    token = setup["token_a"]
    payload = _lineup_payload(_occupied_slots(db_session, setup["team_a"]), setup["role_of"])
    locked_forward = _slot(db_session, setup["team_a"], FIRST_FORWARD_SLOT).athlete_id
    assert str(locked_forward) in payload["starterAthleteIds"]
    saved = client.put(_lineup_url(setup), headers=_headers(token), json=payload)
    assert saved.status_code == 200, saved.json()

    # La sua partita inizia.
    club_id = _assignment(db_session, locked_forward).club_id
    fixture = db_session.scalars(
        select(Fixture)
        .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
        .where(
            FantasyRoundFixture.round_id == UUID(setup["round_id"]),
            (Fixture.home_club_id == club_id) | (Fixture.away_club_id == club_id),
        )
    ).one()
    fixture.kickoff_at = datetime.now(UTC) - timedelta(minutes=30)
    fixture.status_short = "1H"
    db_session.commit()

    # Dopo il calcio d'inizio il listone lo fa centrocampista (C 12 su 11) e il ricalcolo della
    # rosa segna in esubero il C nello slot più alto: proprio lui.
    _assignment(db_session, locked_forward).role = FantasyRole.C
    db_session.commit()
    team = db_session.get(FantasyTeam, UUID(setup["team_a"]))
    league = db_session.get(League, UUID(setup["league_id"]))
    assert team is not None and league is not None
    sync_team_composition_status(db_session, team, league=league)
    db_session.commit()
    assert _flagged(db_session, setup["team_a"]) == [(FIRST_FORWARD_SLOT, locked_forward)]

    # Ri-salvare la stessa formazione funziona, anche come bozza, e la pagina formazione non lo
    # dà in esubero: è in campo con il ruolo con cui è stato schierato.
    again = client.put(_lineup_url(setup), headers=_headers(token), json=payload)
    assert again.status_code == 200, again.json()
    draft = client.put(f"{_lineup_url(setup)}/bozza", headers=_headers(token), json=payload)
    assert draft.status_code == 200, draft.json()
    context = client.get(_lineup_url(setup), headers=_headers(token))
    assert context.status_code == 200, context.json()
    codes = {issue["code"] for issue in context.json()["issues"]}
    assert "athlete_exceeds_role_quota" not in codes
    starters = [row["athleteId"] for row in context.json()["lineup"]["starters"]]
    assert str(locked_forward) in starters
