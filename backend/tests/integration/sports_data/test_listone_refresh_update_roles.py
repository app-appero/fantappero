"""«Aggiorna listone» dal pannello operatore: ruoli congelati o anche dal fornitore (22/11).

Scelta di Rosario: di default l'aggiornamento aggiunge i nuovi calciatori e aggiorna le
squadre, i ruoli di chi c'è già restano. «Aggiorna anche i ruoli dal fornitore» mostra prima
l'anteprima di chi cambierebbe ruolo; i ruoli cambiano solo dopo la conferma.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.sports_data.test_roster_loan_return import (
    NAPOLI,
    SEASON,
    SERIE_A,
    _athlete,
    _FakeProvider,
    _players,
    _seed_catalog,
    _squad,
)

from admin.listone_roles_service import AdminListoneRolesService
from admin.listone_service import refresh_platform_listone
from auth.models.user import User
from database.enums import FantasyRole, LeagueAuditAction, PlatformRole, UserType
from leagues.models.league_audit_event import LeagueAuditEvent
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership, Transfer

MID = 920_001
KEEPER = 920_002
NEWCOMER = 920_003


@pytest.fixture(autouse=True)
def clean_tables(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    session.execute(delete(LeagueRoleOverride))
    session.execute(delete(RoleAssignment))
    session.execute(delete(SquadMembership))
    session.execute(delete(Transfer))
    session.execute(delete(Athlete))
    session.commit()
    # Catalogo già in DB (`_seed_catalog`): l'aggiornamento non lo richiede al fornitore.
    monkeypatch.setattr("admin.listone_service.sync_mvp_catalog_with_client", lambda *_a: None)


def _provider(players: list[tuple[int, str, str]]) -> _FakeProvider:
    return _FakeProvider(
        squads={NAPOLI[0]: _squad(NAPOLI, players)},
        players={NAPOLI[0]: _players(NAPOLI, SERIE_A, players)},
        transfers={},
    )


def _refresh(session: Session, provider: _FakeProvider, *, update_roles: bool = False):
    result = refresh_platform_listone(
        session,
        season_year=SEASON,
        client=provider,  # type: ignore[arg-type]
        update_roles=update_roles,
    )
    session.commit()
    return result


def _role(session: Session, provider_id: int) -> FantasyRole:
    session.expire_all()
    return session.execute(
        select(RoleAssignment.role).where(
            RoleAssignment.athlete_id == _athlete(session, provider_id).id,
            RoleAssignment.season_year == SEASON,
        )
    ).scalar_one()


def _operator(session: Session) -> User:
    user = User(
        email=f"listone-ruoli-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        platform_role=PlatformRole.OPERATOR,
        user_type=UserType.HUMAN,
    )
    session.add(user)
    session.commit()
    return user


def _seeded(session: Session) -> _FakeProvider:
    _seed_catalog(session)
    _refresh(
        session,
        _provider([(MID, "M. Mezzala", "Midfielder"), (KEEPER, "P. Portiere", "Goalkeeper")]),
    )
    assert _role(session, MID) == FantasyRole.C
    # Ora il fornitore dà attaccante il centrocampista e arriva un difensore nuovo.
    return _provider(
        [
            (MID, "M. Mezzala", "Attacker"),
            (KEEPER, "P. Portiere", "Goalkeeper"),
            (NEWCOMER, "N. Arrivato", "Defender"),
        ]
    )


def test_default_refresh_adds_new_players_and_keeps_the_roles(session: Session) -> None:
    provider = _seeded(session)

    result = _refresh(session, provider)

    assert _role(session, MID) == FantasyRole.C
    assert _role(session, NEWCOMER) == FantasyRole.D
    assert result.counters.listone_created == 1
    assert result.counters.role_changes_skipped == 1
    assert result.role_changes is None
    assert result.model_dump(by_alias=True)["counters"]["roleChangesSkipped"] == 1


def test_update_roles_previews_the_changes_without_applying_them(session: Session) -> None:
    provider = _seeded(session)

    result = _refresh(session, provider, update_roles=True)

    assert result.role_changes is not None
    preview = result.role_changes
    assert preview.dry_run is True
    assert [(e.name, e.club, e.current_role, e.new_role) for e in preview.entries] == [
        ("M. Mezzala", "Napoli", "C", "A")
    ]
    assert preview.counts.changes == 1
    assert preview.counts.applied == 0
    assert "conferma" in result.message
    # Anteprima soltanto: ruolo invariato, nuovi calciatori aggiunti come sempre.
    assert _role(session, MID) == FantasyRole.C
    assert _role(session, NEWCOMER) == FantasyRole.D
    # Il risultato del job (salvato come JSON) porta l'anteprima.
    dumped = result.model_dump(by_alias=True, mode="json")
    assert dumped["roleChanges"]["entries"][0]["newRole"] == "A"


def test_confirm_applies_the_previewed_roles_and_resyncs_the_rosters(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _seeded(session)
    preview = _refresh(session, provider, update_roles=True).role_changes
    assert preview is not None
    operator = _operator(session)
    resynced: list[tuple[set[UUID], int | None]] = []

    def fake_resync(_session, *, athlete_ids, season_year=None, league_id=None):
        resynced.append((set(athlete_ids), season_year))
        return 3

    monkeypatch.setattr("admin.listone_roles_service.resync_team_compositions", fake_resync)
    service = AdminListoneRolesService(session)
    applied = service.provider_roles(
        actor=operator,
        season_year=SEASON,
        dry_run=False,
        athlete_ids=[entry.athlete_id for entry in preview.entries],
    )
    session.commit()

    assert applied.counts.applied == 1
    assert applied.counts.rosters_resynced == 3
    assert _role(session, MID) == FantasyRole.A
    assert resynced == [({_athlete(session, MID).id}, SEASON)]
    audit = session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.actor_id == operator.id,
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_LISTONE_REFRESHED,
        )
    ).all()
    assert len(audit) == 1
    assert audit[0].details is not None
    assert audit[0].details["operation"] == "listone_roles_from_provider"

    # Idempotente: confermare di nuovo non trova più differenze.
    again = service.provider_roles(actor=operator, season_year=SEASON, dry_run=False)
    session.commit()
    assert again.counts.changes == 0
    assert again.counts.applied == 0
    assert len(resynced) == 1
    # E il prossimo aggiornamento di default tiene il ruolo nuovo.
    assert _refresh(session, provider).counters.role_changes_skipped == 0
    assert _role(session, MID) == FantasyRole.A


def test_confirm_only_applies_the_previewed_athletes(session: Session) -> None:
    provider = _seeded(session)
    _refresh(session, provider)
    operator = _operator(session)

    applied = AdminListoneRolesService(session).provider_roles(
        actor=operator,
        season_year=SEASON,
        dry_run=False,
        athlete_ids=[],
    )
    session.commit()

    assert applied.counts.changes == 1
    assert applied.counts.applied == 0
    assert _role(session, MID) == FantasyRole.C
