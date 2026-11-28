# ruff: noqa: F811
"""All'inizio del turno la formazione si sistema da sola (decisione di Rosario del 19/11).

Al primo blocco del turno ogni formazione salvata perde chi non è più in rosa e copre i posti
vuoti tra i titolari: entra il primo panchinaro dello stesso ruolo e al suo posto in panchina sale
il primo della tribuna dello stesso ruolo. Senza nessuno in panchina entra direttamente il primo
della tribuna; senza nessuno di quel ruolo il posto resta vuoto. Nessuna mossa tattica, nessuna
nuova revisione, un evento di audit ``turn_start_autofill``; i turni omologati o già calcolati
non si toccano. Prima di questa regola la squadra giocava in 10 (le sostituzioni automatiche
coprono solo i titolari senza voto) e una formazione rimasta sporca contava ancora chi era uscito.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_lineup_athlete_left_roster import _replace_in_roster
from tests.integration.fantasy_lineups.test_lineup_departure_purge import (
    _add_future_round,
    _bench,
    _close_round,
    _h2h_slot,
    _name,
    _rate,
    _round_clubs,
    _starters,
    _stored,
    _submission,
)
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _trade,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import FantasyRole, LeagueAuditAction, LineupSlotKind
from fantasy_lineups.models import EffectiveLineup, LineupPlayer, TacticalMove
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_teams.models import FantasyRosterSlot
from fantasy_turns.live_pipeline import LIVE_PIPELINE_HORIZON, process_live_fantasy_rounds
from fantasy_turns.models import FantasyRound
from fantasy_turns.round_calculation_service import calculate_league_round
from leagues.models.league_audit_event import LeagueAuditEvent

LEFT_ROSTER_CODE = "lineup_athlete_left_roster"
TURN_START_SOURCE = "turn_start_autofill"


# -- helper -------------------------------------------------------------------------------


def _url(setup: dict) -> str:
    return f"/leagues/{setup['league_id']}/turni/{setup['round_id']}/formazione"


def _payload(setup: dict, team: str = "a") -> dict:
    """4-3-3; in panchina il primo difensore (D5) è 4°, dopo un P, un C e un A.

    Titolari P1, D1-D4, C1-C3, A1-A3. Panchina attiva P2 C4 A4 D5 C5 A5 D6 C6 A6 D7 (in regola:
    1P-3D-3C-3A nei primi 10). Tribuna, dall'11° posto: P3, D8-D11, C7-C11, A7-A10.
    """
    roles = setup[f"roles_{team}"]
    p, d, c, a = (
        roles[role] for role in (FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A)
    )
    starters = [p[0], *d[:4], *c[:3], *a[:3]]
    active = [p[1], c[3], a[3], d[4], c[4], a[4], d[5], c[5], a[5], d[6]]
    tribuna = [p[2], *d[7:], *c[6:], *a[6:]]
    return {
        "module": "4-3-3",
        "starterAthleteIds": [str(item) for item in starters],
        "benchAthleteIds": [str(item) for item in (*active, *tribuna)],
    }


def _save(client: TestClient, setup: dict, payload: dict, team: str = "a") -> None:
    saved = client.put(_url(setup), headers=_headers(setup[f"token_{team}"]), json=payload)
    assert saved.status_code == 200, saved.json()


def _start_turn(db_session: Session, setup: dict) -> None:
    """Primo blocco raggiunto: il turno è ancora aperto, le partite iniziano tra 5 minuti
    (dentro il margine di blocco della lega, 15 minuti)."""
    kickoff = datetime.now(UTC) + timedelta(minutes=5)
    fantasy_round = db_session.get(FantasyRound, UUID(setup["round_id"]))
    assert fantasy_round is not None
    fantasy_round.cutoff_at = kickoff
    for fixture in _round_clubs(db_session, setup["round_id"]):
        fixture.kickoff_at = kickoff
    db_session.commit()


def _run_job(db_session: Session) -> None:
    """Il giro del job del calcolo, come lo lancia lo scheduler dei dati sportivi."""
    process_live_fantasy_rounds(db_session, horizon=LIVE_PIPELINE_HORIZON)
    db_session.commit()


def _turn_start_audits(db_session: Session, setup: dict, team: str = "a") -> list[dict]:
    db_session.expire_all()
    rows = db_session.scalars(
        select(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == UUID(setup["league_id"]),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
        )
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    return [
        row.details
        for row in rows
        if (row.details or {}).get("source") == TURN_START_SOURCE
        and row.details["fantasyTeamId"] == setup[f"team_{team}"]
    ]


def _bench_ids(stored: list[tuple[str, int, UUID]]) -> list[UUID]:
    return [athlete_id for _, athlete_id in _bench(stored)]


def _rewrite_bench(db_session: Session, setup: dict, bench_ids: list[UUID]) -> None:
    """Panchina riscritta direttamente nel DB (stessi calciatori, altro ordine)."""
    submission = _submission(db_session, setup["round_id"], setup["team_a"])
    rows = {
        row.athlete_id: row
        for row in db_session.scalars(
            select(LineupPlayer).where(
                LineupPlayer.submission_id == submission.id,
                LineupPlayer.slot_kind == LineupSlotKind.BENCH,
            )
        ).all()
    }
    assert set(rows) == set(bench_ids)
    for offset, row in enumerate(rows.values()):
        row.sort_order = 1_000 + offset
    db_session.flush()
    for index, athlete_id in enumerate(bench_ids):
        rows[athlete_id].sort_order = index
    db_session.commit()


def _drop_from_roster(db_session: Session, setup: dict, athlete_ids: list[UUID]) -> None:
    """Uscita dalla rosa senza la pulizia all'uscita (dati di prima della correzione)."""
    for slot in db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(setup["team_a"]),
            FantasyRosterSlot.athlete_id.in_(athlete_ids),
        )
    ).all():
        slot.athlete_id = None
        slot.purchase_credits = None
    db_session.commit()


