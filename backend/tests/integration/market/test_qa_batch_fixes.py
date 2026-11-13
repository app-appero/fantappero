"""Regressioni dal giro QA su dev: N1 (atomicità), N3 (approvazione visibile), N6 (svincolo)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount, FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from market.models import TradeProposal
from notifications.models import Notification
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


_OWNER_TOKENS: dict[str, str] = {}


def _owner_headers(league_id: str, fallback_token: str) -> dict[str, str]:
    """N12: solo l'amministratore assegna calciatori a mano; i test lo fanno a suo nome."""
    return {"Authorization": f"Bearer {_OWNER_TOKENS.get(league_id, fallback_token)}"}


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    _OWNER_TOKENS[response.json()["id"]] = token
    return response.json()["id"]


def _add_member(db_session: Session, league_id: str, user_id: UUID) -> LeagueMembership:
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=user_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


def _seed_athlete(
    db_session: Session, provider_id: int, name: str, *, season_year: int = 2026
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=FantasyRole.D,
            mapping_version="v1.0.0",
            provider_position_raw=FantasyRole.D.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _own_athlete_at_slot(
    client: TestClient, league_id: str, token: str, slot_index: int, athlete: Athlete
) -> str:
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers=_owner_headers(league_id, token),
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 200
    return team_id


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _set_league_rules(
    client: TestClient,
    league_id: str,
    token: str,
    *,
    require_trade_approval: bool | None = None,
    max_active_trade_proposals_per_team: int | None = None,
) -> dict:
    rules = client.get(
        f"/leagues/{league_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["rules"]
    body = {
        "presetName": "standard",
        "participantCount": rules["participantCount"],
        "roster": rules["roster"],
        "totalCredits": rules["totalCredits"],
        "options": {
            "allowTrades": True,
            "allowManualInvites": True,
            "requireTradeApproval": (
                require_trade_approval
                if require_trade_approval is not None
                else rules["options"]["requireTradeApproval"]
            ),
        },
    }
    if max_active_trade_proposals_per_team is not None:
        body["maxActiveTradeProposalsPerTeam"] = max_active_trade_proposals_per_team
    response = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert response.status_code == 200
    return response.json()


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_owner_sees_and_is_notified_of_trades_pending_approval(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, admin_id = _register_and_login(client, "n3.admin@example.com")
    proposer_token, proposer_id = _register_and_login(client, "n3.proposer@example.com")
    recipient_token, recipient_id = _register_and_login(client, "n3.recipient@example.com")
    outsider_token, outsider_id = _register_and_login(client, "n3.outsider@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N3")
    for user_id in (proposer_id, recipient_id, outsider_id):
        _add_member(db_session, league_id, user_id)
    athlete = _seed_athlete(db_session, 9801, "Scambio Da Approvare")
    recipient_team_id = _own_athlete_at_slot(client, league_id, recipient_token, 0, athlete)
    client.get(f"/leagues/{league_id}/rosa", headers=_hdr(proposer_token))
    client.get(f"/leagues/{league_id}/rosa", headers=_hdr(outsider_token))
    _set_league_rules(client, league_id, admin_token, require_trade_approval=True)

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_hdr(proposer_token),
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 20,
            "requestedAthleteIds": [str(athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()
    pid = proposal["id"]

    # Finché è solo proposto, l'owner (non parte in causa) non lo vede.
    before = client.get(f"/leagues/{league_id}/mercato/scambi/proposte", headers=_hdr(admin_token))
    assert pid not in [row["id"] for row in before.json()["proposals"]]

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{pid}/accetta",
        headers=_hdr(recipient_token),
    )
    assert accepted.json()["status"] == "pending_approval"

    listed = client.get(f"/leagues/{league_id}/mercato/scambi/proposte", headers=_hdr(admin_token))
    assert pid in [row["id"] for row in listed.json()["proposals"]]
    detail = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{pid}", headers=_hdr(admin_token)
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending_approval"

    # Un membro estraneo, non owner, continua a non vedere nulla.
    outsider = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{pid}", headers=_hdr(outsider_token)
    )
    assert outsider.status_code == 400
    assert outsider.json()["code"] == "trade_access_forbidden"
    outsider_list = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte", headers=_hdr(outsider_token)
    )
    assert pid not in [row["id"] for row in outsider_list.json()["proposals"]]

    db_session.expire_all()
    notified = db_session.scalars(
        select(Notification).where(
            Notification.user_id == admin_id,
            Notification.template_key == "mercato.scambio",
        )
    ).all()
    assert len(notified) == 1
    assert "da approvare" in (notified[0].title or "")


def test_member_cannot_release_for_league_exit_but_owner_can(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n6.admin@example.com")
    member_token, member_id = _register_and_login(client, "n6.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N6")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9802, "Svincolo Uscita")
    _own_athlete_at_slot(client, league_id, member_token, 0, athlete)

    denied = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers=_hdr(member_token),
        json={"reason": "league_exit"},
    )
    assert denied.status_code == 400
    assert denied.json()["code"] == "release_reason_forbidden"
    preview = client.get(
        f"/leagues/{league_id}/mercato/svincolo/0/anteprima",
        headers=_hdr(member_token),
        params={"causa": "league_exit"},
    )
    assert preview.status_code == 400

    voluntary = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers=_hdr(member_token),
        json={"reason": "voluntary"},
    )
    assert voluntary.status_code == 200


