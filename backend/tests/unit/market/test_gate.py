"""Unit tests for the league-admin market window."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sqlalchemy.exc import ProgrammingError

from auth.exceptions import ValidationAuthError
from market.gate import MARKET_CLOSED_CODE, assert_market_open


def test_assert_market_open_allows_open_league() -> None:
    assert_market_open(SimpleNamespace(market_open=True))


def test_assert_market_open_rejects_closed_league() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        assert_market_open(SimpleNamespace(market_open=False))
    assert exc.value.code == MARKET_CLOSED_CODE
    assert "scambi" in exc.value.message.lower()


class _MissingMarketOpenColumn:
    @property
    def market_open(self) -> bool:
        raise ProgrammingError("SELECT", {}, Exception("column leagues.market_open does not exist"))


def test_assert_market_open_defaults_open_when_column_is_missing() -> None:
    assert_market_open(_MissingMarketOpenColumn())
