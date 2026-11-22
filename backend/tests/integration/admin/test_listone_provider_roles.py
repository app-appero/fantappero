# ruff: noqa: F811
"""«Aggiorna anche i ruoli dal fornitore»: anteprima con le rose coinvolte, poi conferma (22/11).

``POST /admin/listone/ruoli-dal-fornitore`` (solo operatore): ``dryRun`` elenca chi
cambierebbe ruolo, in quali leghe è in rosa e quante rose andrebbero fuori quota; con la
conferma applica i ruoli e ricalcola le rose.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.admin.test_listone_role_restore import (
    FIRST_MIDFIELDER_SLOT,
    _assignment,
    _flagged,
    _slot_athlete,
    _team,
)
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _register_and_login,
    _trade_league,
    competition_ids,
    db_session,
)
from tests.integration.fantasy_turns.test_fantasy_turns import _promote_to_operator

from database.enums import FantasyRole, RosterCompositionStatus
from sports_data.catalog.models import CompetitionSeasonClub
from sports_data.roster.models import SquadMembership

URL = "/admin/listone/ruoli-dal-fornitore"


def _provider_says_attacker(db_session: Session, setup: dict):
    """Il fornitore oggi dà attaccante un C della squadra A (membership attiva del suo club)."""
    athlete = _slot_athlete(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT)
    assignment = _assignment(db_session, athlete)
    link = db_session.scalars(
        select(CompetitionSeasonClub).where(CompetitionSeasonClub.club_id == assignment.club_id)
    ).first()
    assert link is not None
    db_session.add(
        SquadMembership(
            athlete_id=athlete.id,
            club_id=assignment.club_id,
            sport_season_id=link.sport_season_id,
            provider_position_raw="Attacker",
            is_active=True,
            source="squads",
        )
    )
    db_session.commit()
    return athlete


def _body(*, dry_run: bool, athlete_ids: list[str] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"seasonYear": 2026, "dryRun": dry_run}
    if athlete_ids is not None:
        body["athleteIds"] = athlete_ids
    return body


def test_preview_then_confirm_applies_the_new_roles_and_resyncs_the_rosters(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rf.ruoli", id_offset=8_740_000
    )
    athlete = _provider_says_attacker(db_session, setup)
    token, user_id = _register_and_login(client, "rf.ruoli.op@example.com")
    _promote_to_operator(db_session, user_id)

    preview = client.post(URL, headers=_headers(token), json=_body(dry_run=True))

    assert preview.status_code == 200, preview.json()
    data = preview.json()
    mine = [entry for entry in data["entries"] if entry["athleteId"] == str(athlete.id)]
    assert len(mine) == 1
    assert mine[0]["currentRole"] == "C"
    assert mine[0]["newRole"] == "A"
    assert mine[0]["providerPositionRaw"] == "Attacker"
    assert mine[0]["inRosters"] == ["Lega rf.ruoli"]
    # 11 attaccanti su 10: la rosa della squadra A andrebbe fuori quota.
    assert data["counts"]["rostersOverQuotaAfter"] >= data["counts"]["rostersOverQuotaNow"] + 1
    assert data["counts"]["applied"] == 0
    assert _assignment(db_session, athlete).role == FantasyRole.C
    assert (
        _team(db_session, setup["team_a"]).composition_status == RosterCompositionStatus.VALIDATED
    )

    confirmed = client.post(
        URL,
        headers=_headers(token),
        json=_body(dry_run=False, athlete_ids=[str(athlete.id)]),
    )

    assert confirmed.status_code == 200, confirmed.json()
    assert confirmed.json()["counts"]["applied"] == 1
    assert confirmed.json()["counts"]["rostersResynced"] >= 1
    assert _assignment(db_session, athlete).role == FantasyRole.A
    assert _team(db_session, setup["team_a"]).composition_status == RosterCompositionStatus.INVALID
    assert _flagged(db_session, setup["team_a"]) != []

    again = client.post(
        URL,
        headers=_headers(token),
        json=_body(dry_run=False, athlete_ids=[str(athlete.id)]),
    )
    assert again.status_code == 200
    assert again.json()["counts"]["applied"] == 0
    assert str(athlete.id) not in {entry["athleteId"] for entry in again.json()["entries"]}


def test_provider_roles_are_forbidden_to_a_league_admin_and_to_a_normal_user(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="rf.vietato", id_offset=8_750_000
    )
    athlete = _provider_says_attacker(db_session, setup)
    for token in (setup["token_a"], setup["token_b"]):
        for dry_run in (True, False):
            response = client.post(URL, headers=_headers(token), json=_body(dry_run=dry_run))
            assert response.status_code == 403
        refresh = client.post(
            "/admin/listone/aggiorna?seasonYear=2026&updateRoles=true", headers=_headers(token)
        )
        assert refresh.status_code == 403
    assert _assignment(db_session, athlete).role == FantasyRole.C
