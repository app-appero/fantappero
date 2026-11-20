# ruff: noqa: F811
"""Chi non ha un ruolo nel listone: contesto, copia, blocco e formazione automatica (20/11).

Seguito di ``test_role_unresolved_lineup.py`` (stessa rosa, stesso calciatore senza ruolo), in
un modulo a parte perché ogni lega di prova aggiunge tre partite al DB del modulo e da 25 in su
la creazione di una lega genera da sé il turno 1 (``min_fixtures_per_round``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_role_excess_lineup_payload import _stored_lineup_ids
from tests.integration.fantasy_lineups.test_role_unresolved_lineup import (
    FIRST_MIDFIELDER_SLOT,
    UNRESOLVED_NAME,
    _assert_roster_invalid_for_role_unresolved,
    _lose_role,
    _payload,
    _slot_athlete,
    _unresolved_team,
)
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_url,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import (
    FantasyModule,
    FantasyTurnKind,
    FantasyTurnStatus,
    LineupAutoResolutionSource,
)
from fantasy_lineups.fallback_service import ensure_lineup_submissions_for_round
from fantasy_lineups.models import LineupDraft, LineupSubmission
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.league_membership import LeagueMembership
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import SquadMembership


def test_context_drops_him_from_a_lineup_saved_when_he_still_had_a_role(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Formazione salvata con lui in tribuna quando il ruolo l'aveva: GET non lo restituisce né
    nella `roster` né nella tribuna, così la panchina di web e app coincide con quella salvata."""
    setup = _trade_league(
        client, db_session, competition_ids, prefix="sr.legacy", id_offset=7_590_000
    )
    unresolved_id = _slot_athlete(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT)
    payload = _payload(db_session, setup, unresolved_id, where="tribuna")
    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()
    assert str(unresolved_id) in _stored_lineup_ids(db_session, setup)

    _lose_role(db_session, unresolved_id)
    _assert_roster_invalid_for_role_unresolved(client, db_session, setup, unresolved_id)

    context = client.get(_lineup_url(setup), headers=_headers(setup["token_a"]))
    assert context.status_code == 200, context.json()
    body = context.json()
    assert str(unresolved_id) not in {row["athleteId"] for row in body["roster"]}
    bench = [item["athleteId"] for item in body["lineup"]["bench"]]
    assert bench == payload["benchAthleteIds"][:-1]
    assert {row["athleteId"] for row in body["roster"]} == {
        *payload["starterAthleteIds"],
        *bench,
    }
    assert body["issues"] == []
    # Rimandata senza di lui (come fanno web e app): identica, nessuna nuova revisione.
    without = {**payload, "benchAthleteIds": payload["benchAthleteIds"][:-1]}
    again = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=without)
    assert again.status_code == 200, again.json()
    assert again.json()["lineup"]["revision"] == saved.json()["lineup"]["revision"]


