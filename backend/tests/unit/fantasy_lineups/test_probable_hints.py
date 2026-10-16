"""Gli indizi delle formazioni probabili non devono bloccare il caricamento."""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import MagicMock
from uuid import uuid4

from fantasy_lineups.service import FantasyLineupService


def test_probable_hints_reads_through_the_service_session() -> None:
    service = FantasyLineupService.__new__(FantasyLineupService)
    session = MagicMock()
    session.begin_nested.return_value = nullcontext()
    session.scalars.return_value.all.return_value = []
    service._session = session

    assert service._probable_hints(uuid4(), [uuid4()]) == {}
    session.scalars.assert_called_once()


def test_probable_hints_failure_leaves_the_lineup_usable() -> None:
    service = FantasyLineupService.__new__(FantasyLineupService)
    session = MagicMock()
    session.begin_nested.return_value = nullcontext()
    session.scalars.side_effect = RuntimeError("relation predicted_lineup_snapshots does not exist")
    service._session = session

    assert service._probable_hints(uuid4(), [uuid4()]) == {}
