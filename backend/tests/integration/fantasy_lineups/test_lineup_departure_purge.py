# ruff: noqa: F811
"""Chi esce dalla rosa esce dalle formazioni dei turni non ancora iniziati (QA 19/11, punteggio).

Con 5423e50 il calciatore uscito spariva solo in lettura (GET formazione): nel DB restava tra i
``LineupPlayer`` e nella bozza, e se il fantallenatore non salvava di nuovo prima del blocco il
calcolo del turno lo contava ancora per la vecchia squadra. Ora lo toglie il cambio di rosa
stesso (scambio, svincolo, rimozione o sostituzione dell'admin, cambio in asta live), dalla
formazione e dalla bozza dei turni programmati o aperti non ancora iniziati. I turni bloccati o
conclusi restano com'erano: il ricalcolo non riscrive la storia.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_payload,
    _occupied_slots,
    _trade,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import (
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueCalendarStatus,
    NotificationCategory,
)
from fantasy_lineups.models import (
    EffectiveLineup,
    LineupDraft,
    LineupPlayer,
    LineupSubmission,
    TacticalMove,
)
from fantasy_lineups.rules import lineup_athlete_left_roster_message
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_ratings.config import DEFAULT_FORMULA_VERSION
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.scoring_service import compute_round_results
from notifications.models import Notification
from notifications.reminder_service import LineupReminderService
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

LEFT_ROSTER_CODE = "lineup_athlete_left_roster"
DEPARTURE_SOURCE = "roster_departure"


# -- helper -------------------------------------------------------------------------------


def _url(setup: dict, round_id: str | None = None) -> str:
    return f"/leagues/{setup['league_id']}/turni/{round_id or setup['round_id']}/formazione"


def _save_lineup(
    client: TestClient,
    db_session: Session,
    setup: dict,
    *,
    team: str = "a",
    round_id: str | None = None,
) -> dict:
    payload = _lineup_payload(_occupied_slots(db_session, setup[f"team_{team}"]), setup["role_of"])
    saved = client.put(
        _url(setup, round_id), headers=_headers(setup[f"token_{team}"]), json=payload
    )
    assert saved.status_code == 200, saved.json()
    return payload


def _save_draft(client: TestClient, setup: dict, payload: dict) -> None:
    saved = client.put(f"{_url(setup)}/bozza", headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()


def _stored(db_session: Session, round_id: str, team_id: str) -> list[tuple[str, int, UUID]]:
    """Formazione salvata così com'è nel DB: (titolare/panchina, posizione, calciatore)."""
    db_session.expire_all()
    rows = db_session.execute(
        select(LineupPlayer.slot_kind, LineupPlayer.sort_order, LineupPlayer.athlete_id)
        .join(LineupSubmission, LineupSubmission.id == LineupPlayer.submission_id)
        .where(
            LineupSubmission.round_id == UUID(round_id),
            LineupSubmission.fantasy_team_id == UUID(team_id),
        )
    ).all()
    return sorted((kind.value, order, athlete_id) for kind, order, athlete_id in rows)


def _starters(stored: list[tuple[str, int, UUID]]) -> list[tuple[int, UUID]]:
    return [(order, athlete_id) for kind, order, athlete_id in stored if kind == "starter"]


def _bench(stored: list[tuple[str, int, UUID]]) -> list[tuple[int, UUID]]:
    return [(order, athlete_id) for kind, order, athlete_id in stored if kind == "bench"]


def _submission(db_session: Session, round_id: str, team_id: str) -> LineupSubmission:
    db_session.expire_all()
    return db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == UUID(round_id),
            LineupSubmission.fantasy_team_id == UUID(team_id),
        )
    ).one()


def _draft(db_session: Session, round_id: str, team_id: str) -> LineupDraft:
    db_session.expire_all()
    return db_session.scalars(
        select(LineupDraft).where(
            LineupDraft.round_id == UUID(round_id),
            LineupDraft.fantasy_team_id == UUID(team_id),
        )
    ).one()


def _name(db_session: Session, athlete_id: UUID) -> str:
    athlete = db_session.get(Athlete, athlete_id)
    assert athlete is not None
    return athlete.canonical_name


