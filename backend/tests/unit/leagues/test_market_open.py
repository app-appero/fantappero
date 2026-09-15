"""Safe reads of leagues.market_open when the column is missing."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import ProgrammingError

from auth.exceptions import ValidationAuthError
from leagues.market_open import read_market_open, read_market_open_map, write_market_open


def test_read_market_open_defaults_when_column_is_missing() -> None:
    session = MagicMock()
    session.execute.side_effect = ProgrammingError(
        "SELECT",
        {},
        Exception("column leagues.market_open does not exist"),
    )
    league_id = uuid4()
    assert read_market_open(session, league_id) is True
    session.rollback.assert_called_once()


def test_read_market_open_map_skips_query_for_empty_ids() -> None:
    session = MagicMock()
    assert read_market_open_map(session, []) == {}
    session.execute.assert_not_called()


def test_write_market_open_raises_when_column_is_missing() -> None:
    session = MagicMock()
    session.execute.side_effect = ProgrammingError(
        "UPDATE",
        {},
        Exception("column leagues.market_open does not exist"),
    )
    with pytest.raises(ValidationAuthError) as exc:
        write_market_open(session, uuid4(), False)
    assert exc.value.code == "market_gate_unavailable"
    session.rollback.assert_called_once()