def test_failed_slot_assignment_leaves_no_partial_write(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n1.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N1")
    athlete = _seed_athlete(db_session, 9803, "Troppo Caro")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(admin_token)).json()["id"]

    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers=_hdr(admin_token),
        json={"athleteId": str(athlete.id), "purchaseCredits": 999_999},
    )
    assert response.status_code == 400

    db_session.expire_all()
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is None or slot.athlete_id is None
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    assert account.balance == 1000


def test_second_live_auction_in_same_league_is_rejected(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n19.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N19")
    now = datetime.now(UTC)
    payload = {
        "opensAt": now.isoformat(),
        "closesAt": (now + timedelta(hours=2)).isoformat(),
        "nominationMode": "random",
        "minIncrementCredits": 10,
        "softCloseSeconds": 5,
        "lotDurationSeconds": 30,
    }
    url = f"/leagues/{league_id}/mercato/asta-live/sessioni"
    first = client.post(url, headers=_hdr(admin_token), json=payload)
    assert first.status_code == 201
    second = client.post(url, headers=_hdr(admin_token), json=payload)
    assert second.status_code == 400
    assert second.json()["code"] == "market_session_already_active"


def test_member_cannot_assign_roster_slot_even_at_zero_price(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n12.admin@example.com")
    member_token, member_id = _register_and_login(client, "n12.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N12")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9804, "Gratis Vietato")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(member_token)).json()["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers=_hdr(member_token),
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "roster_assign_forbidden"


def _assign_priced(
    client: TestClient, league_id: str, admin_token: str, team_id: str, slot: int, athlete, price
) -> None:
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot}",
        headers=_hdr(admin_token),
        json={"athleteId": str(athlete.id), "purchaseCredits": price},
    )
    assert response.status_code == 200, response.json()


def test_trade_keeps_each_players_purchase_price_and_moves_no_credits(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n6b.admin@example.com")
    a_token, a_id = _register_and_login(client, "n6b.a@example.com")
    b_token, b_id = _register_and_login(client, "n6b.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Prezzi")
    _add_member(db_session, league_id, a_id)
    _add_member(db_session, league_id, b_id)
    cheap = _seed_athlete(db_session, 9805, "Pagato Uno")
    dear = _seed_athlete(db_session, 9806, "Pagato Cinquecento")
    team_a = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(a_token)).json()["id"]
    team_b = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(b_token)).json()["id"]
    _assign_priced(client, league_id, admin_token, team_a, 0, cheap, 1)
    _assign_priced(client, league_id, admin_token, team_b, 0, dear, 500)
    balance_a = client.get(f"/leagues/{league_id}/crediti", headers=_hdr(a_token)).json()["balance"]

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_hdr(a_token),
        json={
            "recipientTeamId": team_b,
            "offeredAthleteIds": [str(cheap.id)],
            "requestedAthleteIds": [str(dear.id)],
            "expiresAt": _future_iso(),
        },
    )
    assert proposal.status_code == 201, proposal.json()
    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal.json()['id']}/accetta",
        headers=_hdr(b_token),
    )
    assert accepted.status_code == 200, accepted.json()

    db_session.expire_all()
    prices = {
        slot.athlete_id: (slot.fantasy_team_id, slot.purchase_credits)
        for slot in db_session.scalars(
            select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id.in_([cheap.id, dear.id]))
        )
    }
    assert prices[cheap.id] == (UUID(team_b), 1)
    assert prices[dear.id] == (UUID(team_a), 500)
    after = client.get(f"/leagues/{league_id}/crediti", headers=_hdr(a_token)).json()["balance"]
    assert after == balance_a