def _slot_index(db_session: Session, team_id: str, athlete_id: UUID) -> int:
    db_session.expire_all()
    return db_session.scalars(
        select(FantasyRosterSlot.slot_index).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.athlete_id == athlete_id,
        )
    ).one()


def _expected_starters(payload: dict, *departed: UUID) -> list[tuple[int, UUID]]:
    """Titolari salvati meno chi è uscito: gli altri tengono la loro posizione (il posto resta)."""
    return [
        (index, UUID(item))
        for index, item in enumerate(payload["starterAthleteIds"])
        if UUID(item) not in departed
    ]


def _expected_bench(bench_ids: list[str], *departed: UUID) -> list[tuple[int, UUID]]:
    """Panchina meno chi è uscito: gli altri nello stesso ordine, posizioni di nuovo 0..n-1."""
    return list(enumerate(UUID(item) for item in bench_ids if UUID(item) not in departed))


def _round_clubs(db_session: Session, round_id: str) -> list[Fixture]:
    return list(
        db_session.scalars(
            select(Fixture)
            .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
            .where(FantasyRoundFixture.round_id == UUID(round_id))
        ).all()
    )


def _add_future_round(
    db_session: Session, setup: dict, *, number: int, kickoff: datetime, provider_offset: int
) -> str:
    """Un altro turno aperto della lega, con una partita tra gli stessi club del primo."""
    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(setup["league_id"]),
        number=number,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=kickoff - timedelta(days=1),
        window_end_at=kickoff + timedelta(days=3),
        cutoff_at=kickoff,
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()
    for index, template in enumerate(_round_clubs(db_session, setup["round_id"])):
        fixture = Fixture(
            provider_id=provider_offset + index,
            sport_season_id=template.sport_season_id,
            home_club_id=template.home_club_id,
            away_club_id=template.away_club_id,
            kickoff_at=kickoff,
            status_short="NS",
        )
        db_session.add(fixture)
        db_session.flush()
        db_session.add(
            FantasyRoundFixture(
                round_id=fantasy_round.id,
                league_id=UUID(setup["league_id"]),
                fixture_id=fixture.id,
                observed_kickoff_at=kickoff,
            )
        )
    db_session.commit()
    return str(fantasy_round.id)


def _close_round(
    db_session: Session, round_id: str, *, started: datetime, homologated: bool
) -> None:
    """Turno giocato: tutte le partite finite, bloccato (e omologato se ``homologated``)."""
    fantasy_round = db_session.get(FantasyRound, UUID(round_id))
    assert fantasy_round is not None
    fantasy_round.status = FantasyTurnStatus.LOCKED
    fantasy_round.cutoff_at = started
    fantasy_round.window_start_at = started - timedelta(hours=1)
    fantasy_round.window_end_at = started + timedelta(hours=3)
    if homologated:
        fantasy_round.homologated_at = datetime.now(UTC)
    for fixture in _round_clubs(db_session, round_id):
        fixture.kickoff_at = started
        fixture.status_short = "FT"
    db_session.commit()


def _rate(db_session: Session, setup: dict, scores: dict[UUID, float]) -> None:
    """Un voto per calciatore nella partita del suo club (fantavoto = ``scores``)."""
    fixtures = _round_clubs(db_session, setup["round_id"])
    fixture_by_club = {
        club_id: fixture
        for fixture in fixtures
        for club_id in (fixture.home_club_id, fixture.away_club_id)
    }
    for athlete_id, score in scores.items():
        athlete = db_session.get(Athlete, athlete_id)
        assignment = db_session.scalars(
            select(RoleAssignment).where(RoleAssignment.athlete_id == athlete_id)
        ).one()
        raw = min(max(score, 3.0), 10.0)
        db_session.add(
            PlayerMatchRating(
                fixture_id=fixture_by_club[assignment.club_id].id,
                league_id=UUID(setup["league_id"]),
                athlete_id=athlete_id,
                athlete_provider_id=athlete.provider_id,
                formula_version=DEFAULT_FORMULA_VERSION,
                role=assignment.role,
                minutes=90,
                eligible=True,
                eligibility_reason="played",
                base=6.0,
                raw_before_clamp=raw,
                raw=raw,
                display=raw,
                fantasy_score=score,
                stats_hash=f"hash-{athlete_id}",
            )
        )
    db_session.commit()