def _left_roster_messages(body: dict) -> list[str]:
    return [issue["message"] for issue in body["issues"] if issue["code"] == LEFT_ROSTER_CODE]


# -- 1. posto vuoto: entra il primo panchinaro, sale il primo della tribuna ---------------


def test_turn_start_fills_the_hole_from_the_bench_and_refills_the_bench_from_the_tribuna(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="ts.base", id_offset=9_100_000
    )
    roles = setup["roles_a"]
    payload = _payload(setup)
    _save(client, setup, payload)
    d = roles[FantasyRole.D]
    # A cede il titolare D2 (3° posto) prima del turno: la pulizia all'uscita lascia il posto
    # vuoto e la panchina com'era.
    _trade(client, setup, offered=[d[1]], requested=[setup["roles_b"][FantasyRole.D][-1]])
    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    assert 2 not in [order for order, _ in _starters(stored)]
    bench_before = _bench_ids(stored)
    assert bench_before == [UUID(item) for item in payload["benchAthleteIds"]]
    before = _submission(db_session, setup["round_id"], setup["team_a"])
    revision, submitted_at = before.revision, before.submitted_at

    _start_turn(db_session, setup)
    _run_job(db_session)

    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    expected_starters = [UUID(item) for item in payload["starterAthleteIds"]]
    expected_starters[2] = d[4]  # D5, primo difensore della panchina
    assert _starters(stored) == list(enumerate(expected_starters))
    # D8, primo difensore della tribuna, prende in panchina il posto di D5 (4°); gli altri
    # restano dove sono, la tribuna si ricompatta.
    expected_bench = [*bench_before[:3], d[7], *(item for item in bench_before[4:] if item != d[7])]
    assert _bench_ids(stored) == expected_bench
    assert _bench_ids(stored)[10:12] == [roles[FantasyRole.P][2], d[8]]  # P3, poi D9

    # Regola di sistema: nessuna mossa, nessuna nuova revisione, audit con chi è andato dove.
    after = _submission(db_session, setup["round_id"], setup["team_a"])
    assert (after.revision, after.submitted_at) == (revision, submitted_at)
    assert (
        db_session.scalars(select(TacticalMove).where(TacticalMove.submission_id == after.id)).all()
        == []
    )
    audits = _turn_start_audits(db_session, setup)
    assert len(audits) == 1
    audit = audits[0]
    assert audit["roundId"] == setup["round_id"]
    assert audit["tacticalMoveConsumed"] is False
    assert audit["revision"] == revision
    assert audit["removed"] == []
    assert audit["fills"] == [
        {
            "role": "D",
            "starterSortOrder": 2,
            "leftById": str(d[1]),
            "leftByName": _name(db_session, d[1]),
            "source": "bench",
            "starterId": str(d[4]),
            "starterName": _name(db_session, d[4]),
            "fromBenchSortOrder": 3,
            "benchId": str(d[7]),
            "benchName": _name(db_session, d[7]),
            "benchSortOrder": 3,
            "benchFromSortOrder": 11,
        }
    ]

    # Una seconda volta non cambia niente.
    _run_job(db_session)
    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored
    assert len(_turn_start_audits(db_session, setup)) == 1

    # GET formazione: l'avviso dice chi è entrato al posto di chi; il posto non è più vuoto e
    # l'avviso «scegli chi mettere al suo posto» non serve più.
    body = client.get(_url(setup), headers=_headers(setup["token_a"])).json()
    assert _left_roster_messages(body) == [
        f"All'inizio del turno 1 {_name(db_session, d[4])} è entrato al posto di "
        f"{_name(db_session, d[1])} (non più in rosa); dalla tribuna è salito in panchina "
        f"{_name(db_session, d[7])}."
    ]
    assert "missing_athlete" not in {issue["code"] for issue in body["issues"]}
    assert [player["sortOrder"] for player in body["lineup"]["starters"]] == list(range(11))
    assert body["lineup"]["revision"] == revision
    assert body["tacticalMovesUsed"] == 0
    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored
    assert len(_turn_start_audits(db_session, setup)) == 1