def test_requested_credits_cannot_exceed_other_teams_balance_or_overflow(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n7.admin@example.com")
    a_token, a_id = _register_and_login(client, "n7.a@example.com")
    b_token, b_id = _register_and_login(client, "n7.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N7")
    _add_member(db_session, league_id, a_id)
    _add_member(db_session, league_id, b_id)
    mine = _seed_athlete(db_session, 9807, "Mio Giocatore")
    team_a = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(a_token)).json()["id"]
    team_b = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(b_token)).json()["id"]
    _assign_priced(client, league_id, admin_token, team_a, 0, mine, 1)
    url = f"/leagues/{league_id}/mercato/scambi/proposte"

    too_much = client.post(
        url,
        headers=_hdr(a_token),
        json={
            "recipientTeamId": team_b,
            "offeredAthleteIds": [str(mine.id)],
            "requestedCredits": 5000,
            "expiresAt": _future_iso(),
        },
    )
    assert too_much.status_code == 400
    assert too_much.json()["code"] == "requested_credits_exceed_balance"

    huge = client.post(
        url,
        headers=_hdr(a_token),
        json={
            "recipientTeamId": team_b,
            "offeredAthleteIds": [str(mine.id)],
            "requestedCredits": 2**31,
            "expiresAt": _future_iso(),
        },
    )
    assert huge.status_code == 422


def test_repeated_release_of_same_player_and_slot_refunds_every_time(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "r21.admin@example.com")
    member_token, member_id = _register_and_login(client, "r21.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rimborsi")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9808, "Rimborso Doppio")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(member_token)).json()["id"]

    def balance() -> int:
        return client.get(f"/leagues/{league_id}/crediti", headers=_hdr(member_token)).json()[
            "balance"
        ]

    start = balance()
    for round_number in (1, 2):
        _assign_priced(client, league_id, admin_token, team_id, 0, athlete, 40)
        released = client.post(
            f"/leagues/{league_id}/mercato/svincolo/0",
            headers=_hdr(member_token),
            json={"reason": "voluntary"},
        )
        assert released.status_code == 200
        refund = released.json()["refundCredits"]
        assert refund == 20
        assert balance() == start - 20 * round_number


def test_extreme_inputs_return_4xx_not_500(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "r22.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Estremi")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(admin_token)).json()["id"]

    big_slot = client.get(
        f"/leagues/{league_id}/mercato/svincolo/99999999999/anteprima",
        headers=_hdr(admin_token),
        params={"causa": "voluntary"},
    )
    assert big_slot.status_code == 400
    assert big_slot.json()["code"] == "slot_not_found"

    bad_date = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers=_hdr(admin_token),
        json={
            "opensAt": "0001-01-01T00:00:00+14:00",
            "closesAt": "2030-01-01T00:00:00Z",
            "nominationMode": "random",
            "minIncrementCredits": 10,
            "softCloseSeconds": 5,
            "lotDurationSeconds": 30,
        },
    )
    assert bad_date.status_code == 400
    assert bad_date.json()["code"] == "invalid_datetime"

    huge_credit = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers=_hdr(admin_token),
        json={"fantasyTeamId": team_id, "amount": 2**63 - 1, "transactionId": "qa-huge-1"},
    )
    assert huge_credit.status_code == 422


