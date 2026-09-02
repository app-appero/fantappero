"""Integration tests for the missing-lineup fallback (EP-turni-calcolo)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyModule, LineupSlotKind
from database.session import create_session_factory
from fantasy_lineups.fallback_service import ensure_lineup_submissions_for_round
from fantasy_lineups.models import LineupDraft, LineupSubmission
from fantasy_teams.models import FantasyTeam
from leagues.models.competition import Competition
from tests.integration.fantasy_lineups.test_fantasy_lineups import (
    _create_league,
    _create_open_round,
    _fill_validated_roster,
    _lineup_payload,
    _register_and_login,
    _seed_roster_athletes,
)


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


def _team_id(db_session: Session, league_id: str) -> UUID:
    return db_session.scalars(
        select(FantasyTeam.id).where(FantasyTeam.league_id == UUID(league_id))
    ).one()


def _submission(db_session: Session, round_id: UUID, team_id: UUID) -> LineupSubmission | None:
    return db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == team_id,
        )
    ).one_or_none()


def test_leaves_a_team_with_a_real_submission_untouched(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "fallback.has-submission@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Fallback Con Formazione")
    grouped = _seed_roster_athletes(db_session, id_offset=4_800_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=2),
        id_offset=4_810_000,
        competition_ids=competition_ids,
    )
    response = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=_lineup_payload(athletes),
    )
    assert response.status_code == 200, response.text

    team_id = _team_id(db_session, league_id)
    before = _submission(db_session, fantasy_round.id, team_id)
    assert before is not None
    assert before.auto_resolution_source is None

    result = ensure_lineup_submissions_for_round(
        db_session, round_id=fantasy_round.id, league_id=UUID(league_id), actor_id=None
    )
    db_session.commit()

    assert result.total_resolved == 0
    after = _submission(db_session, fantasy_round.id, team_id)
    assert after is not None
    assert after.id == before.id
    assert after.auto_resolution_source is None


def test_resolves_from_a_valid_draft(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, user_id = _register_and_login(client, "fallback.draft@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Fallback Bozza")
    grouped = _seed_roster_athletes(db_session, id_offset=4_820_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=2),
        id_offset=4_830_000,
        competition_ids=competition_ids,
    )
    team_id = _team_id(db_session, league_id)
    payload = _lineup_payload(athletes)

    draft = LineupDraft(
        league_id=UUID(league_id),
        round_id=fantasy_round.id,
        fantasy_team_id=team_id,
        module=FantasyModule.M433,
        starter_athlete_ids=payload["starterAthleteIds"],
        bench_athlete_ids=payload["benchAthleteIds"],
        saved_at=datetime.now(UTC),
        saved_by_user_id=user_id,
    )
    db_session.add(draft)
    db_session.commit()

    result = ensure_lineup_submissions_for_round(
        db_session, round_id=fantasy_round.id, league_id=UUID(league_id), actor_id=None
    )
    db_session.commit()

    assert result.resolved_from_draft == 1
    assert result.resolved_from_previous_round == 0
    assert result.resolved_as_zero == 0

    submission = _submission(db_session, fantasy_round.id, team_id)
    assert submission is not None
    assert submission.auto_resolution_source is not None
    assert submission.auto_resolution_source.value == "draft"
    starters = [
        str(row.athlete_id)
        for row in sorted(
            (row for row in submission.players if row.slot_kind == LineupSlotKind.STARTER),
            key=lambda row: row.sort_order,
        )
    ]
    assert starters == payload["starterAthleteIds"]


def test_falls_through_from_an_incomplete_draft_to_zero(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, user_id = _register_and_login(client, "fallback.incomplete-draft@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Fallback Bozza Incompleta")
    grouped = _seed_roster_athletes(db_session, id_offset=4_840_000)
    _fill_validated_roster(db_session, league_id, grouped)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=2),
        id_offset=4_850_000,
        competition_ids=competition_ids,
    )
    team_id = _team_id(db_session, league_id)

    # Bozza con soli 3 titolari: mai confermabile, non c'è nessuna formazione
    # precedente da usare in alternativa -> deve ricadere sullo zero.
    incomplete_starters = [str(athlete.id) for athlete in grouped["D"][:3]]
    draft = LineupDraft(
        league_id=UUID(league_id),
        round_id=fantasy_round.id,
        fantasy_team_id=team_id,
        module=FantasyModule.M433,
        starter_athlete_ids=incomplete_starters,
        bench_athlete_ids=[],
        saved_at=datetime.now(UTC),
        saved_by_user_id=user_id,
    )
    db_session.add(draft)
    db_session.commit()

    result = ensure_lineup_submissions_for_round(
        db_session, round_id=fantasy_round.id, league_id=UUID(league_id), actor_id=None
    )
    db_session.commit()

    assert result.resolved_from_draft == 0
    assert result.resolved_from_previous_round == 0
    assert result.resolved_as_zero == 1

    submission = _submission(db_session, fantasy_round.id, team_id)
    assert submission is not None
    assert submission.auto_resolution_source is not None
    assert submission.auto_resolution_source.value == "zero_fallback"
    assert submission.players == []


def test_resolves_from_the_previous_round_when_there_is_no_draft(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "fallback.previous@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Fallback Precedente")
    grouped = _seed_roster_athletes(db_session, id_offset=4_860_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    round1, _clubs1 = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=1),
        id_offset=4_870_000,
        competition_ids=competition_ids,
        number=1,
    )
    payload = _lineup_payload(athletes)
    submit = client.put(
        f"/leagues/{league_id}/turni/{round1.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert submit.status_code == 200, submit.text

    round2, _clubs2 = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=2),
        id_offset=4_880_000,
        competition_ids=competition_ids,
        number=2,
    )
    team_id = _team_id(db_session, league_id)
    assert _submission(db_session, round2.id, team_id) is None

    result = ensure_lineup_submissions_for_round(
        db_session, round_id=round2.id, league_id=UUID(league_id), actor_id=None
    )
    db_session.commit()

    assert result.resolved_from_draft == 0
    assert result.resolved_from_previous_round == 1
    assert result.resolved_as_zero == 0

    submission = _submission(db_session, round2.id, team_id)
    assert submission is not None
    assert submission.auto_resolution_source is not None
    assert submission.auto_resolution_source.value == "previous_round"
    starters = [
        str(row.athlete_id)
        for row in sorted(
            (row for row in submission.players if row.slot_kind == LineupSlotKind.STARTER),
            key=lambda row: row.sort_order,
        )
    ]
    assert starters == payload["starterAthleteIds"]


def test_falls_to_zero_when_no_draft_and_no_previous_lineup_exist(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "fallback.nothing@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Fallback Nulla")
    grouped = _seed_roster_athletes(db_session, id_offset=4_890_000)
    _fill_validated_roster(db_session, league_id, grouped)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=2),
        id_offset=4_900_000,
        competition_ids=competition_ids,
    )
    team_id = _team_id(db_session, league_id)

    result = ensure_lineup_submissions_for_round(
        db_session, round_id=fantasy_round.id, league_id=UUID(league_id), actor_id=None
    )
    db_session.commit()

    assert result.resolved_as_zero == 1
    submission = _submission(db_session, fantasy_round.id, team_id)
    assert submission is not None
    assert submission.auto_resolution_source is not None
    assert submission.auto_resolution_source.value == "zero_fallback"
    assert submission.players == []
    assert submission.module is not None  # colonna NOT NULL, valore placeholder atteso
