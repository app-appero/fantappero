# ruff: noqa: F811
"""Formazione salvata con un calciatore non più in rosa (QA 19/11, qa-02 e N. Zortea).

La squadra cede un calciatore dopo aver salvato la formazione del turno aperto. Lo scambio lo
toglie già dalla formazione salvata e dalla bozza (fantasy_lineups.departures, vedi anche
test_lineup_departure_purge.py); se resta lì per altre vie (dati precedenti, correzioni fatte
a mano nel DB) GET formazione lo toglie comunque dai titolari e dalla panchina restituiti. In
entrambi i casi il suo posto resta vuoto e l'avviso dice chi è stato tolto. Il salvataggio con
lui ancora dentro resta rifiutato, ma il messaggio dice chi è: «non è più nella tua rosa» se in
rosa c'è stato davvero (lo storico dei possessi, perciò qui ``record_ownership``), «non è nella
tua rosa» per chi non c'è mai stato (QA 19-20/11). Al primo blocco del turno lo
toglie la regola di inizio turno (fantasy_lineups.turn_start, test_lineup_turn_start_autofill.py),
anche se la sua partita è già in blocco. Nei turni già calcolati o conclusi la formazione non si
tocca: è storia del punteggio.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_payload,
    _lineup_url,
    _occupied_slots,
    _trade,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import FantasyRole, FantasyTurnStatus
from fantasy_lineups.models import LineupDraft, LineupPlayer, LineupSubmission
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_teams.models import FantasyRosterSlot
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

LEFT_ROSTER_CODE = "lineup_athlete_left_roster"


def _left_roster_notice(name: str) -> str:
    return (
        f"{name} non è più nella tua rosa: è stato tolto dalla formazione, "
        "scegli chi mettere al suo posto."
    )


def _name(db_session: Session, athlete_id: UUID) -> str:
    athlete = db_session.get(Athlete, athlete_id)
    assert athlete is not None
    return athlete.canonical_name


def _save_lineup(client: TestClient, db_session: Session, setup: dict) -> dict:
    payload = _lineup_payload(_occupied_slots(db_session, setup["team_a"]), setup["role_of"])
    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()
    return payload


def _stored_athlete_ids(db_session: Session, setup: dict) -> list[tuple[str, int, UUID]]:
    """Formazione salvata di A così com'è nel DB: (titolare/panchina, posizione, calciatore)."""
    db_session.expire_all()
    rows = db_session.execute(
        select(LineupPlayer.slot_kind, LineupPlayer.sort_order, LineupPlayer.athlete_id)
        .join(LineupSubmission, LineupSubmission.id == LineupPlayer.submission_id)
        .where(
            LineupSubmission.round_id == UUID(setup["round_id"]),
            LineupSubmission.fantasy_team_id == UUID(setup["team_a"]),
        )
    ).all()
    return sorted((kind.value, order, athlete_id) for kind, order, athlete_id in rows)


def _replace_in_roster(
    db_session: Session, setup: dict, departed: UUID, *, provider_id: int
) -> UUID:
    """Rimozione diretta dal DB: al suo slot va un nuovo calciatore dello stesso ruolo e club."""
    assignment = db_session.scalars(
        select(RoleAssignment).where(RoleAssignment.athlete_id == departed)
    ).one()
    newcomer = Athlete(provider_id=provider_id, canonical_name=f"Nuovo {provider_id}")
    db_session.add(newcomer)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=newcomer.id,
            season_year=2026,
            role=assignment.role,
            mapping_version="v1.0.0",
            provider_position_raw=assignment.role.value,
            club_id=assignment.club_id,
        )
    )
    slot = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(setup["team_a"]),
            FantasyRosterSlot.athlete_id == departed,
        )
    ).one()
    slot.athlete_id = newcomer.id
    db_session.commit()
    setup["role_of"][newcomer.id] = assignment.role
    return newcomer.id


def _fixture_of(db_session: Session, setup: dict, athlete_id: UUID) -> Fixture:
    club_id = db_session.scalars(
        select(RoleAssignment.club_id).where(RoleAssignment.athlete_id == athlete_id)
    ).one()
    return db_session.scalars(
        select(Fixture)
        .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
        .where(
            FantasyRoundFixture.round_id == UUID(setup["round_id"]),
            or_(Fixture.home_club_id == club_id, Fixture.away_club_id == club_id),
        )
    ).one()