def test_stale_trade_proposal_is_expired_instead_of_staying_open(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "r24.admin@example.com")
    a_token, a_id = _register_and_login(client, "r24.a@example.com")
    b_token, b_id = _register_and_login(client, "r24.b@example.com")
    c_token, c_id = _register_and_login(client, "r24.c@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Obsolete")
    for user_id in (a_id, b_id, c_id):
        _add_member(db_session, league_id, user_id)
    star = _seed_athlete(db_session, 9809, "Offerto Due Volte")
    team_a = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(a_token)).json()["id"]
    team_b = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(b_token)).json()["id"]
    team_c = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(c_token)).json()["id"]
    _assign_priced(client, league_id, admin_token, team_a, 0, star, 1)

    ids = []
    for target in (team_b, team_c):
        created = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte",
            headers=_hdr(a_token),
            json={
                "recipientTeamId": target,
                "offeredAthleteIds": [str(star.id)],
                "requestedCredits": 5,
                "offeredCredits": 0,
                "expiresAt": _future_iso(),
            },
        )
        assert created.status_code == 201, created.json()
        ids.append(created.json()["id"])

    first = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{ids[0]}/accetta",
        headers=_hdr(b_token),
    )
    assert first.status_code == 200, first.json()
    second = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{ids[1]}/accetta",
        headers=_hdr(c_token),
    )
    assert second.status_code == 400
    assert second.json()["code"] == "trade_stale_assets"
    detail = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{ids[1]}", headers=_hdr(c_token)
    )
    assert detail.json()["status"] == "expired"


def test_market_notifications_carry_league_name_and_link() -> None:
    from notifications.templates import render_notification

    content = render_notification(
        "mercato.esito_busta",
        1,
        {
            "outcome": "assigned",
            "athlete_name": "Rossi",
            "amount_credits": 10,
            "league_id": "abc-123",
            "league_name": "Lega Amici",
        },
    )
    assert content.body.startswith("«Lega Amici» ·")
    assert content.deep_link == "/mercato?lega=abc-123"
    scambio = render_notification(
        "mercato.scambio",
        2,
        {"status": "proposed", "proposal_id": "p1", "league_id": "abc-123", "league_name": "X"},
    )
    assert scambio.deep_link == "/mercato?scambio=p1&lega=abc-123"


def test_cancelled_live_lot_returns_the_player_to_the_queue(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "low1.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Annullo")
    _seed_athlete(db_session, 9810, "Aaa Annullato")
    now = datetime.now(UTC)
    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers=_hdr(admin_token),
        json={
            "opensAt": now.isoformat(),
            "closesAt": (now + timedelta(hours=2)).isoformat(),
            "nominationMode": "alphabetical_by_role",
            "minIncrementCredits": 10,
            "softCloseSeconds": 5,
            "lotDurationSeconds": 30,
        },
    )
    assert created.status_code == 201, created.json()
    session_id = created.json()["id"]
    base = f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}"
    assert client.post(f"{base}/avvia", headers=_hdr(admin_token)).status_code == 200
    first = client.post(f"{base}/lotti/nomina", headers=_hdr(admin_token), json={})
    assert first.status_code == 201, first.json()
    cancelled = client.post(f"{base}/lotti/{first.json()['id']}/annulla", headers=_hdr(admin_token))
    assert cancelled.status_code == 200
    again = client.post(f"{base}/lotti/nomina", headers=_hdr(admin_token), json={})
    assert again.status_code == 201, again.json()
    assert again.json()["athleteId"] == first.json()["athleteId"]