def _h2h_slot(db_session: Session, setup: dict) -> LeagueCalendarSlot:
    """A in casa contro B nella giornata 1 del calendario."""
    now = datetime.now(UTC)
    memberships = {
        key: db_session.get(FantasyTeam, UUID(setup[key])).membership_id
        for key in ("team_a", "team_b")
    }
    calendar = LeagueCalendar(
        league_id=UUID(setup["league_id"]),
        status=LeagueCalendarStatus.CONFIRMED,
        algorithm_version="test",
        participant_fingerprint="test",
        # Il vincolo del calendario vuole da 4 a 10 partecipanti; conta solo lo scontro A-B.
        participant_count=4,
        round_count=1,
        matchup_count=1,
        bye_count=0,
        generated_at=now,
        confirmed_at=now,
    )
    db_session.add(calendar)
    db_session.flush()
    slot = LeagueCalendarSlot(
        calendar_id=calendar.id,
        round_number=1,
        slot_index=0,
        is_bye=False,
        home_membership_id=memberships["team_a"],
        away_membership_id=memberships["team_b"],
    )
    db_session.add(slot)
    db_session.commit()
    return slot


def _user_of(db_session: Session, team_id: str) -> UUID:
    return db_session.scalars(
        select(LeagueMembership.user_id)
        .join(FantasyTeam, FantasyTeam.membership_id == LeagueMembership.id)
        .where(FantasyTeam.id == UUID(team_id))
    ).one()


