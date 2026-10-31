"""Un calciatore ritirato/uscito senza un Transfer tracciato deve comunque
smettere di apparire come rosa attiva, non restare ``is_active=True`` per
sempre (bug: "Panchina e tribuna" mostrava calciatori andati in pensione)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from sports_data.provider.types import MappedSquadMembership
from sports_data.roster.models import SquadMembership
from sports_data.roster.sync import (
    MIN_SQUAD_SIZE_FOR_RECONCILIATION,
    RosterSyncCounters,
    _deactivate_memberships_missing_from_fetch,
    sync_squads_for_club,
)


def test_stale_membership_is_deactivated_when_fetch_is_a_full_squad() -> None:
    club_id = uuid4()
    season_id = uuid4()
    stale = SquadMembership(
        athlete_id=uuid4(),
        club_id=club_id,
        sport_season_id=season_id,
        is_active=True,
        ended_at=None,
    )
    session = MagicMock()
    session.scalars.return_value.all.return_value = [stale]

    _deactivate_memberships_missing_from_fetch(
        session,
        club_id=club_id,
        sport_season_id=season_id,
        seen_athlete_ids={uuid4() for _ in range(MIN_SQUAD_SIZE_FOR_RECONCILIATION)},
        counters=RosterSyncCounters(),
    )

    assert stale.is_active is False
    assert stale.ended_at is not None


def test_partial_fetch_is_not_used_to_mass_deactivate() -> None:
    session = MagicMock()

    _deactivate_memberships_missing_from_fetch(
        session,
        club_id=uuid4(),
        sport_season_id=uuid4(),
        seen_athlete_ids={uuid4(), uuid4()},
        counters=RosterSyncCounters(),
    )

    session.scalars.assert_not_called()


def test_sync_squads_for_club_reconciles_against_the_resolved_club_and_season(
    monkeypatch,
) -> None:
    club_id = uuid4()
    season_id = uuid4()
    mapped_rows = [
        MappedSquadMembership(
            athlete_provider_id=i,
            athlete_name=f"Player {i}",
            club_provider_id=1,
            competition_provider_id=39,
            season_year=2026,
        )
        for i in range(MIN_SQUAD_SIZE_FOR_RECONCILIATION)
    ]
    seen_athlete_ids = {uuid4() for _ in mapped_rows}
    memberships = iter(
        [
            SquadMembership(athlete_id=athlete_id, club_id=club_id, sport_season_id=season_id)
            for athlete_id in seen_athlete_ids
        ]
    )
    monkeypatch.setattr(
        "sports_data.roster.sync.map_squad_memberships",
        lambda *_a, **_k: mapped_rows,
    )
    monkeypatch.setattr(
        "sports_data.roster.sync.upsert_squad_membership",
        lambda *_a, **_k: next(memberships),
    )
    reconciled: list[dict] = []
    monkeypatch.setattr(
        "sports_data.roster.sync._deactivate_memberships_missing_from_fetch",
        lambda _session, **kwargs: reconciled.append(kwargs),
    )

    sync_squads_for_club(
        MagicMock(),
        envelope=MagicMock(),
        club_provider_id=1,
        competition_provider_id=39,
        season_year=2026,
        store_snapshots=False,
    )

    assert len(reconciled) == 1
    assert reconciled[0]["club_id"] == club_id
    assert reconciled[0]["sport_season_id"] == season_id
    assert reconciled[0]["seen_athlete_ids"] == seen_athlete_ids