def test_cancel_and_expiry_notify_the_other_coach(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    from market.trade_service import TradeService

    admin_token, _ = _register_and_login(client, "low2.admin@example.com")
    a_token, a_id = _register_and_login(client, "low2.a@example.com")
    b_token, b_id = _register_and_login(client, "low2.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scadenze")
    _add_member(db_session, league_id, a_id)
    _add_member(db_session, league_id, b_id)
    mine = _seed_athlete(db_session, 9811, "Offerto Notifica")
    team_a = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(a_token)).json()["id"]
    team_b = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(b_token)).json()["id"]
    _assign_priced(client, league_id, admin_token, team_a, 0, mine, 1)

    def propose() -> str:
        created = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte",
            headers=_hdr(a_token),
            json={
                "recipientTeamId": team_b,
                "offeredAthleteIds": [str(mine.id)],
                "requestedCredits": 1,
                "expiresAt": _future_iso(),
            },
        )
        assert created.status_code == 201, created.json()
        return created.json()["id"]

    cancelled_id = propose()
    client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{cancelled_id}/annulla",
        headers=_hdr(a_token),
    )
    expiring_id = propose()
    proposal = db_session.get(TradeProposal, UUID(expiring_id))
    proposal.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    assert TradeService(db_session).expire_overdue_proposals() == 1

    db_session.expire_all()
    titles_b = [
        row.title
        for row in db_session.scalars(
            select(Notification).where(Notification.user_id == b_id)
        ).all()
    ]
    titles_a = [
        row.title
        for row in db_session.scalars(
            select(Notification).where(Notification.user_id == a_id)
        ).all()
    ]
    assert any("annullato la proposta" in title for title in titles_b)
    assert any("è scaduta" in title for title in titles_b)
    assert any("è scaduta" in title for title in titles_a)
    assert db_session.get(TradeProposal, UUID(expiring_id)).status.value == "expired"


def test_small_validation_fixes() -> None:
    import pytest as _pytest
    from pydantic import ValidationError

    from fantasy_teams.ledger import order_ledger_entries
    from market.schemas import SubmitMarketBidRequest
    from notifications.schemas import RegisterPushDeviceRequest

    with _pytest.raises(ValidationError):
        SubmitMarketBidRequest.model_validate({"amountCredits": True})
    with _pytest.raises(ValidationError):
        RegisterPushDeviceRequest.model_validate({"token": "t", "platform": "zz"})

    class Entry:
        def __init__(self, amount: int, after: int, when: datetime, key: str) -> None:
            self.amount, self.balance_after, self.created_at, self.id = amount, after, when, key

    when = datetime.now(UTC)
    first, second, third = (
        Entry(-40, 960, when, "z"),
        Entry(+20, 980, when, "a"),
        Entry(-10, 970, when, "m"),
    )
    ordered = order_ledger_entries([second, third, first])
    assert [e.balance_after for e in ordered] == [960, 980, 970]


def test_unauthenticated_request_gets_a_clear_message(client: TestClient) -> None:
    response = client.get("/notifications")
    assert response.status_code == 401
    assert "Accesso richiesto" in response.json()["message"]
    assert response.json()["code"] == "invalid_credentials"


def test_overflow_extra_slot_is_compacted_when_a_free_slot_exists(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    from fantasy_teams.composition_service import reconcile_roster_overflow
    from fantasy_teams.models import FantasyTeam
    from leagues.models.league import League

    admin_token, _ = _register_and_login(client, "low3.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Slot Extra")
    guest = _seed_athlete(db_session, 9812, "Ospite In Piu")
    team_id = UUID(client.get(f"/leagues/{league_id}/rosa", headers=_hdr(admin_token)).json()["id"])
    team = db_session.get(FantasyTeam, team_id)
    league = db_session.get(League, UUID(league_id))
    top_index = max(
        slot.slot_index
        for slot in db_session.scalars(
            select(FantasyRosterSlot).where(FantasyRosterSlot.fantasy_team_id == team_id)
        )
    )
    db_session.add(
        FantasyRosterSlot(
            fantasy_team_id=team_id,
            league_id=UUID(league_id),
            slot_index=top_index + 1,
            athlete_id=guest.id,
            purchase_credits=7,
        )
    )
    db_session.commit()

    reconcile_roster_overflow(db_session, league=league, team=team)
    db_session.commit()

    db_session.expire_all()
    slots = list(
        db_session.scalars(
            select(FantasyRosterSlot).where(FantasyRosterSlot.fantasy_team_id == team_id)
        )
    )
    assert len(slots) == top_index + 1
    moved = next(slot for slot in slots if slot.athlete_id == guest.id)
    assert moved.slot_index <= top_index
    assert moved.purchase_credits == 7
