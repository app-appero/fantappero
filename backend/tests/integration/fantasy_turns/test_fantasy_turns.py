"""Integration tests for european fantasy turn generation (EP06-01)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture


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


def _set_min_fixtures(db_session: Session, league_id: str, value: int) -> None:
    rules = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == UUID(league_id))
    ).one()
    rules.min_fixtures_per_round = value
    db_session.commit()


def _seed_weekend_fixtures(
    db_session: Session,
    competition_ids: list[str],
    *,
    count: int,
    kickoff: datetime,
    status_short: str = "NS",
    id_offset: int,
    league_id: str | None = None,
    clubs_offset: int | None = None,
) -> list[UUID]:
    # `clubs_offset` permette a più finestre di condividere gli stessi club:
    # serve quando un test genera più turni, perché la rosa ha 35 slot e
    # ogni set di club nuovo ne consumerebbe altri 11.
    club_base = id_offset if clubs_offset is None else clubs_offset
    clubs: list[Club] = []
    seasons: list[SportSeason] = []
    for i in range(count * 2):
        club = db_session.scalars(
            select(Club).where(Club.provider_id == club_base + i)
        ).first()
        if club is None:
            club = Club(provider_id=club_base + i, name=f"Club {club_base}-{i}")
            db_session.add(club)
        clubs.append(club)
    db_session.flush()

    fixture_ids: list[UUID] = []
    for i in range(count):
        competition_id = UUID(competition_ids[i % len(competition_ids)])
        season = db_session.scalars(
            select(SportSeason).where(
                SportSeason.competition_id == competition_id,
                SportSeason.year == 2026,
            )
        ).first()
        if season is None:
            season = SportSeason(
                competition_id=competition_id,
                year=2026,
                is_current=True,
            )
            db_session.add(season)
            db_session.flush()
        seasons.append(season)
        fixture = Fixture(
            provider_id=id_offset + 100_000 + i,
            sport_season_id=season.id,
            home_club_id=clubs[i * 2].id,
            away_club_id=clubs[i * 2 + 1].id,
            kickoff_at=kickoff + timedelta(minutes=i),
            status_short=status_short,
        )
        # First fixture keeps the shared kickoff for simultaneous-cutoff cases.
        if i == 0:
            fixture.kickoff_at = kickoff
        db_session.add(fixture)
        db_session.flush()
        fixture_ids.append(fixture.id)

    if league_id is not None:
        _stock_rosters_for_window(
            db_session,
            league_id=league_id,
            clubs=clubs,
            season=seasons[0],
            id_offset=id_offset,
        )

    db_session.commit()
    return fixture_ids


#: Formazione minima che copre gli 11 titolari con un 4-4-2.
_LINEUP_QUOTA = (("P", 1), ("D", 4), ("C", 4), ("A", 2))


def _stock_rosters_for_window(
    db_session: Session,
    *,
    league_id: str,
    clubs: list[Club],
    season: SportSeason,
    id_offset: int,
) -> None:
    """Dà a ogni squadra della lega 11 giocatori dei club di questa finestra.

    Dalla regola di copertura (EP-turni-copertura) un turno esiste solo se
    ogni fantallenatore può schierare la formazione: i test che generano
    turni devono quindi avere rose reali. È additivo — chiamandolo per più
    finestre la stessa rosa copre tutte quelle finestre.
    """
    from database.enums import FantasyRole
    from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
    from sports_data.catalog.models import CompetitionSeasonClub
    from sports_data.listone.models import RoleAssignment
    from sports_data.roster.models import Athlete

    for club in clubs:
        exists_link = db_session.scalars(
            select(CompetitionSeasonClub).where(
                CompetitionSeasonClub.sport_season_id == season.id,
                CompetitionSeasonClub.club_id == club.id,
            )
        ).first()
        if exists_link is None:
            db_session.add(
                CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id)
            )
    db_session.flush()

    teams = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).all()
    club_ids = {club.id for club in clubs}
    provider_id = id_offset + 500_000
    for team in teams:
        already = db_session.scalars(
            select(RoleAssignment.athlete_id)
            .join(FantasyRosterSlot, FantasyRosterSlot.athlete_id == RoleAssignment.athlete_id)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                RoleAssignment.club_id.in_(club_ids),
            )
        ).all()
        if len(already) >= 11:
            continue
        free_slots = list(
            db_session.scalars(
                select(FantasyRosterSlot)
                .where(
                    FantasyRosterSlot.fantasy_team_id == team.id,
                    FantasyRosterSlot.athlete_id.is_(None),
                )
                .order_by(FantasyRosterSlot.slot_index.asc())
            ).all()
        )
        cursor = 0
        for role_code, needed in _LINEUP_QUOTA:
            for _ in range(needed):
                if cursor >= len(free_slots):
                    break
                athlete = Athlete(
                    provider_id=provider_id, canonical_name=f"Player {provider_id}"
                )
                db_session.add(athlete)
                db_session.flush()
                db_session.add(
                    RoleAssignment(
                        athlete_id=athlete.id,
                        season_year=2026,
                        role=FantasyRole(role_code),
                        club_id=clubs[cursor % len(clubs)].id,
                        mapping_version="v1.0.0",
                        provider_position_raw=role_code,
                    )
                )
                free_slots[cursor].athlete_id = athlete.id
                provider_id += 1
                cursor += 1
    db_session.flush()


def test_generate_turn_success_and_permissions(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, _ = _register_and_login(client, "turn.admin@example.com")
    member_token, member_id = _register_and_login(client, "turn.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Turni")
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()
    _set_min_fixtures(db_session, league_id, 10)
    kickoff = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=12, kickoff=kickoff, id_offset=910_000
    , league_id=league_id)

    forbidden = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    # member has matchday:view via membership
    assert forbidden.status_code == 200

    preview = client.post(
        f"/leagues/{league_id}/turni/anteprima",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert preview.status_code == 200
    assert preview.json()["thresholdOk"] is True
    assert preview.json()["eligibleCount"] >= 10

    member_preview = client.post(
        f"/leagues/{league_id}/turni/anteprima",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert member_preview.status_code == 403

    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "scheduled"
    assert body["effectiveStatus"] == "scheduled"
    assert body["fixtureCount"] >= 10
    assert body["cutoffAt"] == kickoff.strftime("%Y-%m-%dT%H:%M:%S+00:00") or body[
        "cutoffAt"
    ].startswith("2026-08-15T14:00:00")
    assert body["modificationAllowed"] is True

    listed = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    member_recalc = client.post(
        f"/leagues/{league_id}/turni/{body['id']}/ricalcola-cutoff",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_recalc.status_code == 403


def test_generate_skipped_when_threshold_not_met(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.skip@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Skip")
    _set_min_fixtures(db_session, league_id, 40)
    kickoff = datetime(2026, 9, 12, 16, 0, tzinfo=UTC)  # Saturday in a fresh weekend
    _seed_weekend_fixtures(db_session, competition_ids, count=3, kickoff=kickoff, id_offset=920_000, league_id=league_id)

    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-09-12"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "skipped"
    assert body["skipReason"]
    # Sotto soglia per il fantasy, ma le partite reali già note devono
    # comunque comparire nel calendario (non un turno "vuoto").
    assert body["fixtureCount"] == 3


def test_exclude_before_open_and_reject_after_open(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.exclude@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Escludi")
    _set_min_fixtures(db_session, league_id, 10)
    today = datetime.now(UTC).date()
    days_until_saturday = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_until_saturday or 7)
    kickoff = datetime(saturday.year, saturday.month, saturday.day, 18, 0, tzinfo=UTC)
    fixture_ids = _seed_weekend_fixtures(
        db_session, competition_ids, count=12, kickoff=kickoff, id_offset=930_000
    , league_id=league_id)

    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": saturday.isoformat()},
    )
    assert created.status_code == 201
    round_id = created.json()["id"]
    fixture_id = str(fixture_ids[0])

    excluded = client.post(
        f"/leagues/{league_id}/turni/{round_id}/escludi-fixture",
        headers={"Authorization": f"Bearer {token}"},
        json={"fixtureId": fixture_id},
    )
    assert excluded.status_code == 200
    assert excluded.json()["fixtureCount"] == created.json()["fixtureCount"] - 1

    opened = client.post(
        f"/leagues/{league_id}/turni/{round_id}/apri",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert opened.status_code == 200
    assert opened.json()["status"] == "open"

    rejected = client.post(
        f"/leagues/{league_id}/turni/{round_id}/escludi-fixture",
        headers={"Authorization": f"Bearer {token}"},
        json={"fixtureId": str(fixture_ids[1])},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "turn_already_open"


def test_recalculate_cutoff_after_kickoff_change(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.cutoff@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Cutoff")
    _set_min_fixtures(db_session, league_id, 10)
    kickoff = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    fixture_ids = _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=kickoff, id_offset=940_000
    , league_id=league_id)

    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert created.status_code == 201
    round_id = created.json()["id"]
    assert created.json()["cutoffAt"].startswith("2026-08-15T12:00:00")

    fixture = db_session.get(Fixture, fixture_ids[0])
    assert fixture is not None
    fixture.kickoff_at = datetime(2026, 8, 15, 11, 30, tzinfo=UTC)
    db_session.commit()

    recalculated = client.post(
        f"/leagues/{league_id}/turni/{round_id}/ricalcola-cutoff",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recalculated.status_code == 200
    assert recalculated.json()["cutoffAt"].startswith("2026-08-15T11:30:00")

    detail = client.get(
        f"/leagues/{league_id}/turni/{round_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["cutoffAt"].startswith("2026-08-15T11:30:00")


def test_fixture_cannot_belong_to_two_active_turns(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.unique@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Unique")
    _set_min_fixtures(db_session, league_id, 10)
    kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=kickoff, id_offset=950_000
    , league_id=league_id)

    first = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert first.status_code == 201

    # Same window rejected as duplicate.
    duplicate = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] == "turn_window_exists"

    rounds = db_session.scalars(
        select(FantasyRound).where(FantasyRound.league_id == UUID(league_id))
    ).all()
    assert len(rounds) == 1


def test_ensure_sincronizza_creates_and_is_idempotent(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.ensure@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Ensure")
    _set_min_fixtures(db_session, league_id, 10)
    today = datetime.now(UTC).date()
    # Next Saturday within the default 14-day horizon.
    days_until_saturday = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_until_saturday or 7)
    kickoff = datetime(saturday.year, saturday.month, saturday.day, 15, 0, tzinfo=UTC)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=12, kickoff=kickoff, id_offset=960_000
    , league_id=league_id)

    first = client.post(
        f"/leagues/{league_id}/turni/sincronizza",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["created"] >= 1
    assert body["opened"] >= 1

    listed = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
    assert any(row["status"] == "open" for row in listed.json())

    second = client.post(
        f"/leagues/{league_id}/turni/sincronizza",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["duplicates"] >= 1


def test_recalculate_cutoff_does_not_move_later_after_elapsed_postponement(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.postpone@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Rinvii")
    _set_min_fixtures(db_session, league_id, 10)
    rome = ZoneInfo("Europe/Rome")
    first_kickoff_utc = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)
    first_kickoff_rome = datetime(2026, 10, 17, 18, 0, tzinfo=rome)
    assert first_kickoff_rome.astimezone(UTC) == first_kickoff_utc
    fixture_ids = _seed_weekend_fixtures(
        db_session,
        competition_ids,
        count=10,
        kickoff=first_kickoff_utc,
        id_offset=970_000,
        league_id=league_id,
    )
    simultaneous = db_session.get(Fixture, fixture_ids[1])
    assert simultaneous is not None
    simultaneous.kickoff_at = first_kickoff_rome
    db_session.commit()

    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-10-17"},
    )
    assert created.status_code == 201
    round_id = created.json()["id"]
    assert created.json()["cutoffAt"].startswith("2026-10-17T16:00:00")

    fixture = db_session.get(Fixture, fixture_ids[0])
    assert fixture is not None
    elapsed = datetime.now(UTC) - timedelta(minutes=5)
    fixture.kickoff_at = elapsed
    db_session.commit()

    detail = client.get(
        f"/leagues/{league_id}/turni/{round_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    latched_cutoff = detail.json()["cutoffAt"]
    fixtures_payload = detail.json()["fixtures"]
    first_row = next(row for row in fixtures_payload if row["fixtureId"] == str(fixture_ids[0]))
    assert first_row["lockLatchedAt"] is not None

    fixture = db_session.get(Fixture, fixture_ids[0])
    assert fixture is not None
    fixture.kickoff_at = datetime.now(UTC) + timedelta(days=2)
    fixture.status_short = "PST"
    db_session.commit()

    recalculated = client.post(
        f"/leagues/{league_id}/turni/{round_id}/ricalcola-cutoff",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recalculated.status_code == 200
    body = recalculated.json()
    assert body["cutoffAt"] == latched_cutoff
    postponed = next(row for row in body["fixtures"] if row["fixtureId"] == str(fixture_ids[0]))
    assert postponed["statusShort"] == "PST"
    assert postponed["lockLatchedAt"] is not None
    assert postponed["lockLatchedAt"] == first_row["lockLatchedAt"]
    postponed_day = (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%d")
    assert not body["cutoffAt"].startswith(postponed_day)

    db_session.expire_all()
    audit_rows = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_TURN_CUTOFF_RECALCULATED,
        )
    ).all()
    assert audit_rows
    assert any(row.details.get("latched") is True for row in audit_rows)
    assert any(row.details.get("fixtureChanges") for row in audit_rows)


def test_round_numbering_stays_chronological_when_generated_out_of_order(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Reproduces the "Nuova lega" bug: a later window generated first must not
    keep a lower number than an earlier window backfilled afterwards."""
    token, _ = _register_and_login(client, "turn.reorder@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Riordino")
    _set_min_fixtures(db_session, league_id, 10)

    later_kickoff = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)
    earlier_kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=later_kickoff, id_offset=985_000
    , league_id=league_id)
    _seed_weekend_fixtures(
        db_session, competition_ids, count=10, kickoff=earlier_kickoff, id_offset=986_000
    , league_id=league_id)

    # Generated out of order: the chronologically later window first.
    later = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-09-05"},
    )
    assert later.status_code == 201
    assert later.json()["number"] == 1  # only turn so far, insertion-order artifact

    earlier = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert earlier.status_code == 201

    listed = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 2
    # Sorted by number ascending (service orders by FantasyRound.number.asc()).
    assert rows[0]["number"] == 1
    assert rows[0]["id"] == earlier.json()["id"]
    assert rows[1]["number"] == 2
    assert rows[1]["id"] == later.json()["id"]

    # Fixtures/ids/homologation are untouched by the renumbering — only the
    # `number` field changes, same round identities as when created.
    earlier_detail = client.get(
        f"/leagues/{league_id}/turni/{earlier.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert earlier_detail.status_code == 200
    assert earlier_detail.json()["number"] == 1
    assert earlier_detail.json()["fixtureCount"] == earlier.json()["fixtureCount"]

    later_detail = client.get(
        f"/leagues/{league_id}/turni/{later.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert later_detail.status_code == 200
    assert later_detail.json()["number"] == 2
    assert later_detail.json()["fixtureCount"] == later.json()["fixtureCount"]

    # Re-running the idempotent sync must not reshuffle anything further.
    resync = client.post(
        f"/leagues/{league_id}/turni/sincronizza",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resync.status_code == 200
    stable = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert [row["number"] for row in stable] == [1, 2]


def _owned_fixture_rows(payload: dict, fixture_ids: list[UUID]) -> list[dict]:
    wanted = {str(item) for item in fixture_ids}
    return [row for row in payload["fixtures"] if row["fixtureId"] in wanted]


def test_kickoff_time_shift_before_elapsed_can_delay_cutoff(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.timeshift.before@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Orario Prima")
    _set_min_fixtures(db_session, league_id, 10)
    first_kickoff = datetime(2026, 11, 7, 16, 0, tzinfo=UTC)
    fixture_ids = _seed_weekend_fixtures(
        db_session,
        competition_ids,
        count=10,
        kickoff=first_kickoff,
        id_offset=980_000,
        league_id=league_id,
    )

    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-11-07"},
    )
    assert created.status_code == 201
    round_id = created.json()["id"]
    assert created.json()["cutoffAt"].startswith("2026-11-07T16:00:00")

    db_session.expire_all()
    for fixture_id in fixture_ids:
        fixture = db_session.get(Fixture, fixture_id)
        assert fixture is not None
        assert fixture.kickoff_at is not None
        fixture.kickoff_at = fixture.kickoff_at + timedelta(hours=2)
        fixture.status_short = "NS"
    db_session.commit()

    recalculated = client.post(
        f"/leagues/{league_id}/turni/{round_id}/ricalcola-cutoff",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recalculated.status_code == 200
    body = recalculated.json()
    ours = _owned_fixture_rows(body, fixture_ids)
    assert len(ours) == 10
    assert body["cutoffAt"].startswith("2026-11-07T18:00:00")
    assert all(row["lockLatchedAt"] is None for row in ours)


def test_kickoff_time_shift_after_elapsed_does_not_reopen(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.timeshift.after@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Orario Dopo")
    _set_min_fixtures(db_session, league_id, 10)
    first_kickoff = datetime(2026, 11, 14, 16, 0, tzinfo=UTC)
    fixture_ids = _seed_weekend_fixtures(
        db_session,
        competition_ids,
        count=10,
        kickoff=first_kickoff,
        id_offset=981_000,
        league_id=league_id,
    )
    created = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-11-14"},
    )
    assert created.status_code == 201
    round_id = created.json()["id"]

    elapsed = datetime.now(UTC) - timedelta(minutes=5)
    db_session.expire_all()
    for index, fixture_id in enumerate(fixture_ids):
        fixture = db_session.get(Fixture, fixture_id)
        assert fixture is not None
        fixture.kickoff_at = elapsed + timedelta(seconds=index)
        fixture.status_short = "NS"
    db_session.commit()

    detail = client.get(
        f"/leagues/{league_id}/turni/{round_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    latched_cutoff = detail.json()["cutoffAt"]
    ours = _owned_fixture_rows(detail.json(), fixture_ids)
    assert len(ours) == 10
    assert all(row["lockLatchedAt"] is not None for row in ours)

    later = datetime.now(UTC) + timedelta(days=2)
    db_session.expire_all()
    for fixture_id in fixture_ids:
        fixture = db_session.get(Fixture, fixture_id)
        assert fixture is not None
        fixture.kickoff_at = later
        fixture.status_short = "NS"
    db_session.commit()

    recalculated = client.post(
        f"/leagues/{league_id}/turni/{round_id}/ricalcola-cutoff",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recalculated.status_code == 200
    body = recalculated.json()
    ours_after = _owned_fixture_rows(body, fixture_ids)
    assert body["cutoffAt"] == latched_cutoff
    assert all(row["lockLatchedAt"] is not None for row in ours_after)
    assert not body["cutoffAt"].startswith(later.strftime("%Y-%m-%d"))


def test_ensure_sincronizza_reconciles_existing_cutoff_after_time_change(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "turn.ensure.recalc@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Sync Orari")
    _set_min_fixtures(db_session, league_id, 10)
    today = datetime.now(UTC).date()
    days_until_saturday = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_until_saturday or 7)
    kickoff = datetime(saturday.year, saturday.month, saturday.day, 15, 0, tzinfo=UTC)
    fixture_ids = _seed_weekend_fixtures(
        db_session, competition_ids, count=12, kickoff=kickoff, id_offset=982_000
    , league_id=league_id)
    target_id = str(fixture_ids[0])

    synced = client.post(
        f"/leagues/{league_id}/turni/sincronizza",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert synced.status_code == 200
    listed = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200

    round_id = None
    original_cutoff = None
    for row in listed.json():
        if row["status"] == "skipped":
            continue
        detail = client.get(
            f"/leagues/{league_id}/turni/{row['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        if any(item["fixtureId"] == target_id for item in detail.json()["fixtures"]):
            round_id = row["id"]
            original_cutoff = detail.json()["cutoffAt"]
            break
    assert round_id is not None
    assert original_cutoff is not None

    original_dt = datetime.fromisoformat(original_cutoff.replace("Z", "+00:00"))
    earlier = original_dt - timedelta(minutes=30)
    db_session.expire_all()
    fixture = db_session.get(Fixture, fixture_ids[0])
    assert fixture is not None
    fixture.kickoff_at = earlier
    fixture.status_short = "NS"
    db_session.commit()

    again = client.post(
        f"/leagues/{league_id}/turni/sincronizza",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["duplicates"] >= 1

    listed_after = client.get(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed_after.status_code == 200
    weekend_after = next(row for row in listed_after.json() if row["id"] == round_id)
    assert weekend_after["cutoffAt"].startswith(earlier.strftime("%Y-%m-%dT%H:%M:%S"))


def test_prune_invalid_rounds_removes_phantom_turns_and_renumbers(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Turni "Non disputato" senza nessuna fixture reale — residuo di
    sincronizzazioni precedenti alla correzione che smette di materializzare
    finestre vuote — vengono rimossi, e i numeri restanti si richiudono senza
    buchi (EP-turni-numerazione: "mi ritrovo con 86 turni")."""
    from fantasy_turns.models import FantasyRoundFixture
    from fantasy_turns.service import FantasyTurnService
    from database.enums import LeagueState
    from database.enums import FantasyRoundFixtureReason, FantasyTurnKind, FantasyTurnStatus
    from leagues.models.league import League

    from fantasy_teams.factory import ensure_team_for_membership
    from leagues.models.league_competition import LeagueCompetition

    token, user_id = _register_and_login(client, "turn.phantom@example.com")
    league = League(name="Lega Turni Fantasma", season_year=2026, state=LeagueState.ACTIVE)
    db_session.add(league)
    db_session.flush()
    for competition_id in competition_ids:
        db_session.add(
            LeagueCompetition(league_id=league.id, competition_id=UUID(competition_id))
        )
    membership = LeagueMembership(
        league_id=league.id, user_id=user_id, role=LeagueMemberRole.OWNER
    )
    db_session.add(membership)
    db_session.flush()
    # Serve una rosa reale: con la regola di copertura un turno sopravvive
    # alla potatura solo se il fantallenatore può schierare la formazione.
    ensure_team_for_membership(db_session, membership, name="Squadra Fantasma")
    db_session.flush()

    now = datetime.now(UTC)

    def make_round(number: int, start_offset_days: int, has_fixture: bool) -> FantasyRound:
        start = datetime(2026, 8, 14, 22, 0, tzinfo=UTC) + timedelta(days=start_offset_days)
        row = FantasyRound(
            league_id=league.id,
            number=number,
            kind=FantasyTurnKind.WEEKEND,
            window_start_at=start,
            window_end_at=start + timedelta(days=4),
            status=FantasyTurnStatus.SKIPPED,
            skip_reason="Soglia non raggiunta: test.",
            generated_at=now,
        )
        db_session.add(row)
        db_session.flush()
        if has_fixture:
            fixture_ids = _seed_weekend_fixtures(
                db_session,
                competition_ids,
                count=1,
                kickoff=start + timedelta(hours=16),
                id_offset=999_000 + number * 10,
                league_id=str(league.id),
            )
            db_session.add(
                FantasyRoundFixture(
                    round_id=row.id,
                    league_id=league.id,
                    fixture_id=fixture_ids[0],
                    included_reason=FantasyRoundFixtureReason.WINDOW,
                )
            )
            db_session.flush()
        return row

    real_1 = make_round(1, 0, has_fixture=True)
    phantom_1 = make_round(2, 4, has_fixture=False)
    phantom_2 = make_round(3, 7, has_fixture=False)
    real_2 = make_round(4, 11, has_fixture=True)
    db_session.commit()

    service = FantasyTurnService(db_session)
    removed = service._prune_invalid_rounds(league)
    assert removed == 2
    service._renumber_league_rounds(league.id)
    db_session.commit()

    remaining = db_session.scalars(
        select(FantasyRound)
        .where(FantasyRound.league_id == league.id)
        .order_by(FantasyRound.number.asc())
    ).all()
    assert [row.id for row in remaining] == [real_1.id, real_2.id]
    assert [row.number for row in remaining] == [1, 2]
    assert db_session.get(FantasyRound, phantom_1.id) is None
    assert db_session.get(FantasyRound, phantom_2.id) is None
