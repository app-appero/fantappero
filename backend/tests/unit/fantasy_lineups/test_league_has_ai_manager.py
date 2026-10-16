"""Il contesto formazione espone se la lega ha almeno un fantallenatore IA."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from fantasy_lineups.service import FantasyLineupService


def test_league_has_ai_manager_when_membership_exists() -> None:
    service = FantasyLineupService.__new__(FantasyLineupService)
    session = MagicMock()
    session.scalar.return_value = uuid4()
    service._session = session

    assert service._league_has_ai_manager(uuid4()) is True
    session.scalar.assert_called_once()


def test_league_has_ai_manager_when_none() -> None:
    service = FantasyLineupService.__new__(FantasyLineupService)
    session = MagicMock()
    session.scalar.return_value = None
    service._session = session

    assert service._league_has_ai_manager(uuid4()) is False