# -- 2. formazione sporca di prima della correzione: esce, si copre, non prende punti ------


def test_dirty_lineup_loses_the_departed_player_at_turn_start_and_scoring_ignores_him(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="ts.sporca", id_offset=9_200_000
    )
    d = setup["roles_a"][FantasyRole.D]
    payload_a = _payload(setup)
    payload_b = _payload(setup, team="b")
    _save(client, setup, payload_a)
    _save(client, setup, payload_b, team="b")
    # Il titolare D2 lascia la rosa senza la pulizia all'uscita (scritto direttamente nel DB, come
    # le formazioni salvate prima della correzione): resta 3° titolare nella formazione.
    newcomer = _replace_in_roster(db_session, setup, d[1], provider_id=9_209_999)
    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    assert (2, d[1]) in _starters(stored)

    # Il turno si gioca: partite finite, nessuno ha riaperto la formazione.
    _close_round(
        db_session,
        setup["round_id"],
        started=datetime.now(UTC) - timedelta(hours=3),
        homologated=False,
    )
    fielded = {
        UUID(item)
        for payload in (payload_a, payload_b)
        for item in (*payload["starterAthleteIds"], *payload["benchAthleteIds"])
    }
    scores = {athlete_id: 6.0 for athlete_id in fielded}
    scores[d[1]] = 40.0  # se contasse ancora, A farebbe 100 invece di 66
    _rate(db_session, setup, scores)
    slot = _h2h_slot(db_session, setup)

    calculate_league_round(
        db_session,
        round_id=UUID(setup["round_id"]),
        league_id=UUID(setup["league_id"]),
        actor_id=None,
        automatic=True,
    )
    db_session.commit()

    # Il punteggio non conta D2: A fa 11 x 6, come B.
    db_session.refresh(slot)
    assert slot.home_score == pytest.approx(66.0)
    assert slot.away_score == pytest.approx(66.0)
    effective_a = db_session.scalars(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == UUID(setup["round_id"]),
            EffectiveLineup.fantasy_team_id == UUID(setup["team_a"]),
        )
    ).one()
    assert str(d[1]) not in effective_a.effective_starter_ids
    assert str(d[4]) in effective_a.effective_starter_ids
    assert len(effective_a.effective_starter_ids) == 11

    # Prima del calcolo: D2 fuori, D5 al suo posto, D8 in panchina al posto di D5.
    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    assert d[1] not in {athlete_id for _, _, athlete_id in stored}
    assert newcomer not in {athlete_id for _, _, athlete_id in stored}
    starters = dict(_starters(stored))
    assert starters[2] == d[4]
    assert _bench_ids(stored)[3] == d[7]
    audit = _turn_start_audits(db_session, setup)[0]
    assert audit["removed"] == [
        {
            "athleteId": str(d[1]),
            "athleteName": _name(db_session, d[1]),
            "slotKind": "starter",
            "sortOrder": 2,
        }
    ]
    assert [(fill["leftById"], fill["starterId"], fill["benchId"]) for fill in audit["fills"]] == [
        (str(d[1]), str(d[4]), str(d[7]))
    ]
    # B non aveva niente da sistemare.
    assert _turn_start_audits(db_session, setup, team="b") == []


