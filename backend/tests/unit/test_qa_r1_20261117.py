"""Correzioni QA del 17/11 (corsa R1): link delle notifiche d'asta e testi di lega."""

from __future__ import annotations

import pytest

from database.enums import LeagueState
from leagues.service import admin_panel_message
from notifications.templates import render_notification


@pytest.mark.parametrize(
    ("template", "params", "path"),
    [
        ("mercato.esito_busta", {"outcome": "assigned", "amount_credits": 5}, "/asta"),
        ("mercato.esito_busta", {"outcome": "lost"}, "/asta"),
        ("mercato.esito_busta", {"outcome": "tiebreak"}, "/asta"),
        ("mercato.asta_live_aggiudicato", {"amount_credits": 5}, "/asta-live"),
        ("mercato.asta_live_sorpassato", {}, "/asta-live"),
        ("mercato.asta_live_scambio_richiesto", {}, "/asta-live"),
        ("mercato.asta_live_iniziata", {}, "/asta-live"),
    ],
)
def test_auction_notifications_open_the_auction_tab(
    template: str, params: dict[str, object], path: str
) -> None:
    content = render_notification(
        template, 1, {"athlete_name": "Rossi", "league_id": "abc", **params}
    )
    assert content.deep_link == f"{path}?lega=abc"


def test_admin_panel_message_follows_league_state() -> None:
    setup = "Configura il regolamento della lega prima dell'avvio."
    assert admin_panel_message(LeagueState.CONFIGURING) == setup
    assert admin_panel_message(LeagueState.ACTIVE) == "La stagione è in corso."
    assert admin_panel_message(LeagueState.CONCLUDED) == "La stagione è conclusa."


def test_tiebreak_cancelled_notification_and_same_role_swap_never_exceeds_quota() -> None:
    from database.enums import FantasyRole
    from fantasy_teams.composition import RosterCompositionLimits, would_exceed_role_quota
    from market.validators import validate_session_window

    cancelled = render_notification(
        "mercato.esito_busta",
        1,
        {"outcome": "lost", "athlete_name": "Rossi", "tiebreak_cancelled": True},
    )
    assert cancelled.title == "Spareggio annullato"

    limits = RosterCompositionLimits(
        roster_size=35, goalkeepers=3, defenders=11, midfielders=11, forwards=10
    )
    over_quota = [FantasyRole.C] * 14
    assert not would_exceed_role_quota(
        limits=limits,
        current_roles=over_quota,
        new_role=FantasyRole.C,
        replacing_role=FantasyRole.C,
    )
    assert would_exceed_role_quota(
        limits=limits,
        current_roles=over_quota,
        new_role=FantasyRole.C,
        replacing_role=FantasyRole.D,
    )

    from datetime import UTC, datetime

    import pytest as _pytest

    from auth.exceptions import ValidationAuthError

    now = datetime.now(UTC)
    with _pytest.raises(ValidationAuthError):
        validate_session_window(
            opens_at=datetime(1, 1, 1, tzinfo=UTC),
            closes_at=now.replace(year=now.year + 1),
            now=now,
        )