def _new_athlete_like(db_session: Session, athlete_id: UUID, *, provider_id: int) -> UUID:
    """Calciatore libero dello stesso ruolo e club (per una sostituzione dell'admin)."""
    assignment = db_session.scalars(
        select(RoleAssignment).where(RoleAssignment.athlete_id == athlete_id)
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
    db_session.commit()
    return newcomer.id


# -- scambio: formazione, bozza, punteggio ------------------------------------------------


def test_trade_removes_departed_players_from_future_lineup_draft_and_scoring(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="dep.scambio", id_offset=9_100_000
    )
    round_id, team_a, team_b = setup["round_id"], setup["team_a"], setup["team_b"]
    payload_a = _save_lineup(client, db_session, setup)
    # Bozza salvata dopo la formazione: stessi titolari, panchina rovesciata.
    draft_bench = list(reversed(payload_a["benchAthleteIds"]))
    _save_draft(client, setup, {**payload_a, "benchAthleteIds": draft_bench})
    payload_b = _save_lineup(client, db_session, setup, team="b")
    before = _submission(db_session, round_id, team_a)
    revision_before, submitted_at_before = before.revision, before.submitted_at

    # A cede un titolare (3° posto, un difensore) e il 4° della panchina (un difensore) per due
    # difensori di B che B teneva in tribuna.
    starter = UUID(payload_a["starterAthleteIds"][2])
    bench_player = UUID(payload_a["benchAthleteIds"][3])
    assert setup["role_of"][starter] == setup["role_of"][bench_player] == FantasyRole.D
    incoming = setup["roles_b"][FantasyRole.D][-2:]
    assert {str(item) for item in incoming} <= set(payload_b["benchAthleteIds"][10:])
    names = [_name(db_session, starter), _name(db_session, bench_player)]
    _trade(client, setup, offered=[starter, bench_player], requested=incoming)

    # Nel DB: il titolare esce e il suo posto resta (gli altri tengono la posizione); in
    # panchina gli altri restano nell'ordine, con le posizioni ricompattate.
    stored_a = _stored(db_session, round_id, team_a)
    assert _starters(stored_a) == _expected_starters(payload_a, starter)
    assert _bench(stored_a) == _expected_bench(payload_a["benchAthleteIds"], bench_player)
    draft = _draft(db_session, round_id, team_a)
    expected_draft_starters = list(payload_a["starterAthleteIds"])
    expected_draft_starters[2] = ""
    assert draft.starter_athlete_ids == expected_draft_starters
    assert draft.bench_athlete_ids == [item for item in draft_bench if item != str(bench_player)]
    # B perde dalla panchina i due difensori ceduti; i titolari non cambiano.
    stored_b = _stored(db_session, round_id, team_b)
    assert _starters(stored_b) == _expected_starters(payload_b)
    assert _bench(stored_b) == _expected_bench(payload_b["benchAthleteIds"], *incoming)

    # Pulizia di sistema: nessuna nuova revisione, nessuna mossa tattica, audit con il nome.
    after = _submission(db_session, round_id, team_a)
    assert after.revision == revision_before
    assert after.submitted_at == submitted_at_before
    assert (
        db_session.scalars(select(TacticalMove).where(TacticalMove.submission_id == after.id)).all()
        == []
    )
    audits = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(setup["league_id"]),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
        )
    ).all()
    departures = [
        row.details
        for row in audits
        if (row.details or {}).get("source") == DEPARTURE_SOURCE
        and row.details["fantasyTeamId"] == team_a
    ]
    assert sorted(item["athleteName"] for item in departures) == sorted(names)
    assert all(item["roundId"] == round_id for item in departures)
    assert all(item["tacticalMoveConsumed"] is False for item in departures)

    # GET formazione: avviso con i due nomi, posto vuoto tra i titolari, slot da riempire.
    body = client.get(_url(setup), headers=_headers(setup["token_a"])).json()
    assert body["issues"][0] == {
        "code": LEFT_ROSTER_CODE,
        "message": lineup_athlete_left_roster_message(names),
    }
    codes = {issue["code"] for issue in body["issues"]}
    assert "missing_athlete" in codes
    assert not codes & {"starter_count_invalid", "module_role_mismatch", "athlete_not_in_roster"}
    assert [player["sortOrder"] for player in body["lineup"]["starters"]] == [0, 1, *range(3, 11)]
    assert body["lineup"]["revision"] == revision_before
    assert body["tacticalMovesUsed"] == 0
    assert body["draft"]["starterAthleteIds"] == expected_draft_starters

    # Il turno si gioca senza un nuovo salvataggio: chi è uscito non conta per A.
    _close_round(
        db_session, round_id, started=datetime.now(UTC) - timedelta(hours=3), homologated=False
    )
    fielded = {
        UUID(item)
        for payload in (payload_a, payload_b)
        for item in (*payload["starterAthleteIds"], *payload["benchAthleteIds"])
    }
    scores = {athlete_id: 6.0 for athlete_id in fielded}
    scores[starter] = 40.0
    scores[bench_player] = 30.0
    _rate(db_session, setup, scores)
    slot = _h2h_slot(db_session, setup)
    compute_round_effective_lineups(db_session, round_id=UUID(round_id))
    db_session.commit()
    effective_a = db_session.scalars(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == UUID(round_id),
            EffectiveLineup.fantasy_team_id == UUID(team_a),
        )
    ).one()
    assert str(starter) not in effective_a.effective_starter_ids
    assert str(bench_player) not in effective_a.effective_starter_ids
    assert len(effective_a.effective_starter_ids) == 10
    compute_round_results(db_session, round_id=UUID(round_id))
    db_session.commit()
    db_session.refresh(slot)
    assert slot.home_score == pytest.approx(60.0)  # 10 titolari rimasti a 6
    assert slot.away_score == pytest.approx(66.0)  # B: i suoi 11, senza chi ha ricevuto


# -- svincolo, rimozione e sostituzione dell'admin ----------------------------------------