# -- 3. nessun panchinaro di quel ruolo: entra il primo della tribuna --------------------


def test_without_a_bench_player_of_the_role_the_first_tribuna_player_starts(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="ts.tribuna", id_offset=9_300_000
    )
    roles = setup["roles_a"]
    p, d, c, a = (
        roles[role] for role in (FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A)
    )
    _save(client, setup, _payload(setup))
    _trade(client, setup, offered=[d[1]], requested=[setup["roles_b"][FantasyRole.D][-1]])
    # Panchina attiva senza difensori (scritta nel DB): D5, D6, D7 in tribuna, dopo P3.
    bench = [p[1], c[3], a[3], c[4], a[4], c[5], a[5], c[6], a[6], c[7]]
    bench += [p[2], d[4], d[5], d[6], *d[7:], *c[8:], *a[7:]]
    _rewrite_bench(db_session, setup, bench)
    _start_turn(db_session, setup)

    # Il primo che apre la formazione dopo il blocco (prima del job) la trova già sistemata.
    body = client.get(_url(setup), headers=_headers(setup["token_a"])).json()
    starters = {player["sortOrder"]: player["athleteId"] for player in body["lineup"]["starters"]}
    assert starters[2] == str(d[4])  # D5, primo difensore della tribuna
    assert _left_roster_messages(body) == [
        f"All'inizio del turno 1 {_name(db_session, d[4])} è entrato dalla tribuna al posto di "
        f"{_name(db_session, d[1])} (non più in rosa): in panchina non c'era nessun difensore "
        "da far entrare."
    ]
    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    assert dict(_starters(stored))[2] == d[4]
    # La panchina attiva non cambia; la tribuna si ricompatta senza di lui.
    assert _bench_ids(stored) == [item for item in bench if item != d[4]]
    audit = _turn_start_audits(db_session, setup)
    assert [
        (fill["source"], fill["fromBenchSortOrder"], fill["benchId"]) for fill in audit[0]["fills"]
    ] == [("tribuna", 11, None)]

    # Riaperta (o col job) non cambia più.
    client.get(_url(setup), headers=_headers(setup["token_a"]))
    _run_job(db_session)
    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored
    assert len(_turn_start_audits(db_session, setup)) == 1


# -- 4. nessuno di quel ruolo: il posto resta vuoto -----------------------------------------


