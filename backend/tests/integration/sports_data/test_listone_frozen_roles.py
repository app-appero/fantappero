"""Ruoli ufficiali congelati per la stagione e membership del club attuale (Rosario 22/11).

Pilota, 21/11 ore 15 circa: «Aggiorna listone» (con la correzione dei rientri dal prestito)
ha cambiato il ruolo ufficiale di diversi calciatori già nelle rose (C→A, A→C) e le rose
complete e valide sono finite fuori quota. Due cause nel listone:

1. ``_upsert_assignment`` riscriveva il ruolo a ogni aggiornamento con la posizione del
   fornitore di quel momento;
2. con più membership attive nella stagione vinceva la più recente: la correzione dei
   prestiti riattiva anche la membership del club lasciato prima dell'inizio della stagione
   se il fornitore lo elenca ancora lì, e la riattivazione la rende la più recente.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.sports_data.test_roster_loan_return import (
    LAZIO,
    NAPOLI,
    SEASON,
    SERIE_A,
    _athlete,
    _club,
    _FakeProvider,
    _membership,
    _players,
    _seed_catalog,
    _squad,
    _transfers,
)

from database.enums import FantasyRole
from sports_data.listone.generate import (
    _active_memberships_for_season,
    _pick_membership_per_athlete,
    generate_official_listone,
)
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.roster.sync import sync_mvp_roster_with_client

MID = 910_001
NEWCOMER = 910_002
MOVED = 910_003
MATE = 910_004


@pytest.fixture(autouse=True)
def clean_tables(session: Session) -> None:
    session.execute(delete(LeagueRoleOverride))
    session.execute(delete(RoleAssignment))
    session.execute(delete(SquadMembership))
    session.execute(delete(Transfer))
    session.execute(delete(Athlete))
    session.commit()


def _refresh(session: Session, provider: _FakeProvider):
    sync_mvp_roster_with_client(
        session,
        provider,  # type: ignore[arg-type]
        season_year=SEASON,
        store_snapshots=False,
    )
    result = generate_official_listone(session, season_year=SEASON)
    session.commit()
    return result


def _assignment(session: Session, provider_id: int) -> RoleAssignment:
    row = session.execute(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == _athlete(session, provider_id).id,
            RoleAssignment.season_year == SEASON,
        )
    ).scalar_one()
    session.refresh(row)
    return row


def _napoli(players: list[tuple[int, str, str]]) -> _FakeProvider:
    return _FakeProvider(
        squads={NAPOLI[0]: _squad(NAPOLI, players)},
        players={NAPOLI[0]: _players(NAPOLI, SERIE_A, players)},
        transfers={},
    )


def test_refresh_keeps_the_role_of_a_player_already_in_the_listone(session: Session) -> None:
    _seed_catalog(session)
    first = _refresh(session, _napoli([(MID, "M. Mezzala", "Midfielder")]))
    assert first.counters.created == 1
    assert _assignment(session, MID).role == FantasyRole.C

    # Il fornitore ora lo dà attaccante (rosa e statistiche) e arriva un difensore nuovo.
    provider = _napoli(
        [(MID, "M. Mezzala", "Attacker"), (NEWCOMER, "N. Arrivato", "Defender")],
    )
    second = _refresh(session, provider)

    kept = _assignment(session, MID)
    assert kept.role == FantasyRole.C
    assert kept.provider_position_raw == "Midfielder"
    assert second.counters.role_changes_skipped == 1
    assert second.counters.updated == 0
    assert second.counters.created == 1
    assert _assignment(session, NEWCOMER).role == FantasyRole.D
    # Solo il nuovo arrivato tocca le rose: il ruolo di chi c'era non è cambiato.
    assert second.affected_athlete_ids == {_athlete(session, NEWCOMER).id}

    # Ogni aggiornamento successivo conta di nuovo la differenza, senza applicarla.
    third = _refresh(session, provider)
    assert third.counters.role_changes_skipped == 1
    assert third.counters.unchanged == 2
    assert third.affected_athlete_ids == set()
    assert _assignment(session, MID).role == FantasyRole.C


def test_frozen_role_still_follows_the_club_of_a_transfer(session: Session) -> None:
    _seed_catalog(session)
    _refresh(session, _napoli([(MOVED, "T. Ceduto", "Midfielder")]))
    assert _assignment(session, MOVED).role == FantasyRole.C

    # Ceduto alla Lazio a stagione iniziata: alla Lazio il fornitore lo dà attaccante.
    sale = _transfers(MOVED, "T. Ceduto", [("2026-09-01", "Transfer", NAPOLI, LAZIO)])
    provider = _FakeProvider(
        squads={
            NAPOLI[0]: _squad(NAPOLI, [(MATE, "C. Compagno", "Defender")]),
            LAZIO[0]: _squad(LAZIO, [(MOVED, "T. Ceduto", "Attacker")]),
        },
        players={},
        transfers={NAPOLI[0]: sale, LAZIO[0]: sale},
    )
    result = _refresh(session, provider)

    moved = _assignment(session, MOVED)
    assert moved.club_id == _club(session, LAZIO[0]).id
    assert moved.role == FantasyRole.C
    assert moved.provider_position_raw == "Midfielder"
    assert result.counters.role_changes_skipped == 1
    assert _athlete(session, MOVED).id in result.affected_athlete_ids


def test_pick_prefers_the_current_club_over_a_reactivated_stale_membership(
    session: Session,
) -> None:
    """Il meccanismo del 21/11: ceduto dal Napoli alla Lazio a luglio, prima dell'inizio
    della Serie A; il Napoli lo elenca ancora in rosa (dato in ritardo) come centrocampista,
    la Lazio come attaccante. Con la correzione dei prestiti la membership del Napoli resta
    attiva e, appena riattivata, è la più recente."""
    _seed_catalog(session)
    sale = _transfers(MOVED, "T. Ceduto", [("2026-07-20", "Transfer", NAPOLI, LAZIO)])
    provider = _FakeProvider(
        squads={
            NAPOLI[0]: _squad(NAPOLI, [(MOVED, "T. Ceduto", "Midfielder")]),
            LAZIO[0]: _squad(LAZIO, [(MOVED, "T. Ceduto", "Attacker")]),
        },
        players={},
        transfers={NAPOLI[0]: sale, LAZIO[0]: sale},
    )
    sync_mvp_roster_with_client(
        session,
        provider,  # type: ignore[arg-type]
        season_year=SEASON,
        store_snapshots=False,
    )
    stale = _membership(session, MOVED, NAPOLI[0])
    current = _membership(session, MOVED, LAZIO[0])
    assert stale is not None and stale.is_active
    assert current is not None and current.is_active
    # Come la riattivazione del 21/11: la membership del club lasciato è la più recente.
    stale.updated_at = datetime.now(UTC) + timedelta(minutes=5)
    session.commit()

    memberships = _active_memberships_for_season(session, SEASON)
    athlete_id = _athlete(session, MOVED).id
    # Prima della correzione: vinceva la più recente, cioè il club lasciato.
    assert _pick_membership_per_athlete(memberships)[athlete_id].club_id == stale.club_id

    generate_official_listone(session, season_year=SEASON)
    session.commit()
    assignment = _assignment(session, MOVED)
    assert assignment.club_id == _club(session, LAZIO[0]).id
    assert assignment.role == FantasyRole.A
    assert assignment.squad_membership_id == current.id


def test_pick_prefers_the_provider_squad_over_a_players_only_membership(
    session: Session,
) -> None:
    _seed_catalog(session)
    # Nessun trasferimento: al Napoli compare solo nelle statistiche (/players), alla Lazio
    # nella rosa attuale (/players/squads).
    provider = _FakeProvider(
        squads={LAZIO[0]: _squad(LAZIO, [(MOVED, "T. Doppio", "Attacker")])},
        players={NAPOLI[0]: _players(NAPOLI, SERIE_A, [(MOVED, "T. Doppio", "Midfielder")])},
        transfers={},
    )
    sync_mvp_roster_with_client(
        session,
        provider,  # type: ignore[arg-type]
        season_year=SEASON,
        store_snapshots=False,
    )
    players_only = _membership(session, MOVED, NAPOLI[0])
    assert players_only is not None and players_only.is_active
    assert players_only.source == "players"
    players_only.updated_at = datetime.now(UTC) + timedelta(minutes=5)
    session.commit()

    generate_official_listone(session, season_year=SEASON)
    session.commit()
    assignment = _assignment(session, MOVED)
    assert assignment.club_id == _club(session, LAZIO[0]).id
    assert assignment.role == FantasyRole.A
