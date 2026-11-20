"""Precondizioni del mercato per i test d'integrazione scritti prima del 20/11/2026.

Decisione del 20/11: il mercato si apre solo a lega al completo (iscritti = partecipanti del
regolamento, minimo 4) e una lega nuova nasce col mercato chiuso. I test di aste, scambi, rose
e formazioni scritti prima provano quei meccanismi su leghe di 1-3 iscritti create col mercato
aperto di default: per loro la lega conta come al completo e nasce col mercato aperto, come
allora. Tutto il resto (interruttore, turno in corso, conteggio degli iscritti) gira davvero.

I test della regola nuova sono marcati ``league_capacity_rule`` e girano senza questa
compatibilità (``tests/integration/market/test_league_full_market.py``).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import event

LEAGUE_CAPACITY_RULE_MARKER = "league_capacity_rule"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        f"{LEAGUE_CAPACITY_RULE_MARKER}: test della regola «mercato a lega al completo» (20/11), "
        "senza la compatibilità dei test precedenti",
    )


def _market_open_by_default(_target: object, _args: object, kwargs: dict[str, object]) -> None:
    # Il default della colonna resta quello vero (chiuso): qui si apre solo la lega creata
    # senza un valore esplicito, come faceva il default prima del 20/11.
    kwargs.setdefault("market_open", True)


@pytest.fixture(autouse=True)
def _market_preconditions_before_capacity_rule(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker(LEAGUE_CAPACITY_RULE_MARKER) is not None:
        yield
        return
    from leagues.capacity import LeagueOccupancy
    from leagues.models.league import League

    monkeypatch.setattr(LeagueOccupancy, "is_full", property(lambda _self: True))
    event.listen(League, "init", _market_open_by_default)
    try:
        yield
    finally:
        event.remove(League, "init", _market_open_by_default)