def test_without_anyone_of_the_role_the_place_stays_empty(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="ts.vuoto", id_offset=9_400_000
    )
    d = setup["roles_a"][FantasyRole.D]
    payload = _payload(setup)
    _save(client, setup, payload)
    # Escono dalla rosa (senza la pulizia all'uscita) il titolare D2 e tutti i difensori che non
    # sono titolari: in rosa restano solo D1, D3 e D4, già in campo.
    departed = [d[1], *d[4:]]
    _drop_from_roster(db_session, setup, departed)
    _start_turn(db_session, setup)

    _run_job(db_session)

    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    expected_starters = [
        (index, UUID(item))
        for index, item in enumerate(payload["starterAthleteIds"])
        if UUID(item) != d[1]
    ]
    assert _starters(stored) == expected_starters
    assert _bench_ids(stored) == [
        UUID(item) for item in payload["benchAthleteIds"] if UUID(item) not in departed
    ]
    audits = _turn_start_audits(db_session, setup)
    assert len(audits) == 1
    assert [item["athleteId"] for item in audits[0]["removed"]] == [str(item) for item in departed]
    assert audits[0]["fills"][0]["source"] is None
    assert audits[0]["fills"][0]["starterId"] is None

    _run_job(db_session)
    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored
    assert len(_turn_start_audits(db_session, setup)) == 1

    body = client.get(_url(setup), headers=_headers(setup["token_a"])).json()
    names = [_name(db_session, item) for item in departed[1:]]
    assert _left_roster_messages(body) == [
        f"All'inizio del turno 1 il posto di {_name(db_session, d[1])} (non più in rosa) è rimasto "
        "vuoto: in rosa non c'è nessun altro difensore da schierare.",
        f"All'inizio del turno 1 {', '.join(names[:-1])} e {names[-1]} sono stati tolti dalla "
        "formazione: non sono più nella tua rosa.",
    ]
    assert "missing_athlete" in {issue["code"] for issue in body["issues"]}
    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored

    # Il calcolo parte lo stesso, in 10.
    compute_round_effective_lineups(db_session, round_id=UUID(setup["round_id"]))
    db_session.commit()
    effective = db_session.scalars(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == UUID(setup["round_id"]),
            EffectiveLineup.fantasy_team_id == UUID(setup["team_a"]),
        )
    ).one()
    assert len(effective.effective_starter_ids) == 10


# -- 4 bis. nessuna formazione: la copia del turno precedente con un posto vuoto si copre -----


