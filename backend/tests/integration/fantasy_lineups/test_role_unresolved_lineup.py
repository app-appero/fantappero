# ruff: noqa: F811
"""Chi non ha un ruolo nel listone non blocca la formazione degli altri (decisione del 20/11).

Dal 20/11 (fee7bc8) la rosa con un calciatore senza ruolo nemmeno con i ripieghi del
risolutore (``role_unresolved``: niente listone di nessuna stagione, niente posizione nel club,
es. passato a un campionato che non copriamo) è ``invalid``, e ``roster_allows_lineup``
ammetteva la formazione solo per una rosa convalidata o non convalidata per gli esuberi
segnati: su dev alcune squadre QA non potevano più salvare nessuna formazione (400
``roster_not_validated``) finché il calciatore non veniva svincolato.

Decisione di Rosario, opzione (a): vale come chi è in esubero di ruolo. Resta in rosa (che
resta ``invalid`` con ``role_unresolved``), non si schiera (né titolare né nei primi 10 della
panchina) e non blocca gli altri. In tribuna si toglie senza errore; nel contesto della
formazione non c'è, perché web e app mettono in panchina tutta la rosa del contesto e
rifiutano da sé un panchinaro senza ruolo. Chi è già in campo e bloccato resta per il turno.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_role_excess_lineup_payload import (
    ACTIVE_BENCH_POSITION,
    _stored_lineup_ids,
)
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _lineup_payload,
    _lineup_url,
    _occupied_slots,
    _trade_league,
    competition_ids,
    db_session,
)

from database.enums import RosterCompositionStatus
from fantasy_lineups.models import LineupDraft
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from sports_data.catalog.models import Club
from sports_data.listone.models import RoleAssignment

#: Slot di `_fill_full_roster`: P 0-2, D 3-13, C 14-24, A 25-34. Il primo centrocampista è
#: titolare nella formazione di `_lineup_payload`.
FIRST_MIDFIELDER_SLOT = 14
UNRESOLVED_NAME = "SqA C1"
SINGLE_MESSAGE = (
    f"{UNRESOLVED_NAME} non ha un ruolo nel listone: non può essere schierato finché non lo riceve."
)


def _slot_athlete(db_session: Session, team_id: str, slot_index: int) -> UUID:
    db_session.expire_all()
    athlete_id = db_session.scalars(
        select(FantasyRosterSlot.athlete_id).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == slot_index,
        )
    ).one()
    assert athlete_id is not None
    return athlete_id


def _rosa(client: TestClient, setup: dict) -> dict:
    rosa = client.get(f"/leagues/{setup['league_id']}/rosa", headers=_headers(setup["token_a"]))
    assert rosa.status_code == 200, rosa.json()
    return rosa.json()


def _stored_status(db_session: Session, team_id: str) -> RosterCompositionStatus:
    db_session.expire_all()
    team = db_session.get(FantasyTeam, UUID(team_id))
    assert team is not None
    return team.composition_status


def _lose_role(db_session: Session, athlete_id: UUID) -> None:
    """Esce dal listone di ogni stagione e non ha una posizione nel club: nessun ripiego."""
    db_session.execute(delete(RoleAssignment).where(RoleAssignment.athlete_id == athlete_id))
    db_session.commit()


def _assert_roster_invalid_for_role_unresolved(
    client: TestClient, db_session: Session, setup: dict, unresolved_id: UUID
) -> None:
    """Stato salvato ``invalid`` e problema ``role_unresolved`` visibili in GET /rosa."""
    rosa = _rosa(client, setup)
    assert rosa["compositionStatus"] == RosterCompositionStatus.INVALID.value
    assert "role_unresolved" in {issue["code"] for issue in rosa["composition"]["issues"]}
    slot = next(row for row in rosa["slots"] if row["athleteId"] == str(unresolved_id))
    assert slot["role"] is None
    assert slot["exceedsRoleQuota"] is False
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.INVALID


def _unresolved_team(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    id_offset: int,
) -> tuple[dict, UUID]:
    """Rosa piena e convalidata in cui il primo centrocampista perde il ruolo nel listone."""
    setup = _trade_league(client, db_session, competition_ids, prefix=prefix, id_offset=id_offset)
    unresolved_id = _slot_athlete(db_session, setup["team_a"], FIRST_MIDFIELDER_SLOT)
    _lose_role(db_session, unresolved_id)
    # GET /rosa trova lo stato salvato scaduto ("validated") e lo riallinea.
    _assert_roster_invalid_for_role_unresolved(client, db_session, setup, unresolved_id)
    return setup, unresolved_id


def _payload(db_session: Session, setup: dict, unresolved_id: UUID, *, where: str) -> dict:
    """La formazione come la mandano web e app: lui in coda (tribuna) o forzato altrove."""
    slots = _occupied_slots(db_session, setup["team_a"])
    if where == "starter":
        payload = _lineup_payload(slots, setup["role_of"])
        assert str(unresolved_id) in payload["starterAthleteIds"]
        return payload
    payload = _lineup_payload(
        [slot for slot in slots if slot.athlete_id != unresolved_id], setup["role_of"]
    )
    if where == "tribuna":
        payload["benchAthleteIds"].append(str(unresolved_id))
    else:
        payload["benchAthleteIds"].insert(ACTIVE_BENCH_POSITION, str(unresolved_id))
    return payload


def test_save_with_the_unresolved_player_in_the_tribuna_succeeds_and_the_roster_stays_invalid(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, unresolved_id = _unresolved_team(
        client, db_session, competition_ids, prefix="sr.tribuna", id_offset=7_510_000
    )
    payload = _payload(db_session, setup, unresolved_id, where="tribuna")
    assert payload["benchAthleteIds"][-1] == str(unresolved_id)

    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)

    assert saved.status_code == 200, saved.json()
    body = saved.json()
    assert [item["athleteId"] for item in body["lineup"]["starters"]] == payload[
        "starterAthleteIds"
    ]
    assert [item["athleteId"] for item in body["lineup"]["bench"]] == payload["benchAthleteIds"][
        :-1
    ]
    stored = _stored_lineup_ids(db_session, setup)
    assert len(stored) == 34
    assert str(unresolved_id) not in stored
    assert body["issues"] == []
    # La rosa resta "invalid" con il problema visibile: cambia solo il permesso di schierare.
    _assert_roster_invalid_for_role_unresolved(client, db_session, setup, unresolved_id)

    # Nel contesto lui non c'è: la panchina che web e app ricostruiscono dalla `roster` è
    # quella salvata, quindi nessuna «1 modifica non salvata».
    roster_ids = {row["athleteId"] for row in body["roster"]}
    assert str(unresolved_id) not in roster_ids
    assert roster_ids == {*payload["starterAthleteIds"], *payload["benchAthleteIds"][:-1]}
    assert all(row["role"] is not None for row in body["roster"])

    # La stessa formazione rimandata (app già installate): identica, nessuna nuova revisione.
    again = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert again.status_code == 200, again.json()
    assert again.json()["lineup"]["revision"] == body["lineup"]["revision"]


def test_draft_with_the_unresolved_player_in_the_tribuna_succeeds_without_him(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, unresolved_id = _unresolved_team(
        client, db_session, competition_ids, prefix="sr.bozza", id_offset=7_520_000
    )
    payload = _payload(db_session, setup, unresolved_id, where="tribuna")

    saved = client.put(
        f"{_lineup_url(setup)}/bozza", headers=_headers(setup["token_a"]), json=payload
    )

    assert saved.status_code == 200, saved.json()
    draft = saved.json()["draft"]
    assert draft["starterAthleteIds"] == payload["starterAthleteIds"]
    assert draft["benchAthleteIds"] == payload["benchAthleteIds"][:-1]
    db_session.expire_all()
    stored = db_session.scalars(
        select(LineupDraft).where(
            LineupDraft.round_id == UUID(setup["round_id"]),
            LineupDraft.fantasy_team_id == UUID(setup["team_a"]),
        )
    ).one()
    assert str(unresolved_id) not in {*stored.starter_athlete_ids, *stored.bench_athlete_ids}
    assert _stored_status(db_session, setup["team_a"]) == RosterCompositionStatus.INVALID


@pytest.mark.parametrize(
    ("endpoint", "where", "id_offset"),
    [
        ("", "starter", 7_530_000),
        ("", "panchina", 7_540_000),
        ("/bozza", "starter", 7_550_000),
        ("/bozza", "panchina", 7_560_000),
    ],
)
def test_unresolved_player_as_starter_or_in_the_active_bench_is_rejected_by_name(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    endpoint: str,
    where: str,
    id_offset: int,
) -> None:
    setup, unresolved_id = _unresolved_team(
        client,
        db_session,
        competition_ids,
        prefix=f"sr{endpoint.replace('/', '.')}.{where}",
        id_offset=id_offset,
    )
    payload = _payload(db_session, setup, unresolved_id, where=where)
    if where == "panchina":
        assert payload["benchAthleteIds"][ACTIVE_BENCH_POSITION] == str(unresolved_id)

    rejected = client.put(
        f"{_lineup_url(setup)}{endpoint}", headers=_headers(setup["token_a"]), json=payload
    )

    assert rejected.status_code == 400, rejected.json()
    assert rejected.json()["code"] == "athlete_role_unresolved"
    assert rejected.json()["message"] == SINGLE_MESSAGE
    assert _stored_lineup_ids(db_session, setup) == []


def test_a_roster_invalid_for_other_reasons_stays_blocked(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Senza di lui la rosa deve essere in regola: qui senza i club del 3° campionato resta
    bloccata; con i club di nuovo nei 3 campionati lui non blocca più."""
    id_offset = 7_570_000
    setup, unresolved_id = _unresolved_team(
        client, db_session, competition_ids, prefix="sr.campionati", id_offset=id_offset
    )
    payload = _payload(db_session, setup, unresolved_id, where="tribuna")
    team_a_athletes = [slot.athlete_id for slot in _occupied_slots(db_session, setup["team_a"])]
    # Club di `_seed_clubs_and_round`: due per campionato, provider id offset + 2*campionato (+1).
    third_competition_clubs = set(
        db_session.scalars(
            select(Club.id).where(Club.provider_id.in_([id_offset + 4, id_offset + 5]))
        ).all()
    )
    assert len(third_competition_clubs) == 2
    first_club = db_session.scalars(select(Club.id).where(Club.provider_id == id_offset)).one()
    moved = db_session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id.in_(team_a_athletes),
            RoleAssignment.club_id.in_(third_competition_clubs),
        )
    ).all()
    assert moved
    original_clubs = {assignment.id: assignment.club_id for assignment in moved}
    for assignment in moved:
        assignment.club_id = first_club
    db_session.commit()
    rosa = _rosa(client, setup)
    assert rosa["composition"]["competitionCount"] == 2

    for endpoint in ("", "/bozza"):
        blocked = client.put(
            f"{_lineup_url(setup)}{endpoint}", headers=_headers(setup["token_a"]), json=payload
        )
        assert blocked.status_code == 400, blocked.json()
        assert blocked.json()["code"] == "roster_not_validated"
    best = client.post(f"{_lineup_url(setup)}/migliore", headers=_headers(setup["token_a"]))
    assert best.status_code == 400, best.json()
    assert best.json()["code"] == "roster_not_validated"

    # Di nuovo nei 3 campionati: lui da solo non blocca.
    db_session.expire_all()
    for assignment_id, club_id in original_clubs.items():
        restored = db_session.get(RoleAssignment, assignment_id)
        assert restored is not None
        restored.club_id = club_id
    db_session.commit()
    _assert_roster_invalid_for_role_unresolved(client, db_session, setup, unresolved_id)
    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert saved.status_code == 200, saved.json()


def test_best_lineup_never_picks_the_unresolved_player(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, unresolved_id = _unresolved_team(
        client, db_session, competition_ids, prefix="sr.migliore", id_offset=7_580_000
    )

    best = client.post(f"{_lineup_url(setup)}/migliore", headers=_headers(setup["token_a"]))

    assert best.status_code == 200, best.json()
    draft = best.json()["draft"]
    assert draft is not None
    fielded = [*draft["starterAthleteIds"], *draft["benchAthleteIds"]]
    assert len([item for item in draft["starterAthleteIds"] if item]) == 11
    assert len(fielded) == 34
    assert str(unresolved_id) not in fielded
    # La bozza della formula si conferma così com'è.
    saved = client.put(
        _lineup_url(setup),
        headers=_headers(setup["token_a"]),
        json={
            "module": draft["module"],
            "starterAthleteIds": draft["starterAthleteIds"],
            "benchAthleteIds": draft["benchAthleteIds"],
        },
    )
    assert saved.status_code == 200, saved.json()