def test_bench_player_traded_away_leaves_the_open_turn_lineup(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client,
        db_session,
        competition_ids,
        prefix="lar.panchina",
        id_offset=9_500_000,
        record_ownership=True,
    )
    token = setup["token_a"]
    payload = _save_lineup(client, db_session, setup)
    # 4° in panchina, come N. Zortea per qa-02: un difensore della panchina attiva.
    departed = UUID(payload["benchAthleteIds"][3])
    assert setup["role_of"][departed] == FantasyRole.D
    name = _name(db_session, departed)
    incoming = setup["roles_b"][FantasyRole.D][-1]
    _trade(client, setup, offered=[departed], requested=[incoming])
    # Lo scambio lo ha già tolto dalla formazione salvata, non solo da quella restituita.
    stored_before = _stored_athlete_ids(db_session, setup)
    assert departed not in {athlete_id for _, _, athlete_id in stored_before}

    context = client.get(_lineup_url(setup), headers=_headers(token))
    assert context.status_code == 200, context.json()
    body = context.json()
    starters = [player["athleteId"] for player in body["lineup"]["starters"]]
    bench = [player["athleteId"] for player in body["lineup"]["bench"]]
    assert starters == payload["starterAthleteIds"]
    # Tolto dalla panchina, gli altri nello stesso ordine; al 10° posto, invece del primo della
    # tribuna (P3, un portiere), sale il primo difensore della tribuna (Rosario, 20/11), e il
    # difensore arrivato con lo scambio è in coda, come lo mettono web e app.
    kept = [item for item in payload["benchAthleteIds"] if item != str(departed)]
    first_tribuna, first_tribuna_defender = UUID(kept[9]), UUID(kept[10])
    assert setup["role_of"][first_tribuna] == FantasyRole.P
    assert setup["role_of"][first_tribuna_defender] == FantasyRole.D
    assert bench == [*kept[:9], kept[10], kept[9], *kept[11:], str(incoming)]
    roster_ids = {row["athleteId"] for row in body["roster"]}
    assert str(departed) not in roster_ids
    assert str(incoming) in roster_ids
    notices = [issue for issue in body["issues"] if issue["code"] == LEFT_ROSTER_CODE]
    assert notices == [{"code": LEFT_ROSTER_CODE, "message": _left_roster_notice(name)}]
    assert body["issues"][0]["code"] == LEFT_ROSTER_CODE
    codes = {issue["code"] for issue in body["issues"]}
    assert "athlete_not_in_roster" not in codes
    assert "bench_roles_invalid" not in codes
    # GET non cambia niente: la pulizia l'ha già fatta lo scambio.
    assert _stored_athlete_ids(db_session, setup) == stored_before

    # Salvare con lui ancora dentro (app aperta prima dello scambio) resta rifiutato, con il nome.
    stale = client.put(_lineup_url(setup), headers=_headers(token), json=payload)
    assert stale.status_code == 400
    assert stale.json()["code"] == "athlete_not_in_roster"
    assert stale.json()["message"] == f"{name} non è più nella tua rosa."

    # Al suo posto il difensore arrivato con lo scambio: la formazione si salva.
    corrected_bench = list(payload["benchAthleteIds"])
    corrected_bench[3] = str(incoming)
    corrected = {**payload, "benchAthleteIds": corrected_bench}
    saved = client.put(_lineup_url(setup), headers=_headers(token), json=corrected)
    assert saved.status_code == 200, saved.json()
    assert [player["athleteId"] for player in saved.json()["lineup"]["bench"]] == corrected_bench
    assert not [issue for issue in saved.json()["issues"] if issue["code"] == LEFT_ROSTER_CODE]
    assert departed not in {
        athlete_id for _, _, athlete_id in _stored_athlete_ids(db_session, setup)
    }

    again = client.get(_lineup_url(setup), headers=_headers(token)).json()
    assert again["issues"] == []
    assert [player["athleteId"] for player in again["lineup"]["bench"]] == corrected_bench