@pytest.mark.parametrize(
    ("exit_path", "id_offset"),
    [("svincolo", 9_200_000), ("rimozione_admin", 9_300_000), ("sostituzione_admin", 9_400_000)],
)
def test_release_removes_the_player_from_the_future_lineup(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    exit_path: str,
    id_offset: int,
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix=f"dep.{exit_path}", id_offset=id_offset
    )
    round_id, team_a, token = setup["round_id"], setup["team_a"], setup["token_a"]
    payload = _save_lineup(client, db_session, setup)
    _save_draft(client, setup, payload)
    # Un titolare per lo svincolo e la sostituzione, il 4° della panchina per la rimozione.
    if exit_path == "rimozione_admin":
        departed = UUID(payload["benchAthleteIds"][3])
    else:
        departed = UUID(payload["starterAthleteIds"][5])
    name = _name(db_session, departed)
    slot_index = _slot_index(db_session, team_a, departed)
    league_url = f"/leagues/{setup['league_id']}"
    admin_slot_url = f"{league_url}/amministrazione/squadre/{team_a}/slot/{slot_index}"

    if exit_path == "svincolo":
        response = client.post(
            f"{league_url}/mercato/svincolo/{slot_index}",
            headers=_headers(token),
            json={"reason": "voluntary", "athleteId": str(departed)},
        )
    elif exit_path == "rimozione_admin":
        response = client.delete(admin_slot_url, headers=_headers(token))
    else:
        newcomer = _new_athlete_like(db_session, departed, provider_id=id_offset + 9_999)
        response = client.put(
            admin_slot_url,
            headers=_headers(token),
            json={"athleteId": str(newcomer), "purchaseCredits": 1},
        )
    assert response.status_code == 200, response.json()

    stored = _stored(db_session, round_id, team_a)
    assert departed not in {athlete_id for _, _, athlete_id in stored}
    assert _starters(stored) == _expected_starters(payload, departed)
    assert _bench(stored) == _expected_bench(payload["benchAthleteIds"], departed)
    draft = _draft(db_session, round_id, team_a)
    assert str(departed) not in {*draft.starter_athlete_ids, *draft.bench_athlete_ids}
    if exit_path == "rimozione_admin":
        assert draft.starter_athlete_ids == payload["starterAthleteIds"]
    else:
        assert draft.starter_athlete_ids[5] == ""

    body = client.get(_url(setup), headers=_headers(token)).json()
    notices = [issue for issue in body["issues"] if issue["code"] == LEFT_ROSTER_CODE]
    assert notices == [
        {"code": LEFT_ROSTER_CODE, "message": lineup_athlete_left_roster_message([name])}
    ]


# -- turni bloccati o conclusi: la storia non cambia --------------------------------------


@pytest.mark.parametrize(
    ("closed_state", "exit_path", "id_offset"),
    [("concluso", "scambio", 9_500_000), ("bloccato", "svincolo", 9_600_000)],
)
def test_locked_or_finished_turn_lineup_is_untouched_by_a_later_departure(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    closed_state: str,
    exit_path: str,
    id_offset: int,
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix=f"dep.{closed_state}", id_offset=id_offset
    )
    team_a, token = setup["team_a"], setup["token_a"]
    first_round = setup["round_id"]
    payload = _save_lineup(client, db_session, setup)
    second_round = _add_future_round(
        db_session,
        setup,
        number=2,
        kickoff=datetime.now(UTC) + timedelta(days=9),
        provider_offset=id_offset + 60_000,
    )
    payload_second = _save_lineup(client, db_session, setup, round_id=second_round)
    departed = UUID(payload["starterAthleteIds"][2])
    assert str(departed) == payload_second["starterAthleteIds"][2]

    if closed_state == "concluso":
        # Turno giocato e omologato: il mercato è di nuovo aperto.
        _close_round(
            db_session,
            first_round,
            started=datetime.now(UTC) - timedelta(hours=3),
            homologated=True,
        )
    else:
        # Turno bloccato e mai omologato, finito da più di una settimana: il mercato non resta
        # chiuso per sempre (market.round_freeze.STUCK_ROUND_GRACE), ma il turno non si tocca.
        _close_round(
            db_session,
            first_round,
            started=datetime.now(UTC) - timedelta(days=9),
            homologated=False,
        )
    stored_first = _stored(db_session, first_round, team_a)
    assert departed in {athlete_id for _, _, athlete_id in stored_first}

    if exit_path == "scambio":
        _trade(client, setup, offered=[departed], requested=[setup["roles_b"][FantasyRole.D][-1]])
    else:
        slot_index = _slot_index(db_session, team_a, departed)
        released = client.post(
            f"/leagues/{setup['league_id']}/mercato/svincolo/{slot_index}",
            headers=_headers(token),
            json={"reason": "voluntary", "athleteId": str(departed)},
        )
        assert released.status_code == 200, released.json()

    assert _stored(db_session, first_round, team_a) == stored_first
    stored_second = _stored(db_session, second_round, team_a)
    assert _starters(stored_second) == _expected_starters(payload_second, departed)


