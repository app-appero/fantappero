# ruff: noqa: F811
"""Un portiere in panchina al posto dell'attaccante (Rosario, 20/11, «lega demo»).

«Fabio Trotta ha una formazione con un portiere in panchina al posto dell'attaccante e non si può
sostituire.» Quando un calciatore dei primi 10 della panchina usciva dalla rosa, la pulizia
(``fantasy_lineups.departures``) ricompattava la panchina e al 10° posto saliva il primo della
tribuna, qualunque ruolo avesse. Con la tribuna in ordine P→D→C→A, uscito un attaccante, saliva un
portiere: 2 P e 2 A nei primi 10, la quota 1P·3D·3C·3A rotta e ogni salvataggio rifiutato
(``bench_roles_invalid``). Lo stesso alla regola di inizio turno e nella pulizia in lettura di GET
formazione. Ora al posto lasciato sale il primo della tribuna con il ruolo che manca.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_lineup_departure_purge import (
    _bench,
    _draft,
    _new_athlete_like,
    _round_clubs,
    _slot_index,
    _stored,
    _submission,
)
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_payload,
    _occupied_slots,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import FantasyRole, LeagueAuditAction, LineupSlotKind
from fantasy_lineups.models import LineupPlayer, TacticalMove
from fantasy_lineups.turn_start import settle_lineups_at_turn_start, turn_start_messages
from fantasy_teams.models import FantasyRosterSlot
from fantasy_turns.models import FantasyRound
from leagues.models.league_audit_event import LeagueAuditEvent
from sports_data.catalog.models import Club, CompetitionSeasonClub
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

BENCH_ROLES_INVALID = "bench_roles_invalid"


def _url(setup: dict) -> str:
    return f"/leagues/{setup['league_id']}/turni/{setup['round_id']}/formazione"


def _save(client: TestClient, setup: dict, payload: dict) -> None:
    saved = client.put(_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()


def _payload(client: TestClient, db_session: Session, setup: dict) -> dict:
    """4-3-3 salvato: panchina P2 D5-D7 C4-C6 A4-A6, tribuna P3 D8-D11 C7-C11 A7-A10."""
    payload = _lineup_payload(_occupied_slots(db_session, setup["team_a"]), setup["role_of"])
    roles = setup["roles_a"]
    p, d, c, a = (roles[role] for role in FantasyRole)
    assert [UUID(item) for item in payload["benchAthleteIds"]] == [
        p[1],
        *d[4:7],
        *c[3:6],
        *a[3:6],
        p[2],
        *d[7:],
        *c[6:],
        *a[6:],
    ]
    _save(client, setup, payload)
    return payload


def _expected_bench(setup: dict) -> list[UUID]:
    """Uscito A4 (8° in panchina): A5 e A6 salgono di un posto, A7 (primo attaccante della
    tribuna) prende il 10° posto, P3 resta primo della tribuna."""
    roles = setup["roles_a"]
    p, d, c, a = (roles[role] for role in FantasyRole)
    return [p[1], *d[4:7], *c[3:6], a[4], a[5], a[6], p[2], *d[7:], *c[6:], *a[7:]]


def _bench_issues(body: dict) -> list[dict]:
    return [issue for issue in body["issues"] if issue["code"] == BENCH_ROLES_INVALID]


def test_forward_leaving_the_bench_is_replaced_by_the_first_forward_of_the_tribuna(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="bq.purge", id_offset=9_710_000
    )
    team_a, token = setup["team_a"], setup["token_a"]
    payload = _payload(client, db_session, setup)
    draft = client.put(f"{_url(setup)}/bozza", headers=_headers(token), json=payload)
    assert draft.status_code == 200, draft.json()
    before = _submission(db_session, setup["round_id"], team_a)
    revision, submitted_at = before.revision, before.submitted_at
    departed = setup["roles_a"][FantasyRole.A][3]  # A4, 8° in panchina

    # L'admin sostituisce A4 con un nuovo attaccante (la rosa resta completa e convalidata).
    newcomer = _new_athlete_like(db_session, departed, provider_id=9_719_999)
    response = client.put(
        f"/leagues/{setup['league_id']}/amministrazione/squadre/{team_a}/slot/"
        f"{_slot_index(db_session, team_a, departed)}",
        headers=_headers(token),
        json={"athleteId": str(newcomer), "purchaseCredits": 1},
    )
    assert response.status_code == 200, response.json()

    # Nel DB: al 10° posto l'attaccante A7, non il portiere P3.
    stored = _stored(db_session, setup["round_id"], team_a)
    assert [athlete_id for _, athlete_id in _bench(stored)] == _expected_bench(setup)
    draft_row = _draft(db_session, setup["round_id"], team_a)
    assert draft_row.bench_athlete_ids == [str(item) for item in _expected_bench(setup)]
    # Pulizia di sistema: nessuna nuova revisione, nessuna mossa.
    after = _submission(db_session, setup["round_id"], team_a)
    assert (after.revision, after.submitted_at) == (revision, submitted_at)
    assert not db_session.scalars(
        select(TacticalMove).where(TacticalMove.submission_id == after.id)
    ).all()
    audit = db_session.scalars(
        select(LeagueAuditEvent.details).where(
            LeagueAuditEvent.league_id == UUID(setup["league_id"]),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
            LeagueAuditEvent.details["source"].astext == "roster_departure",
        )
    ).one()
    a7, p3 = setup["roles_a"][FantasyRole.A][6], setup["roles_a"][FantasyRole.P][2]
    assert [(item["promotedId"], item["demotedId"]) for item in audit["benchRepair"]] == [
        (str(a7), str(p3))
    ]
    assert audit["tacticalMoveConsumed"] is False

    # La formazione si apre senza errori (il nuovo arrivato in coda, come lo mettono web e app)
    # e si salva così com'è.
    body = client.get(_url(setup), headers=_headers(token)).json()
    assert _bench_issues(body) == []
    shown = [player["athleteId"] for player in body["lineup"]["bench"]]
    assert shown == [*(str(item) for item in _expected_bench(setup)), str(newcomer)]
    assert body["draft"]["benchAthleteIds"] == shown[:-1]
    _save(
        client,
        setup,
        {
            "module": body["lineup"]["module"],
            "starterAthleteIds": [player["athleteId"] for player in body["lineup"]["starters"]],
            "benchAthleteIds": shown,
        },
    )
    assert client.get(_url(setup), headers=_headers(token)).json()["tacticalMovesUsed"] == 0


def _legacy_drop(db_session: Session, setup: dict, athlete_id: UUID) -> UUID:
    """Uscita dalla rosa scritta direttamente nel DB, senza la pulizia all'uscita (formazioni
    sporche di prima della correzione): al suo slot un nuovo attaccante."""
    newcomer = _new_athlete_like(db_session, athlete_id, provider_id=9_729_999)
    slot = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(setup["team_a"]),
            FantasyRosterSlot.athlete_id == athlete_id,
        )
    ).one()
    slot.athlete_id = newcomer
    db_session.commit()
    setup["role_of"][newcomer] = FantasyRole.A
    return newcomer


def test_dirty_lineup_read_and_turn_start_keep_the_forward_quota(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="bq.start", id_offset=9_720_000
    )
    team_a, token = setup["team_a"], setup["token_a"]
    _payload(client, db_session, setup)
    departed = setup["roles_a"][FantasyRole.A][3]  # A4
    newcomer = _legacy_drop(db_session, setup, departed)

    # GET formazione: la pulizia in lettura toglie A4 e mostra la panchina già in regola.
    body = client.get(_url(setup), headers=_headers(token)).json()
    assert _bench_issues(body) == []
    assert [player["athleteId"] for player in body["lineup"]["bench"]] == [
        *(str(item) for item in _expected_bench(setup)),
        str(newcomer),
    ]

    # Primo blocco: solo la partita del primo campionato è entro il margine; le altre tra 2 giorni.
    fixtures = sorted(_round_clubs(db_session, setup["round_id"]), key=lambda row: row.provider_id)
    soon = datetime.now(UTC) + timedelta(minutes=5)
    fantasy_round = db_session.get(FantasyRound, UUID(setup["round_id"]))
    assert fantasy_round is not None
    fantasy_round.cutoff_at = soon
    for index, fixture in enumerate(fixtures):
        fixture.kickoff_at = soon if index == 0 else soon + timedelta(days=2)
    db_session.commit()
    locked_clubs = {fixtures[0].home_club_id, fixtures[0].away_club_id}

    result = settle_lineups_at_turn_start(db_session, fantasy_round=fantasy_round)
    db_session.commit()
    assert result.due and result.teams_changed == 1

    stored = _stored(db_session, setup["round_id"], team_a)
    stored_bench = [athlete_id for _, athlete_id in _bench(stored)]
    roles = setup["roles_a"]
    p, d, c, a = (roles[role] for role in FantasyRole)
    # Il 10° posto va al primo attaccante della tribuna con la partita non ancora iniziata.
    club_of = {
        row.athlete_id: row.club_id
        for row in db_session.scalars(
            select(RoleAssignment).where(RoleAssignment.athlete_id.in_(a))
        ).all()
    }
    first_free_forward = next(item for item in a[6:] if club_of[item] not in locked_clubs)
    assert stored_bench[:10] == [p[1], *d[4:7], *c[3:6], a[4], a[5], first_free_forward]
    assert stored_bench[10] == p[2]
    assert departed not in stored_bench
    audit = next(
        row
        for row in db_session.scalars(
            select(LeagueAuditEvent.details).where(
                LeagueAuditEvent.league_id == UUID(setup["league_id"]),
                LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
            )
        ).all()
        if row.get("source") == "turn_start_autofill"
    )
    assert [(item["promotedId"], item["demotedId"]) for item in audit["benchRepair"]] == [
        (str(first_free_forward), str(p[2]))
    ]
    names = {
        row.id: row.canonical_name
        for row in db_session.scalars(
            select(Athlete).where(Athlete.id.in_([first_free_forward, p[2]]))
        ).all()
    }
    assert any(
        f"{names[first_free_forward]} è salito in panchina al posto di {names[p[2]]}" in message
        for message in turn_start_messages(audit)
    )


# -- attaccanti senza partita, arrivati dopo l'ultimo salvataggio (Fabio, 20/11 16:50) ------


def _club_without_match(db_session: Session, setup: dict, *, provider_id: int) -> UUID:
    """Un club dello stesso campionato di un club della lega, senza partita nel turno."""
    template = _round_clubs(db_session, setup["round_id"])[0]
    club = Club(provider_id=provider_id, name=f"Club senza partita {provider_id}")
    db_session.add(club)
    db_session.flush()
    db_session.add(CompetitionSeasonClub(sport_season_id=template.sport_season_id, club_id=club.id))
    db_session.commit()
    return club.id


def _write_saved_bench(
    db_session: Session, setup: dict, bench_ids: list[UUID], *, drop: list[UUID]
) -> None:
    """La formazione salvata nel DB come su pilota: senza ``drop``, panchina ``bench_ids``."""
    submission = _submission(db_session, setup["round_id"], setup["team_a"])
    rows = {
        row.athlete_id: row
        for row in db_session.scalars(
            select(LineupPlayer).where(LineupPlayer.submission_id == submission.id)
        ).all()
    }
    for athlete_id in drop:
        db_session.delete(rows.pop(athlete_id))
    db_session.flush()
    bench_rows = [row for row in rows.values() if row.slot_kind == LineupSlotKind.BENCH]
    assert {row.athlete_id for row in bench_rows} == set(bench_ids)
    for offset, row in enumerate(bench_rows):
        row.sort_order = 1_000 + offset
    db_session.flush()
    for index, athlete_id in enumerate(bench_ids):
        rows[athlete_id].sort_order = index
    db_session.commit()


def test_forwards_without_a_match_do_not_block_the_lineup(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="bq.novote", id_offset=9_730_000
    )
    team_a, token = setup["team_a"], setup["token_a"]
    payload = _payload(client, db_session, setup)
    roles = setup["roles_a"]
    p, d, c, a = (roles[role] for role in FantasyRole)
    # A7-A10 giocano in un club senza partita nel turno: nessun voto possibile.
    no_match = _club_without_match(db_session, setup, provider_id=9_739_001)
    for assignment in db_session.scalars(
        select(RoleAssignment).where(RoleAssignment.athlete_id.in_(a[6:]))
    ).all():
        assignment.club_id = no_match
    # A4 esce dalla rosa (scritto nel DB, come i dati di pilota) e al suo posto arriva un
    # attaccante dello stesso club senza partita.
    newcomer = Athlete(provider_id=9_739_999, canonical_name="Nuovo attaccante senza partita")
    db_session.add(newcomer)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=newcomer.id,
            season_year=2026,
            role=FantasyRole.A,
            mapping_version="v1.0.0",
            provider_position_raw="A",
            club_id=no_match,
        )
    )
    slot = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_a),
            FantasyRosterSlot.athlete_id == a[3],
        )
    ).one()
    slot.athlete_id = newcomer.id
    db_session.commit()
    # La formazione di Fabio come su pilota: senza A4, con P3 salito al 10° posto e nessun
    # attaccante in tribuna (A7-A10 non erano nella formazione salvata).
    dirty = [p[1], *d[4:7], *c[3:6], a[4], a[5], p[2], *d[7:], *c[6:]]
    _write_saved_bench(db_session, setup, dirty, drop=[a[3], *a[6:]])
    blocked_forwards = [*a[6:], newcomer.id]

    # 1. Web e app già installati ricevono una panchina con tutta la rosa e 3 attaccanti nei
    #    primi 10 (contati come li contano loro): non la rifiutano più da sé.
    body = client.get(_url(setup), headers=_headers(token)).json()
    shown = [UUID(player["athleteId"]) for player in body["lineup"]["bench"]]
    assert set(shown) == {*dirty, *blocked_forwards}
    assert shown[:9] == [p[1], *d[4:7], *c[3:6], a[4], a[5]]
    assert shown[9] in blocked_forwards
    assert shown[10] == p[2]
    assert _bench_issues(body) == []
    roster_rows = {row["athleteId"]: row for row in body["roster"]}
    assert all(roster_rows[str(item)]["selectionBlocked"] for item in blocked_forwards)

    # 2. Il server accetta anche la panchina di prima, con il portiere al 10° posto e gli
    #    attaccanti senza partita in coda: chi non prende il voto non alza la quota.
    response = client.put(
        _url(setup),
        headers=_headers(token),
        json={
            "module": payload["module"],
            "starterAthleteIds": payload["starterAthleteIds"],
            "benchAthleteIds": [str(item) for item in (*dirty, *blocked_forwards)],
        },
    )
    assert response.status_code == 200, response.json()
