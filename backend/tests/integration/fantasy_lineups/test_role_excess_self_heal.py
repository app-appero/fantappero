# ruff: noqa: F811
"""Esubero di ruolo senza calciatore segnato: auto-riparazione dei flag (KO-A, QA 19/11).

Su dev (lega QA-PREP-PARI, squadra qa-02) la rosa era a 35/35 con 11 attaccanti su 10, ma
nessuno slot aveva ``exceeds_role_quota``: un'operazione precedente (un cambio di ruolo,
un'assegnazione o un import) aveva lasciato l'esubero senza segnarlo. ``roster_allows_lineup``
ammette la formazione solo se gli esuberi sono segnati, quindi il salvataggio rispondeva
sempre 400 ``roster_not_validated``.

Qui lo stato legacy si costruisce direttamente nel DB. Il sistema deve segnare da sé il
calciatore in più (il più recente del ruolo, poi lo slot più alto), lasciar schierare gli
altri e mostrare l'esubero in GET /rosa.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_payload,
    _lineup_url,
    _occupied_slots,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import FantasyRole, RosterCompositionStatus
from fantasy_teams.composition_service import sync_team_composition_status
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam, RosterOwnershipInterval
from leagues.models.league import League
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

#: Slot di `_fill_full_roster`: P 0-2, D 3-13, C 14-24, A 25-34.
LAST_MIDFIELDER_SLOT = 24
FIRST_MIDFIELDER_SLOT = 14
LAST_FORWARD_SLOT = 34


def _mark_legacy_invalid(db_session: Session, team_id: str) -> None:
    """Stato salvato come su dev: rosa non convalidata, nessun flag di esubero."""
    team = db_session.get(FantasyTeam, UUID(team_id))
    assert team is not None
    team.composition_status = RosterCompositionStatus.INVALID
    team.validated_at = None
    db_session.commit()


def _slot(db_session: Session, team_id: str, slot_index: int) -> FantasyRosterSlot:
    return db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == slot_index,
        )
    ).one()


def _legacy_eleventh_forward_newest(db_session: Session, setup: dict) -> UUID:
    """Un 11° attaccante acquistato per ultimo al posto dell'ultimo centrocampista.

    Tutti gli slot hanno un possesso attivo: l'acquisto più recente è lo slot 24, non lo
    slot più alto (34). Ritorna l'id del calciatore in esubero atteso.
    """
    team_id = setup["team_a"]
    base = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    slots = _occupied_slots(db_session, team_id)
    template = next(slot for slot in slots if slot.slot_index == LAST_FORWARD_SLOT)
    template_club = db_session.scalars(
        select(RoleAssignment.club_id).where(RoleAssignment.athlete_id == template.athlete_id)
    ).one()

    newcomer = Athlete(provider_id=9_931_500, canonical_name="SqA A11 legacy")
    db_session.add(newcomer)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=newcomer.id,
            season_year=2026,
            role=FantasyRole.A,
            mapping_version="v1.0.0",
            provider_position_raw="A",
            club_id=template_club,
        )
    )
    target = next(slot for slot in slots if slot.slot_index == LAST_MIDFIELDER_SLOT)
    target.athlete_id = newcomer.id
    target.purchase_credits = 1
    db_session.flush()

    for slot in slots:
        acquired = (
            base + timedelta(days=10)
            if slot.slot_index == LAST_MIDFIELDER_SLOT
            else base + timedelta(minutes=slot.slot_index)
        )
        db_session.add(
            RosterOwnershipInterval(
                league_id=UUID(setup["league_id"]),
                fantasy_team_id=UUID(team_id),
                athlete_id=slot.athlete_id,
                slot_index=slot.slot_index,
                purchase_credits=1,
                acquired_at=acquired,
            )
        )
    db_session.commit()
    _mark_legacy_invalid(db_session, team_id)
    setup["role_of"][newcomer.id] = FantasyRole.A
    return newcomer.id


def _legacy_midfielder_turned_forward(db_session: Session, setup: dict) -> UUID:
    """Il listone sposta un centrocampista tra gli attaccanti: C 10, A 11, come qa-02.

    Nessun possesso registrato: a parità di acquisto conta lo slot più alto, quindi
    l'esubero atteso è l'attaccante dello slot 34.
    """
    team_id = setup["team_a"]
    moved = _slot(db_session, team_id, FIRST_MIDFIELDER_SLOT)
    assignment = db_session.scalars(
        select(RoleAssignment).where(RoleAssignment.athlete_id == moved.athlete_id)
    ).one()
    assignment.role = FantasyRole.A
    setup["role_of"][moved.athlete_id] = FantasyRole.A
    db_session.commit()
    _mark_legacy_invalid(db_session, team_id)
    expected = _slot(db_session, team_id, LAST_FORWARD_SLOT).athlete_id
    assert expected is not None
    return expected


def _flagged(db_session: Session, team_id: str) -> list[tuple[int, UUID | None]]:
    return sorted(
        (slot.slot_index, slot.athlete_id)
        for slot in _occupied_slots(db_session, team_id)
        if slot.exceeds_role_quota
    )


def _rosa_flags(client: TestClient, setup: dict, token: str) -> list[int]:
    rosa = client.get(f"/leagues/{setup['league_id']}/rosa", headers=_headers(token))
    assert rosa.status_code == 200, rosa.json()
    return sorted(slot["slotIndex"] for slot in rosa.json()["slots"] if slot["exceedsRoleQuota"])


def test_unflagged_forward_excess_is_flagged_on_lineup_save_newest_first(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="koa.recente", id_offset=9_930_000
    )
    excess_id = _legacy_eleventh_forward_newest(db_session, setup)
    token = setup["token_a"]
    slots = _occupied_slots(db_session, setup["team_a"])
    assert len(slots) == 35
    assert not any(slot.exceeds_role_quota for slot in slots)

    # Formazione senza l'11° attaccante: si salva.
    without_excess = [slot for slot in slots if slot.athlete_id != excess_id]
    saved = client.put(
        _lineup_url(setup),
        headers=_headers(token),
        json=_lineup_payload(without_excess, setup["role_of"]),
    )
    assert saved.status_code == 200, saved.json()
    assert len(saved.json()["lineup"]["starters"]) == 11

    # Segnato l'acquisto più recente del ruolo (slot 24), non lo slot più alto (34).
    assert _flagged(db_session, setup["team_a"]) == [(LAST_MIDFIELDER_SLOT, excess_id)]

    # Il calciatore in esubero non è schierabile: il rifiuto dice chi è.
    with_excess = client.put(
        _lineup_url(setup),
        headers=_headers(token),
        json=_lineup_payload(
            _occupied_slots(db_session, setup["team_a"]), setup["role_of"], include=excess_id
        ),
    )
    assert with_excess.status_code == 400
    assert with_excess.json()["code"] == "athlete_exceeds_role_quota"
    assert with_excess.json()["message"].startswith("SqA A11 legacy è in esubero di ruolo")

    # GET /rosa mostra l'esubero proprio su quello slot.
    assert _rosa_flags(client, setup, token) == [LAST_MIDFIELDER_SLOT]

    # Idempotente: un nuovo salvataggio, la rosa e la sincronizzazione non cambiano i flag.
    again = client.put(
        _lineup_url(setup),
        headers=_headers(token),
        json=_lineup_payload(without_excess, setup["role_of"]),
    )
    assert again.status_code == 200, again.json()
    assert _rosa_flags(client, setup, token) == [LAST_MIDFIELDER_SLOT]
    team = db_session.get(FantasyTeam, UUID(setup["team_a"]))
    league = db_session.get(League, UUID(setup["league_id"]))
    assert team is not None and league is not None
    sync_team_composition_status(db_session, team, league=league, require_complete=False)
    db_session.commit()
    assert _flagged(db_session, setup["team_a"]) == [(LAST_MIDFIELDER_SLOT, excess_id)]


def test_rosa_flags_the_excess_of_a_role_change_on_the_highest_slot(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="koa.ruolo", id_offset=9_940_000
    )
    excess_id = _legacy_midfielder_turned_forward(db_session, setup)
    token = setup["token_a"]

    # La pagina rosa, aperta per prima, segna già l'esubero (stessa scelta deterministica).
    rosa = client.get(f"/leagues/{setup['league_id']}/rosa", headers=_headers(token))
    assert rosa.status_code == 200
    body = rosa.json()
    assert body["filledSlots"] == 35
    assert body["composition"]["counts"] == {"P": 3, "D": 11, "C": 10, "A": 11}
    flagged = [slot for slot in body["slots"] if slot["exceedsRoleQuota"]]
    assert [(slot["slotIndex"], slot["athleteId"]) for slot in flagged] == [
        (LAST_FORWARD_SLOT, str(excess_id))
    ]
    assert _flagged(db_session, setup["team_a"]) == [(LAST_FORWARD_SLOT, excess_id)]

    # La pagina formazione lo mostra in esubero e la formazione si salva senza di lui.
    context = client.get(_lineup_url(setup), headers=_headers(token))
    assert context.status_code == 200, context.json()
    in_excess = [row["athleteId"] for row in context.json()["roster"] if row["exceedsRoleQuota"]]
    assert in_excess == [str(excess_id)]
    saved = client.put(
        _lineup_url(setup),
        headers=_headers(token),
        json=_lineup_payload(_occupied_slots(db_session, setup["team_a"]), setup["role_of"]),
    )
    assert saved.status_code == 200, saved.json()
    assert _rosa_flags(client, setup, token) == [LAST_FORWARD_SLOT]


def test_composition_sync_flags_the_excess_once(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="koa.sync", id_offset=9_950_000
    )
    excess_id = _legacy_midfielder_turned_forward(db_session, setup)
    team = db_session.get(FantasyTeam, UUID(setup["team_a"]))
    league = db_session.get(League, UUID(setup["league_id"]))
    assert team is not None and league is not None

    for _ in range(2):
        report = sync_team_composition_status(
            db_session, team, league=league, require_complete=False
        )
        db_session.commit()
        # Il ruolo resta oltre quota (lo stato non cambia), ma l'esubero è segnato una volta.
        assert report.status == RosterCompositionStatus.INVALID
        assert _flagged(db_session, setup["team_a"]) == [(LAST_FORWARD_SLOT, excess_id)]


def test_roster_with_exact_quotas_gets_no_flags(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="koa.esatta", id_offset=9_920_000
    )
    token = setup["token_a"]
    slots = _occupied_slots(db_session, setup["team_a"])

    saved = client.put(
        _lineup_url(setup), headers=_headers(token), json=_lineup_payload(slots, setup["role_of"])
    )
    assert saved.status_code == 200, saved.json()
    assert _rosa_flags(client, setup, token) == []
    team = db_session.get(FantasyTeam, UUID(setup["team_a"]))
    league = db_session.get(League, UUID(setup["league_id"]))
    assert team is not None and league is not None
    report = sync_team_composition_status(db_session, team, league=league, require_complete=False)
    db_session.commit()
    assert report.status == RosterCompositionStatus.VALIDATED
    assert _flagged(db_session, setup["team_a"]) == []
