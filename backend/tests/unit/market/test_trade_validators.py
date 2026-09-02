"""Unit tests for trade proposal validators (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from auth.exceptions import ValidationAuthError
from market.trade_validators import (
    parse_athlete_ids,
    validate_active_proposal_limit,
    validate_athletes_owned_by_team,
    validate_distinct_teams,
    validate_no_athlete_overlap,
    validate_offered_credits_within_balance,
    validate_trade_expiry,
    validate_trade_sides_not_empty,
    validate_trades_enabled,
)


def test_validate_trades_enabled_rejects_when_disabled() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_trades_enabled(allow_trades=False)
    assert exc.value.code == "trades_disabled"
    validate_trades_enabled(allow_trades=True)


def test_validate_trade_expiry_rejects_past_or_now() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationAuthError) as exc:
        validate_trade_expiry(now, now=now)
    assert exc.value.code == "invalid_trade_expiry"
    with pytest.raises(ValidationAuthError):
        validate_trade_expiry(now - timedelta(hours=1), now=now)
    validate_trade_expiry(now + timedelta(hours=1), now=now)


def test_validate_distinct_teams_rejects_same_team() -> None:
    team_id = uuid4()
    with pytest.raises(ValidationAuthError) as exc:
        validate_distinct_teams(proposer_team_id=team_id, recipient_team_id=team_id)
    assert exc.value.code == "trade_same_team"


def test_parse_athlete_ids_rejects_invalid_and_duplicate() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        parse_athlete_ids(["not-a-uuid"], field="offerta")
    assert exc.value.code == "invalid_athlete_id"

    valid = str(uuid4())
    with pytest.raises(ValidationAuthError) as exc:
        parse_athlete_ids([valid, valid], field="offerta")
    assert exc.value.code == "duplicate_athlete_id"

    assert len(parse_athlete_ids([valid], field="offerta")) == 1


def test_validate_trade_sides_not_empty_rejects_empty_offer_or_request() -> None:
    athlete = uuid4()
    with pytest.raises(ValidationAuthError) as exc:
        validate_trade_sides_not_empty(
            offered_athlete_ids=[],
            offered_credits=0,
            requested_athlete_ids=[athlete],
            requested_credits=0,
        )
    assert exc.value.code == "trade_offer_empty"

    with pytest.raises(ValidationAuthError) as exc:
        validate_trade_sides_not_empty(
            offered_athlete_ids=[athlete],
            offered_credits=0,
            requested_athlete_ids=[],
            requested_credits=0,
        )
    assert exc.value.code == "trade_request_empty"

    # Credits alone satisfy a side.
    validate_trade_sides_not_empty(
        offered_athlete_ids=[],
        offered_credits=10,
        requested_athlete_ids=[],
        requested_credits=10,
    )


def test_validate_no_athlete_overlap_rejects_shared_athlete() -> None:
    shared = uuid4()
    with pytest.raises(ValidationAuthError) as exc:
        validate_no_athlete_overlap(
            offered_athlete_ids=[shared], requested_athlete_ids=[shared, uuid4()]
        )
    assert exc.value.code == "trade_athlete_overlap"


def test_validate_athletes_owned_by_team_rejects_missing_athlete() -> None:
    owned = uuid4()
    missing = uuid4()
    with pytest.raises(ValidationAuthError) as exc:
        validate_athletes_owned_by_team(
            athlete_ids=[owned, missing], owned_athlete_ids={owned}, team_label="della tua squadra"
        )
    assert exc.value.code == "trade_athlete_not_owned"
    validate_athletes_owned_by_team(
        athlete_ids=[owned], owned_athlete_ids={owned}, team_label="della tua squadra"
    )


def test_validate_offered_credits_within_balance_rejects_overdraw() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_offered_credits_within_balance(offered_credits=101, balance=100)
    assert exc.value.code == "insufficient_credits"
    validate_offered_credits_within_balance(offered_credits=100, balance=100)


def test_validate_active_proposal_limit_rejects_at_or_above_limit() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_active_proposal_limit(active_count=5, limit=5)
    assert exc.value.code == "trade_active_limit_reached"
    validate_active_proposal_limit(active_count=4, limit=5)
