"""Unit tests for market history categorisation/filtering (EP08-08 / FR-MKT-04)."""

from __future__ import annotations

from uuid import uuid4

from database.enums import LeagueAuditAction
from market.history_service import category_for, proposal_ids_in, team_ids_for


def test_category_for_maps_acquisto_actions() -> None:
    for action in (
        LeagueAuditAction.MARKET_SESSION_CREATED,
        LeagueAuditAction.MARKET_SESSION_CLOSED,
        LeagueAuditAction.MARKET_BID_SUBMITTED,
        LeagueAuditAction.MARKET_BID_WITHDRAWN,
        LeagueAuditAction.MARKET_SESSION_RESOLVED,
        LeagueAuditAction.MARKET_TIEBREAK_OPENED,
    ):
        assert category_for(action, None) == "acquisto"


def test_category_for_maps_scambio_actions() -> None:
    for action in (
        LeagueAuditAction.MARKET_TRADE_PROPOSED,
        LeagueAuditAction.MARKET_TRADE_CANCELLED,
        LeagueAuditAction.MARKET_TRADE_ACCEPTED,
        LeagueAuditAction.MARKET_TRADE_REJECTED,
        LeagueAuditAction.MARKET_TRADE_COUNTERED,
        LeagueAuditAction.MARKET_TRADE_APPROVED,
        LeagueAuditAction.MARKET_TRADE_REJECTED_BY_ADMIN,
    ):
        assert category_for(action, None) == "scambio"


def test_category_for_svincolo_requires_market_reason() -> None:
    action = LeagueAuditAction.FANTASY_ROSTER_SLOT_RELEASED
    # Market voluntary/exit release always carries a "reason" (EP08-04).
    assert category_for(action, {"reason": "voluntary"}) == "svincolo"
    # Admin manual roster release (fantasy_teams/service.py) has no "reason"
    # and must not be mistaken for a market event.
    assert category_for(action, {"refundedCredits": 0}) is None
    assert category_for(action, None) is None


def test_category_for_intervento_manuale() -> None:
    assert (
        category_for(LeagueAuditAction.CREDIT_LEDGER_ENTRY_POSTED, {"amount": 5})
        == "intervento_manuale"
    )


def test_category_for_unrelated_action_is_excluded() -> None:
    assert category_for(LeagueAuditAction.LEAGUE_CREATED, None) is None


def test_proposal_ids_in_collects_known_keys() -> None:
    proposal_id = str(uuid4())
    original_id = str(uuid4())
    counter_id = str(uuid4())
    assert proposal_ids_in({"proposalId": proposal_id}) == {proposal_id}
    assert proposal_ids_in(
        {"originalProposalId": original_id, "counterProposalId": counter_id}
    ) == {original_id, counter_id}
    assert proposal_ids_in(None) == set()
    assert proposal_ids_in({"somethingElse": 1}) == set()


def test_team_ids_for_direct_keys() -> None:
    team_id = str(uuid4())
    assert team_ids_for({"fantasyTeamId": team_id}, {}) == {team_id}
    proposer = str(uuid4())
    recipient = str(uuid4())
    assert team_ids_for(
        {"proposerTeamId": proposer, "recipientTeamId": recipient}, {}
    ) == {proposer, recipient}


def test_team_ids_for_team_ids_list_and_winners() -> None:
    team_a = str(uuid4())
    team_b = str(uuid4())
    assert team_ids_for({"teamIds": [team_a, team_b]}, {}) == {team_a, team_b}
    assert team_ids_for(
        {"winners": [{"fantasyTeamId": team_a}, {"fantasyTeamId": team_b}]}, {}
    ) == {team_a, team_b}


def test_team_ids_for_resolves_via_proposal_lookup() -> None:
    proposal_id = str(uuid4())
    proposer = str(uuid4())
    recipient = str(uuid4())
    proposal_teams = {proposal_id: (proposer, recipient)}
    assert team_ids_for({"proposalId": proposal_id}, proposal_teams) == {
        proposer,
        recipient,
    }
    # An unresolved proposal id (not in the lookup) contributes nothing.
    assert team_ids_for({"proposalId": str(uuid4())}, proposal_teams) == set()


def test_team_ids_for_empty_details() -> None:
    assert team_ids_for(None, {}) == set()
    assert team_ids_for({}, {}) == set()
