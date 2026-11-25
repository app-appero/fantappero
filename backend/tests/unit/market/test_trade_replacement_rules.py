"""Regole del sostituto dopo uno scambio sbilanciato (1.5): ruoli, testi, notifica."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from database.enums import FantasyRole
from fantasy_teams.composition import limits_from_rules
from market.trade_replacement import (
    missing_roles_label,
    net_outgoing_roles,
    plan_replacement_roles,
    role_count_label,
)
from notifications.templates import render_notification

D, C, A, P = FantasyRole.D, FantasyRole.C, FantasyRole.A, FantasyRole.P
LIMITS = limits_from_rules(roster_size=35, goalkeepers=3, defenders=11, midfielders=11, forwards=10)


def _roster(p: int, d: int, c: int, a: int) -> list[FantasyRole]:
    return [P] * p + [D] * d + [C] * c + [A] * a


def test_two_defenders_out_one_midfielder_in_leaves_one_defender_to_choose() -> None:
    roles = _roster(3, 9, 12, 10)  # 34 in rosa, un C in esubero
    assert plan_replacement_roles(
        limits=LIMITS, roster_roles=roles, roster_count=len(roles), cap=1, preferred=[D, D]
    ) == [D]


def test_three_for_one_leaves_two_to_choose_never_more_than_the_empty_places() -> None:
    roles = _roster(3, 8, 12, 10)  # 33: mancano 2 posti, tre D sotto quota
    assert plan_replacement_roles(
        limits=LIMITS, roster_roles=roles, roster_count=33, cap=2, preferred=[D, D, D]
    ) == [D, D]
    # Il diritto non supera mai i giocatori ceduti in più né i posti vuoti.
    assert plan_replacement_roles(
        limits=LIMITS, roster_roles=roles, roster_count=33, cap=5, preferred=[D]
    ) == [D, D]
    assert (
        plan_replacement_roles(
            limits=LIMITS, roster_roles=_roster(3, 11, 11, 10), roster_count=35, cap=3
        )
        == []
    )


def test_the_role_follows_the_quotas_and_ties_go_to_the_player_given_away_in_excess() -> None:
    # Ceduti un D e un C per un A: un posto solo, D e C entrambi sotto quota.
    roles = _roster(3, 10, 10, 11)
    assert plan_replacement_roles(
        limits=LIMITS, roster_roles=roles, roster_count=34, cap=1, preferred=[C, D]
    ) == [C]
    assert plan_replacement_roles(
        limits=LIMITS, roster_roles=roles, roster_count=34, cap=1, preferred=[D, C]
    ) == [D]
    # Il ceduto in più conta solo se il suo ruolo manca davvero: qui manca solo un D.
    assert plan_replacement_roles(
        limits=LIMITS, roster_roles=_roster(3, 10, 11, 10), roster_count=34, cap=1, preferred=[C]
    ) == [D]


def test_without_any_role_under_quota_the_role_of_the_player_given_away_is_used() -> None:
    small = limits_from_rules(roster_size=4, goalkeepers=1, defenders=1, midfielders=0, forwards=1)
    roles = [P, D, A]
    assert plan_replacement_roles(
        limits=small, roster_roles=roles, roster_count=3, cap=1, preferred=[C]
    ) == [C]


def test_net_outgoing_roles_skip_the_roles_that_came_back() -> None:
    assert net_outgoing_roles([D, C], [C]) == [D]
    assert net_outgoing_roles([D, D], [C]) == [D, D]
    assert net_outgoing_roles([D, None], [A]) == [D]


def test_labels_count_and_plural() -> None:
    assert role_count_label(D, 1) == "1 Difensore"
    assert role_count_label(D, 2) == "2 Difensori"
    assert role_count_label(P, 2) == "2 Portieri"
    assert missing_roles_label([D]) == "1 Difensore"
    assert missing_roles_label([D, D]) == "2 Difensori"
    assert missing_roles_label([C, D]) == "1 Difensore e 1 Centrocampista"
    assert missing_roles_label([A, C, D]) == "1 Difensore, 1 Centrocampista e 1 Attaccante"
    assert missing_roles_label([]) == ""


def test_replacement_notification_says_what_is_missing_and_opens_the_choice() -> None:
    content = render_notification(
        "mercato.sostituto_scambio",
        1,
        {
            "league_id": "lega-x",
            "league_name": "Lega X",
            "other_team": "Giulia United",
            "missing_label": "1 Difensore",
            "count": 1,
        },
    )
    assert content.title == "Scegli il sostituto dopo lo scambio"
    assert content.body == (
        "«Lega X» · Scambio con Giulia United fatto: ti manca 1 Difensore. Sceglilo dagli "
        "svincolati, al suo Valore, per schierare la formazione."
    )
    assert content.deep_link is not None
    link = urlsplit(content.deep_link)
    assert link.path == "/rosa"
    assert parse_qs(link.query) == {"sostituto": ["1"], "lega": ["lega-x"]}

    many = render_notification(
        "mercato.sostituto_scambio",
        1,
        {"missing_label": "2 Difensori", "count": 2},
    )
    assert many.body == (
        "Scambio fatto: ti mancano 2 Difensori. Sceglili dagli svincolati, al loro Valore, per "
        "schierare la formazione."
    )
