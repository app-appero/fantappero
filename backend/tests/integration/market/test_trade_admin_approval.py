"""Integration tests for trade admin approval and limits (EP08-07 / FR-MKT-03)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
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


def test_require_trade_approval_defers_execution_until_admin_acts(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "approve.admin@example.com")
    member_token, member_id = _register_and_login(client, "approve.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Approvazione")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9701, "Destinatario Approvazione")
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)

    rules = _set_league_rules(client, league_id, admin_token, require_trade_approval=True)
    assert rules["options"]["requireTradeApproval"] is True

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 20,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "pending_approval"

    from notifications.models import Notification

    def trade_notes(user_id) -> list[str]:
        db_session.expire_all()
        return [
            row.dedup_key
            for row in db_session.scalars(
                select(Notification).where(Notification.user_id == user_id)
            ).all()
            if row.dedup_key and proposal["id"] in row.dedup_key
        ]

    # L'admin parte dello scambio riceve solo "da approvare", non anche "in attesa".
    admin_after_accept = trade_notes(admin_id)
    assert len(admin_after_accept) == 1
    assert "admin_review" in admin_after_accept[0]

    # Nothing moved yet: the player is still with the recipient.
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(recipient_team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot.athlete_id == recipient_athlete.id

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "executed"
    # Chi approva non riceve l'avviso della propria azione; l'altra parte sì.
    assert trade_notes(admin_id) == admin_after_accept
    assert any("executed" in key for key in trade_notes(member_id))

    db_session.expire_all()
    slot_after = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(recipient_team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot_after.athlete_id is None  # moved out to the proposer

    # Already-executed proposals cannot be approved again.
    again = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert again.status_code == 400
    assert again.json()["code"] == "trade_not_pending_approval"


def test_admin_can_reject_a_pending_approval_trade(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "approve.rej.admin@example.com")
    member_token, member_id = _register_and_login(client, "approve.rej.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rifiuto Admin")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9702, "Destinatario Rifiuto Admin")
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)
    _set_league_rules(client, league_id, admin_token, require_trade_approval=True)

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 15,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()
    client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    rejected = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/rifiuta",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected_by_admin"

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(recipient_team_id))
    )
    assert account is not None
    assert account.balance == 1000  # untouched


def test_max_active_trade_proposals_per_team_is_enforced(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "limit.admin@example.com")
    member_token, member_id = _register_and_login(client, "limit.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Limite Scambi")
    _add_member(db_session, league_id, member_id)
    recipient_team_id = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {member_token}"}
    ).json()["id"]

    offered = _seed_athlete(db_session, 9951, "Giocatore Limite Scambi")
    _own_athlete_at_slot(client, league_id, admin_token, 0, offered)

    rules = _set_league_rules(client, league_id, admin_token, max_active_trade_proposals_per_team=2)
    assert rules["maxActiveTradeProposalsPerTeam"] == 2

    for _ in range(2):
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "recipientTeamId": recipient_team_id,
                "offeredAthleteIds": [str(offered.id)],
                "offeredCredits": 0,
                "requestedCredits": 5,
                "expiresAt": _future_iso(),
            },
        )
        assert response.status_code == 201

    over_limit = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredAthleteIds": [str(offered.id)],
            "offeredCredits": 0,
            "requestedCredits": 5,
            "expiresAt": _future_iso(),
        },
    )
    assert over_limit.status_code == 400
    assert over_limit.json()["code"] == "trade_active_limit_reached"


def test_concurrent_admin_approve_and_reject_only_one_transition_wins(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """B5: due decisioni amministrative concorrenti (approva/rifiuta) sulla
    stessa proposta in attesa di approvazione devono risolversi in una sola
    transizione valida. Stesso meccanismo di lock di riga già provato per
    accetta/rifiuta del destinatario in test_trade_decision.py
    (`_lock_pending_approval_proposal` usa lo stesso pattern di
    `_lock_actionable_proposal_as_recipient`) — qui lo verifichiamo
    direttamente sul percorso amministrativo, non per parentela di codice.
    """
    admin_token, admin_id = _register_and_login(client, "approve.race.admin@example.com")
    member_token, member_id = _register_and_login(client, "approve.race.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Corsa Approvazione")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9703, "Destinatario Corsa Admin")
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)
    _set_league_rules(client, league_id, admin_token, require_trade_approval=True)

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 15,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()
    client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    def _approve(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}"
            "/amministrazione/approva",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return response.status_code

    def _reject(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}"
            "/amministrazione/rifiuta",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_approve, 0),
            pool.submit(_reject, 1),
            pool.submit(_approve, 2),
            pool.submit(_reject, 3),
        ]
        statuses = [future.result() for future in futures]

    assert statuses.count(200) == 1
    assert statuses.count(400) == 3

    db_session.expire_all()
    row = db_session.scalar(select(TradeProposal).where(TradeProposal.id == UUID(proposal["id"])))
    assert row is not None
    assert row.status.value in {"executed", "rejected_by_admin"}


def test_pending_approval_trade_with_moved_player_reads_as_expired(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    import random

    admin_token, _ = _register_and_login(client, "approve.stale.admin@example.com")
    member_token, member_id = _register_and_login(client, "approve.stale.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Approvazione Obsoleta")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(
        db_session, random.randint(100_000_000, 2_000_000_000), "Doppio Scambio"
    )
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, athlete)
    _set_league_rules(client, league_id, admin_token, require_trade_approval=True)

    def propose() -> dict:
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "recipientTeamId": recipient_team_id,
                "offeredCredits": 5,
                "requestedAthleteIds": [str(athlete.id)],
                "expiresAt": _future_iso(),
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    first, second = propose(), propose()
    base = f"/leagues/{league_id}/mercato/scambi/proposte"
    for proposal in (first, second):
        accepted = client.post(
            f"{base}/{proposal['id']}/accetta",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "pending_approval"

    approved = client.post(
        f"{base}/{first['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200

    detail = client.get(
        f"{base}/{second['id']}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"
    listed = client.get(base, headers={"Authorization": f"Bearer {admin_token}"}).json()
    rows = listed if isinstance(listed, list) else listed.get("proposals", listed.get("items", []))
    assert all(row["status"] != "pending_approval" for row in rows)


def _three_team_league_with_approval(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    limit: int,
    recipient_athletes: int,
) -> dict:
    """Admin che approva, allenatore A che propone, allenatore B con ``recipient_athletes``
    difensori in rosa. Scambi con approvazione dell'admin e limite ``limit``."""
    import random

    admin_token, _ = _register_and_login(client, f"{prefix}.admin@example.com")
    a_token, a_id = _register_and_login(client, f"{prefix}.a@example.com")
    b_token, b_id = _register_and_login(client, f"{prefix}.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, f"Lega {prefix}")
    _add_member(db_session, league_id, a_id)
    _add_member(db_session, league_id, b_id)
    base = random.randint(100_000_000, 2_000_000_000)
    a_athlete = _seed_athlete(db_session, base, f"{prefix} Offerto")
    team_a = _own_athlete_at_slot(client, league_id, a_token, 0, a_athlete)
    b_athletes = [
        _seed_athlete(db_session, base + 1 + index, f"{prefix} Richiesto {index}")
        for index in range(recipient_athletes)
    ]
    team_b = ""
    for index, athlete in enumerate(b_athletes):
        team_b = _own_athlete_at_slot(client, league_id, b_token, index, athlete)
    rules = _set_league_rules(
        client,
        league_id,
        admin_token,
        require_trade_approval=True,
        max_active_trade_proposals_per_team=limit,
    )
    assert rules["options"]["requireTradeApproval"] is True
    assert rules["maxActiveTradeProposalsPerTeam"] == limit
    return {
        "league_id": league_id,
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "a": {"Authorization": f"Bearer {a_token}"},
        "b": {"Authorization": f"Bearer {b_token}"},
        "team_a": team_a,
        "team_b": team_b,
        "a_athlete": a_athlete,
        "b_athletes": b_athletes,
        "base": f"/leagues/{league_id}/mercato/scambi/proposte",
    }


def test_trades_awaiting_admin_approval_count_towards_the_active_limit(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """KI-21 (Rosario 24/11): lo scambio accettato e in attesa dell'admin è ancora una proposta
    attiva di chi l'ha fatta. Prima usciva dal conteggio e si potevano mandare altre proposte
    oltre il limite; ora la proposta in più è rifiutata finché l'admin non decide."""
    run = _three_team_league_with_approval(
        client, db_session, competition_ids, prefix="ki21.pending", limit=2, recipient_athletes=4
    )
    base = run["base"]

    def propose(athlete_index: int):
        return client.post(
            base,
            headers=run["a"],
            json={
                "recipientTeamId": run["team_b"],
                "offeredCredits": 5,
                "requestedAthleteIds": [str(run["b_athletes"][athlete_index].id)],
                "expiresAt": _future_iso(),
            },
        )

    first, second = propose(0), propose(1)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    accepted = client.post(f"{base}/{first.json()['id']}/accetta", headers=run["b"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "pending_approval"

    # Una proposta ancora da decidere + una in attesa dell'admin = limite raggiunto.
    over_limit = propose(2)
    assert over_limit.status_code == 400
    assert over_limit.json()["code"] == "trade_active_limit_reached"
    assert over_limit.json()["message"] == (
        "Hai raggiunto il limite di 2 proposte di scambio attive."
    )

    # In attesa dell'admin non scade con l'orario della proposta: continua a contare.
    row = db_session.get(TradeProposal, UUID(first.json()["id"]))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()
    still_over = propose(2)
    assert still_over.status_code == 400
    assert still_over.json()["code"] == "trade_active_limit_reached"

    # L'approvazione esegue lo scambio e libera il posto: si può proporre di nuovo, una volta.
    approved = client.post(
        f"{base}/{first.json()['id']}/amministrazione/approva", headers=run["admin"]
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "executed"
    third = propose(2)
    assert third.status_code == 201, third.text
    assert propose(3).json()["code"] == "trade_active_limit_reached"

    # Anche il rifiuto dell'admin libera il posto.
    accepted_second = client.post(f"{base}/{second.json()['id']}/accetta", headers=run["b"])
    assert accepted_second.json()["status"] == "pending_approval"
    assert propose(3).json()["code"] == "trade_active_limit_reached"
    rejected = client.post(
        f"{base}/{second.json()['id']}/amministrazione/rifiuta", headers=run["admin"]
    )
    assert rejected.status_code == 200, rejected.text
    fourth = propose(3)
    assert fourth.status_code == 201, fourth.text


def test_trade_awaiting_credits_cannot_be_accepted_into_admin_approval(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """KI-21: la proposta «in attesa di crediti» non conta nel limite (decisione del 14/11).
    Con l'approvazione dell'admin il destinatario non può accettarla finché i crediti non
    bastano, come senza approvazione: altrimenti, in attesa dell'admin, tornerebbe a contare e
    chi l'ha proposta supererebbe il limite."""
    run = _three_team_league_with_approval(
        client, db_session, competition_ids, prefix="ki21.credits", limit=1, recipient_athletes=1
    )
    base = run["base"]

    def propose(requested_credits: int):
        return client.post(
            base,
            headers=run["a"],
            json={
                "recipientTeamId": run["team_b"],
                "offeredAthleteIds": [str(run["a_athlete"].id)],
                "requestedCredits": requested_credits,
                "expiresAt": _future_iso(),
            },
        )

    waiting = propose(100)
    assert waiting.status_code == 201, waiting.text
    # B spende i crediti: la proposta resta aperta ma «in attesa di crediti» e libera il posto.
    spend = client.post(
        f"/leagues/{run['league_id']}/amministrazione/crediti/movimenti",
        headers=run["admin"],
        json={"fantasyTeamId": run["team_b"], "amount": -950, "transactionId": "ki21-spend"},
    )
    assert spend.status_code == 200, spend.text
    shown = client.get(f"{base}/{waiting.json()['id']}", headers=run["a"]).json()
    assert shown["status"] == "proposed"
    assert shown["awaitingCredits"] is True
    other = propose(5)
    assert other.status_code == 201, other.text

    blocked = client.post(f"{base}/{waiting.json()['id']}/accetta", headers=run["b"])
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "insufficient_credits"
    assert blocked.json()["message"] == (
        "Il destinatario non ha più crediti sufficienti per lo scambio."
    )
    after = client.get(f"{base}/{waiting.json()['id']}", headers=run["a"]).json()
    assert after["status"] == "proposed"
    assert after["awaitingCredits"] is True

    # La proposta con i crediti coperti si accetta normalmente e va all'admin; A resta al limite.
    accepted = client.post(f"{base}/{other.json()['id']}/accetta", headers=run["b"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "pending_approval"
    assert propose(5).json()["code"] == "trade_active_limit_reached"