def test_previous_round_copy_with_a_departed_starter_is_filled_not_zeroed(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Voce 6.7 (28/11): la formazione automatica non va più «a zero».

    Al turno 2 la squadra non ha né formazione né bozza; quella del turno 1 c'è, con un titolare
    poi uscito dalla rosa. Prima la copia, incompleta, non si poteva confermare e la formazione
    automatica era «a zero» (0 titolari), che la regola di inizio turno salta. Ora la copia si
    salva con il posto vuoto e la regola di inizio turno lo copre dalla panchina.
    """
    setup = _trade_league(
        client, db_session, competition_ids, prefix="ts.copia", id_offset=9_450_000
    )
    d = setup["roles_a"][FantasyRole.D]
    payload = _payload(setup)
    _save(client, setup, payload)
    first_round = setup["round_id"]
    _close_round(
        db_session,
        first_round,
        started=datetime.now(UTC) - timedelta(hours=3),
        homologated=True,
    )
    # Il titolare D2 (3° posto) esce dalla rosa: al suo posto un nuovo difensore.
    newcomer = _replace_in_roster(db_session, setup, d[1], provider_id=9_459_999)
    # Turno 2 al primo blocco (le partite iniziano tra 5 minuti, margine di lega 15 minuti),
    # nessuna formazione né bozza salvata.
    second_round = _add_future_round(
        db_session,
        setup,
        number=2,
        kickoff=datetime.now(UTC) + timedelta(minutes=5),
        provider_offset=9_450_000 + 60_000,
    )
    second = {**setup, "round_id": second_round}

    body = client.get(_url(second), headers=_headers(setup["token_a"])).json()

    assert body["lineup"]["autoResolutionSource"] == "previous_round"
    starters = {player["sortOrder"]: player["athleteId"] for player in body["lineup"]["starters"]}
    expected = list(payload["starterAthleteIds"])
    expected[2] = str(d[4])  # D5, primo difensore della panchina
    assert starters == dict(enumerate(expected))
    assert "missing_athlete" not in {issue["code"] for issue in body["issues"]}
    stored = _stored(db_session, second_round, setup["team_a"])
    assert _starters(stored) == [(index, UUID(item)) for index, item in enumerate(expected)]
    assert d[1] not in {athlete_id for _, _, athlete_id in stored}
    assert d[4] not in _bench_ids(stored)
    assert newcomer in _bench_ids(stored)

    audits = _turn_start_audits(db_session, second)
    assert [audit["roundId"] for audit in audits] == [second_round]
    assert [(fill["source"], fill["starterId"]) for fill in audits[0]["fills"]] == [
        ("bench", str(d[4]))
    ]
    assert any(
        message.startswith(f"All'inizio del turno 2 {_name(db_session, d[4])} è entrato")
        for message in _left_roster_messages(body)
    )

    # Riaperta non cambia più; il turno 1 non si tocca.
    client.get(_url(second), headers=_headers(setup["token_a"]))
    assert _stored(db_session, second_round, setup["team_a"]) == stored
    assert len(_turn_start_audits(db_session, second)) == 1
    assert d[1] in {
        athlete_id for _, _, athlete_id in _stored(db_session, first_round, setup["team_a"])
    }


# -- 5. formazione completa e in regola: invariata ----------------------------------------


def test_complete_valid_lineup_is_unchanged_at_turn_start(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="ts.piena", id_offset=9_500_000
    )
    _save(client, setup, _payload(setup))
    stored = _stored(db_session, setup["round_id"], setup["team_a"])
    _start_turn(db_session, setup)

    _run_job(db_session)
    body = client.get(_url(setup), headers=_headers(setup["token_a"])).json()

    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored
    assert _turn_start_audits(db_session, setup) == []
    assert body["issues"] == []


# -- 6. turno omologato o già calcolato: invariato ----------------------------------------


@pytest.mark.parametrize(
    ("closed_state", "id_offset"), [("omologato", 9_600_000), ("calcolato", 9_700_000)]
)
def test_finalized_or_already_scored_turn_is_unchanged(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    closed_state: str,
    id_offset: int,
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix=f"ts.{closed_state}", id_offset=id_offset
    )
    d = setup["roles_a"][FantasyRole.D]
    _save(client, setup, _payload(setup))
    started = datetime.now(UTC) - timedelta(hours=3)
    if closed_state == "omologato":
        _close_round(db_session, setup["round_id"], started=started, homologated=True)
    else:
        # Turno bloccato e già calcolato (formazioni effettive presenti), non ancora omologato.
        _close_round(db_session, setup["round_id"], started=started, homologated=False)
        compute_round_effective_lineups(db_session, round_id=UUID(setup["round_id"]))
        db_session.commit()
    # Formazione sporca e con un posto da coprire: un titolare esce dalla rosa senza pulizia.
    _replace_in_roster(db_session, setup, d[1], provider_id=id_offset + 9_999)
    stored = _stored(db_session, setup["round_id"], setup["team_a"])

    _run_job(db_session)
    client.get(_url(setup), headers=_headers(setup["token_a"]))

    assert _stored(db_session, setup["round_id"], setup["team_a"]) == stored
    assert (2, d[1]) in _starters(stored)
    assert _turn_start_audits(db_session, setup) == []