def test_open_turn_already_started_is_untouched(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """A turno iniziato mercato e scambi sono chiusi; la pulizia comunque non lo toccherebbe."""
    from fantasy_lineups.departures import purge_departed_athlete_from_future_lineups

    setup = _trade_league(
        client, db_session, competition_ids, prefix="dep.iniziato", id_offset=9_700_000
    )
    round_id, team_a = setup["round_id"], setup["team_a"]
    payload = _save_lineup(client, db_session, setup)
    departed = UUID(payload["benchAthleteIds"][3])

    # Una partita del turno entro il margine di blocco (15 minuti): il turno è iniziato.
    fixture = _round_clubs(db_session, round_id)[0]
    fixture.kickoff_at = datetime.now(UTC) + timedelta(minutes=5)
    db_session.commit()
    proposal = client.post(
        f"/leagues/{setup['league_id']}/mercato/scambi/proposte",
        headers=_headers(setup["token_a"]),
        json={
            "recipientTeamId": setup["team_b"],
            "offeredAthleteIds": [str(departed)],
            "requestedAthleteIds": [str(setup["roles_b"][FantasyRole.D][-1])],
            "offeredCredits": 0,
            "requestedCredits": 0,
            "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        },
    )
    assert proposal.status_code == 400
    assert proposal.json()["code"] == "market_round_in_progress"

    # Un'uscita che non passa dal mercato (correzione diretta nel DB) e la pulizia chiamata a
    # mano: il turno è iniziato, la formazione resta com'è.
    slot = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_a),
            FantasyRosterSlot.athlete_id == departed,
        )
    ).one()
    slot.athlete_id = None
    slot.purchase_credits = None
    db_session.commit()
    stored_before = _stored(db_session, round_id, team_a)
    removed = purge_departed_athlete_from_future_lineups(
        db_session,
        league_id=UUID(setup["league_id"]),
        team_id=UUID(team_a),
        athlete_id=departed,
        now=datetime.now(UTC),
    )
    db_session.commit()
    assert removed == []
    assert _stored(db_session, round_id, team_a) == stored_before

    # Prima del primo blocco la stessa chiamata lo toglie.
    fixture = db_session.get(Fixture, fixture.id)
    fixture.kickoff_at = datetime.now(UTC) + timedelta(days=2)
    db_session.commit()
    removed = purge_departed_athlete_from_future_lineups(
        db_session,
        league_id=UUID(setup["league_id"]),
        team_id=UUID(team_a),
        athlete_id=departed,
        now=datetime.now(UTC),
    )
    db_session.commit()
    assert [item.round_id for item in removed] == [UUID(round_id)]
    assert _bench(_stored(db_session, round_id, team_a)) == _expected_bench(
        payload["benchAthleteIds"], departed
    )


# -- promemoria formazione ------------------------------------------------------------------


def test_lineup_with_a_hole_is_not_counted_as_deployed_by_the_reminder(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="dep.promemoria", id_offset=9_800_000
    )
    payload_a = _save_lineup(client, db_session, setup)
    _save_lineup(client, db_session, setup, team="b")
    starter = UUID(payload_a["starterAthleteIds"][2])
    _trade(client, setup, offered=[starter], requested=[setup["roles_b"][FantasyRole.D][-1]])

    LineupReminderService(db_session).send_due_reminders(now=datetime.now(UTC), window_hours=72)
    db_session.commit()

    def reminders(team_id: str) -> list[Notification]:
        return list(
            db_session.scalars(
                select(Notification).where(
                    Notification.user_id == _user_of(db_session, team_id),
                    Notification.category == NotificationCategory.FORMAZIONE,
                    Notification.dedup_key == f"lineup_reminder:{setup['round_id']}:{team_id}",
                )
            ).all()
        )

    # A ha un titolare in meno: va avvisato. B ha perso solo un panchinaro: è a posto.
    assert len(reminders(setup["team_a"])) == 1
    assert reminders(setup["team_b"]) == []