def test_copy_of_the_previous_lineup_excludes_him_by_name(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="sr.copia", id_offset=7_600_000
    )
    unresolved_id = _slot_athlete(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT)
    payload = _payload(db_session, setup, unresolved_id, where="starter")
    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()

    # Turno successivo aperto; nel frattempo lui perde il ruolo.
    now = datetime.now(UTC)
    next_round = FantasyRound(
        league_id=UUID(setup["league_id"]),
        number=2,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now + timedelta(days=6),
        window_end_at=now + timedelta(days=9),
        cutoff_at=now + timedelta(days=7),
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(next_round)
    db_session.commit()
    _lose_role(db_session, unresolved_id)
    _assert_roster_invalid_for_role_unresolved(client, db_session, setup, unresolved_id)
    next_url = f"/leagues/{setup['league_id']}/turni/{next_round.id}/formazione"

    copied = client.post(f"{next_url}/copia", headers=_headers(setup["token_a"]))

    assert copied.status_code == 200, copied.json()
    body = copied.json()
    draft = body["draft"]
    assert str(unresolved_id) not in {*draft["starterAthleteIds"], *draft["benchAthleteIds"]}
    assert {
        "code": "copied_athlete_role_unresolved",
        "message": (
            f"{UNRESOLVED_NAME} non ha un ruolo nel listone ed è stato escluso dalla formazione "
            "copiata."
        ),
    } in body["copyIssues"]
    assert "copied_athlete_not_in_roster" not in {issue["code"] for issue in body["copyIssues"]}


def test_fielded_and_locked_he_stays_in_the_lineup_of_the_current_turn(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Titolare confermato, partita iniziata, poi esce dal listone (resta la squadra del club
    ma senza una posizione riconosciuta): per questo turno vale il ruolo con cui è stato
    schierato, come per chi viene segnato in esubero a turno in corso."""
    setup = _trade_league(
        client, db_session, competition_ids, prefix="sr.bloccato", id_offset=7_610_000
    )
    unresolved_id = _slot_athlete(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT)
    payload = _payload(db_session, setup, unresolved_id, where="starter")
    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()

    assignment = db_session.scalars(
        select(RoleAssignment).where(RoleAssignment.athlete_id == unresolved_id)
    ).one()
    club_id = assignment.club_id
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
    db_session.add(
        SquadMembership(
            athlete_id=unresolved_id,
            club_id=club_id,
            sport_season_id=fixture.sport_season_id,
            provider_position_raw=None,
        )
    )
    db_session.commit()
    _lose_role(db_session, unresolved_id)
    _assert_roster_invalid_for_role_unresolved(client, db_session, setup, unresolved_id)

    again = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert again.status_code == 200, again.json()
    draft = client.put(
        f"{_lineup_url(setup)}/bozza", headers=_headers(setup["token_a"]), json=payload
    )
    assert draft.status_code == 200, draft.json()
    context = client.get(_lineup_url(setup), headers=_headers(setup["token_a"]))
    assert context.status_code == 200, context.json()
    body = context.json()
    assert "athlete_role_unresolved" not in {issue["code"] for issue in body["issues"]}
    assert str(unresolved_id) in [row["athleteId"] for row in body["lineup"]["starters"]]
    row = next(item for item in body["roster"] if item["athleteId"] == str(unresolved_id))
    assert row["role"] == "C"
    assert row["locked"] is True


def test_missing_lineup_is_taken_from_a_draft_without_him(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Formazione automatica al primo blocco: la bozza senza di lui è valida e si usa."""
    setup, unresolved_id = _unresolved_team(
        client, db_session, competition_ids, prefix="sr.automatica", id_offset=7_620_000
    )
    payload = _payload(db_session, setup, unresolved_id, where="tribuna")
    owner_id = db_session.scalars(
        select(LeagueMembership.user_id)
        .join(FantasyTeam, FantasyTeam.membership_id == LeagueMembership.id)
        .where(FantasyTeam.id == UUID(setup["team_a"]))
    ).one()
    # Bozza com'era prima di oggi (salvata senza passare dal server di oggi): lui in tribuna.
    db_session.add(
        LineupDraft(
            league_id=UUID(setup["league_id"]),
            round_id=UUID(setup["round_id"]),
            fantasy_team_id=UUID(setup["team_a"]),
            module=FantasyModule(payload["module"]),
            starter_athlete_ids=payload["starterAthleteIds"],
            bench_athlete_ids=payload["benchAthleteIds"],
            saved_at=datetime.now(UTC),
            saved_by_user_id=owner_id,
        )
    )
    db_session.commit()

    result = ensure_lineup_submissions_for_round(
        db_session,
        round_id=UUID(setup["round_id"]),
        league_id=UUID(setup["league_id"]),
        actor_id=None,
        team_ids={UUID(setup["team_a"])},
    )
    db_session.commit()

    assert result.resolved_from_draft == 1, result
    submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == UUID(setup["round_id"]),
            LineupSubmission.fantasy_team_id == UUID(setup["team_a"]),
        )
    ).one()
    assert submission.auto_resolution_source == LineupAutoResolutionSource.DRAFT
    stored = _stored_lineup_ids(db_session, setup)
    assert len(stored) == 34
    assert str(unresolved_id) not in stored