def test_player_of_another_team_is_refused_with_the_neutral_message(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19-20/11: chi non è mai stato in rosa non «non è più» nella tua rosa: «non è»."""
    setup = _trade_league(
        client,
        db_session,
        competition_ids,
        prefix="lar.altrui",
        id_offset=9_300_000,
        record_ownership=True,
    )
    token = setup["token_a"]
    payload = _save_lineup(client, db_session, setup)
    outsider = setup["roles_b"][FantasyRole.D][0]
    name = _name(db_session, outsider)
    bench = list(payload["benchAthleteIds"])
    bench[3] = str(outsider)
    foreign = {**payload, "benchAthleteIds": bench}

    saved = client.put(_lineup_url(setup), headers=_headers(token), json=foreign)
    assert saved.status_code == 400
    assert saved.json()["code"] == "athlete_not_in_roster"
    assert saved.json()["message"] == f"{name} non è nella tua rosa."

    draft = client.put(f"{_lineup_url(setup)}/bozza", headers=_headers(token), json=foreign)
    assert draft.status_code == 400
    assert draft.json()["code"] == "athlete_not_in_roster"
    assert draft.json()["message"] == f"{name} non è nella tua rosa."

    # Con anche un difensore appena ceduto (più avanti in panchina) il neutro vale per entrambi;
    # il solo ceduto resta «non è più» (test_bench_player_traded_away_leaves_the_open_turn_lineup).
    position = next(
        index
        for index, athlete_id in enumerate(payload["benchAthleteIds"])
        if index > 3 and setup["role_of"][UUID(athlete_id)] == FantasyRole.D
    )
    departed = UUID(payload["benchAthleteIds"][position])
    departed_name = _name(db_session, departed)
    _trade(client, setup, offered=[departed], requested=[setup["roles_b"][FantasyRole.D][-1]])
    both = client.put(_lineup_url(setup), headers=_headers(token), json=foreign)
    assert both.status_code == 400
    assert both.json()["message"] == f"{name} e {departed_name} non sono nella tua rosa."


def test_starter_removed_from_roster_leaves_an_empty_slot_in_lineup_and_draft(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client,
        db_session,
        competition_ids,
        prefix="lar.titolare",
        id_offset=9_600_000,
        record_ownership=True,
    )
    token = setup["token_a"]
    payload = _save_lineup(client, db_session, setup)
    # Una bozza con gli stessi titolari e la panchina rovesciata, salvata dopo la formazione.
    draft_payload = {**payload, "benchAthleteIds": list(reversed(payload["benchAthleteIds"]))}
    draft = client.put(f"{_lineup_url(setup)}/bozza", headers=_headers(token), json=draft_payload)
    assert draft.status_code == 200, draft.json()

    departed = UUID(payload["starterAthleteIds"][2])
    assert setup["role_of"][departed] == FantasyRole.D
    name = _name(db_session, departed)
    newcomer = _replace_in_roster(db_session, setup, departed, provider_id=9_609_999)
    stored_before = _stored_athlete_ids(db_session, setup)

    body = client.get(_lineup_url(setup), headers=_headers(token)).json()
    lineup_starters = body["lineup"]["starters"]
    assert [player["athleteId"] for player in lineup_starters] == [
        item for item in payload["starterAthleteIds"] if item != str(departed)
    ]
    # Il terzo posto (un difensore) resta vuoto: le posizioni degli altri non scalano.
    assert [player["sortOrder"] for player in lineup_starters] == [0, 1, *range(3, 11)]
    expected_draft_starters = list(payload["starterAthleteIds"])
    expected_draft_starters[2] = ""
    assert body["draft"]["starterAthleteIds"] == expected_draft_starters
    assert body["draft"]["benchAthleteIds"] == draft_payload["benchAthleteIds"]
    # Un solo avviso anche se era sia nella formazione sia nella bozza.
    notices = [issue for issue in body["issues"] if issue["code"] == LEFT_ROSTER_CODE]
    assert notices == [{"code": LEFT_ROSTER_CODE, "message": _left_roster_notice(name)}]
    assert "missing_athlete" in {issue["code"] for issue in body["issues"]}
    # Sola lettura: formazione e bozza nel DB restano quelle salvate.
    assert _stored_athlete_ids(db_session, setup) == stored_before
    stored_draft = db_session.scalars(
        select(LineupDraft).where(LineupDraft.fantasy_team_id == UUID(setup["team_a"]))
    ).one()
    assert str(departed) in stored_draft.starter_athlete_ids

    # Anche la bozza con lui dentro è rifiutata col suo nome.
    stale_draft = client.put(
        f"{_lineup_url(setup)}/bozza", headers=_headers(token), json=draft_payload
    )
    assert stale_draft.status_code == 400
    assert stale_draft.json()["code"] == "athlete_not_in_roster"
    assert stale_draft.json()["message"] == f"{name} non è più nella tua rosa."

    corrected_starters = list(payload["starterAthleteIds"])
    corrected_starters[2] = str(newcomer)
    saved = client.put(
        _lineup_url(setup),
        headers=_headers(token),
        json={**payload, "starterAthleteIds": corrected_starters},
    )
    assert saved.status_code == 200, saved.json()
    assert [player["athleteId"] for player in saved.json()["lineup"]["starters"]] == (
        corrected_starters
    )
    assert saved.json()["draft"] is None
    assert saved.json()["issues"] == []


def _depart_then_close_turn(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    id_offset: int,
    homologated: bool,
) -> tuple[dict, dict, UUID]:
    setup = _trade_league(client, db_session, competition_ids, prefix=prefix, id_offset=id_offset)
    payload = _save_lineup(client, db_session, setup)
    departed = UUID(payload["benchAthleteIds"][3])

    # Il turno è in corso (o finito): tutte le partite sono iniziate.
    started = datetime.now(UTC) - timedelta(hours=3)
    fantasy_round = db_session.get(FantasyRound, UUID(setup["round_id"]))
    assert fantasy_round is not None
    fantasy_round.status = FantasyTurnStatus.LOCKED
    fantasy_round.cutoff_at = started
    fantasy_round.window_start_at = started - timedelta(hours=1)
    if homologated:
        fantasy_round.homologated_at = datetime.now(UTC)
    for fixture in db_session.scalars(
        select(Fixture)
        .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
        .where(FantasyRoundFixture.round_id == fantasy_round.id)
    ).all():
        fixture.kickoff_at = started
        fixture.status_short = "FT" if homologated else "2H"
    db_session.commit()
    if not homologated:
        # Turno bloccato e già calcolato: dopo il primo calcolo la regola di inizio turno
        # (fantasy_lineups.turn_start) non lo tocca più.
        compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
        db_session.commit()
    # Uscito senza passare dal mercato (correzione diretta nel DB): resta nella formazione
    # salvata. Uno scambio lo avrebbe già tolto, e a turno in corso il mercato è chiuso.
    _replace_in_roster(db_session, setup, departed, provider_id=id_offset + 9_999)
    return setup, payload, departed


def _assert_lineup_untouched(
    client: TestClient,
    db_session: Session,
    setup: dict,
    payload: dict,
    departed: UUID,
) -> None:
    stored_before = _stored_athlete_ids(db_session, setup)
    body = client.get(_lineup_url(setup), headers=_headers(setup["token_a"])).json()
    assert [player["athleteId"] for player in body["lineup"]["starters"]] == (
        payload["starterAthleteIds"]
    )
    assert [player["athleteId"] for player in body["lineup"]["bench"]] == (
        payload["benchAthleteIds"]
    )
    codes = [issue["code"] for issue in body["issues"]]
    assert LEFT_ROSTER_CODE not in codes
    # Resta segnalato, ora con il nome.
    not_in_roster = [issue for issue in body["issues"] if issue["code"] == "athlete_not_in_roster"]
    assert not_in_roster == [
        {
            "code": "athlete_not_in_roster",
            "message": f"{_name(db_session, departed)} non è più nella tua rosa.",
        }
    ]
    assert _stored_athlete_ids(db_session, setup) == stored_before


def test_locked_and_scored_turn_lineup_with_a_departed_player_is_left_alone(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, payload, departed = _depart_then_close_turn(
        client,
        db_session,
        competition_ids,
        prefix="lar.bloccato",
        id_offset=9_700_000,
        homologated=False,
    )
    _assert_lineup_untouched(client, db_session, setup, payload, departed)


def test_finished_turn_lineup_with_a_departed_player_is_left_alone(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, payload, departed = _depart_then_close_turn(
        client,
        db_session,
        competition_ids,
        prefix="lar.concluso",
        id_offset=9_800_000,
        homologated=True,
    )
    _assert_lineup_untouched(client, db_session, setup, payload, departed)


def test_departed_player_whose_match_is_locked_leaves_the_lineup_at_turn_start(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Turno ancora aperto, ma la partita del calciatore uscito è già in blocco.

    È il primo blocco del turno: la regola di inizio turno (fantasy_lineups.turn_start,
    decisione del 19/11) toglie dalla formazione chi non è più in rosa, anche se la sua
    partita è già in blocco. Prima del primo calcolo non conta ancora per nessun punteggio.
    """
    setup = _trade_league(
        client, db_session, competition_ids, prefix="lar.partita", id_offset=9_400_000
    )
    payload = _save_lineup(client, db_session, setup)
    departed = UUID(payload["benchAthleteIds"][3])
    _replace_in_roster(db_session, setup, departed, provider_id=9_409_999)
    # Entro il margine di blocco della lega (15 minuti) ma prima della chiusura del turno.
    fixture = _fixture_of(db_session, setup, departed)
    fixture.kickoff_at = datetime.now(UTC) + timedelta(minutes=5)
    db_session.commit()

    body = client.get(_lineup_url(setup), headers=_headers(setup["token_a"])).json()
    assert body["effectiveStatus"] == "open"
    assert str(departed) not in [player["athleteId"] for player in body["lineup"]["bench"]]
    assert [issue for issue in body["issues"] if issue["code"] == LEFT_ROSTER_CODE] == [
        {
            "code": LEFT_ROSTER_CODE,
            "message": (
                f"All'inizio del turno 1 {_name(db_session, departed)} è stato tolto dalla "
                "formazione: non è più nella tua rosa."
            ),
        }
    ]
    assert departed not in {
        athlete_id for _, _, athlete_id in _stored_athlete_ids(db_session, setup)
    }
