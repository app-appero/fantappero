# ruff: noqa: F811
"""Chi è in esubero di ruolo nella panchina mandata da web e app (QA 19/11, qa-02).

Su dev qa-02 aveva un attaccante in esubero (A. Adams, ``exceedsRoleQuota: true``). Web e app
costruiscono la panchina con tutta la rosa e lo mettono in coda, in tribuna: ogni salvataggio
e ogni bozza rispondevano 400 ``athlete_not_in_roster`` con il messaggio generico «Uno o più
calciatori schierati non appartengono alla rosa.» (lui in rosa c'è, quindi nessun nome).

In tribuna non gioca mai: il server lo toglie senza errore e non lo salva, così funzionano anche
le app già installate. Titolare o nei primi 10 della panchina, invece, la formazione è rifiutata
con un messaggio che lo nomina.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_role_excess_self_heal import (
    _legacy_midfielder_turned_forward,
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

from fantasy_lineups.models import LineupDraft, LineupPlayer, LineupSubmission
from sports_data.roster.models import Athlete

#: Posto nella panchina mandata quando lo si forza tra i primi 10 (8°, tra gli attaccanti).
ACTIVE_BENCH_POSITION = 7


def _excess_team(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    id_offset: int,
) -> tuple[dict, UUID, str]:
    """Rosa come qa-02: 11 attaccanti su 10, l'ultimo segnato in esubero all'apertura."""
    setup = _trade_league(client, db_session, competition_ids, prefix=prefix, id_offset=id_offset)
    excess_id = _legacy_midfielder_turned_forward(db_session, setup)
    context = client.get(_lineup_url(setup), headers=_headers(setup["token_a"]))
    assert context.status_code == 200, context.json()
    flagged = [row["athleteId"] for row in context.json()["roster"] if row["exceedsRoleQuota"]]
    assert flagged == [str(excess_id)]
    athlete = db_session.get(Athlete, excess_id)
    assert athlete is not None
    return setup, excess_id, athlete.canonical_name


def _app_payload(db_session: Session, setup: dict, excess_id: UUID, *, where: str) -> dict:
    """La formazione come la mandano web e app: chi è in esubero in coda o forzato altrove."""
    slots = _occupied_slots(db_session, setup["team_a"])
    if where == "starter":
        return _lineup_payload(slots, setup["role_of"], include=excess_id)
    payload = _lineup_payload(slots, setup["role_of"])
    if where == "tribuna":
        payload["benchAthleteIds"].append(str(excess_id))
    else:
        payload["benchAthleteIds"].insert(ACTIVE_BENCH_POSITION, str(excess_id))
    return payload


def _stored_lineup_ids(db_session: Session, setup: dict) -> list[str]:
    db_session.expire_all()
    return [
        str(athlete_id)
        for athlete_id in db_session.scalars(
            select(LineupPlayer.athlete_id)
            .join(LineupSubmission, LineupSubmission.id == LineupPlayer.submission_id)
            .where(
                LineupSubmission.round_id == UUID(setup["round_id"]),
                LineupSubmission.fantasy_team_id == UUID(setup["team_a"]),
            )
        )
    ]


def test_save_with_the_excess_player_in_the_tribuna_succeeds_without_him(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, excess_id, _ = _excess_team(
        client, db_session, competition_ids, prefix="esu.tribuna", id_offset=9_810_000
    )
    payload = _app_payload(db_session, setup, excess_id, where="tribuna")
    assert payload["benchAthleteIds"][-1] == str(excess_id)

    saved = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)

    assert saved.status_code == 200, saved.json()
    lineup = saved.json()["lineup"]
    assert [item["athleteId"] for item in lineup["starters"]] == payload["starterAthleteIds"]
    assert [item["athleteId"] for item in lineup["bench"]] == payload["benchAthleteIds"][:-1]
    stored = _stored_lineup_ids(db_session, setup)
    assert len(stored) == 34
    assert str(excess_id) not in stored
    assert saved.json()["issues"] == []

    # La stessa formazione rimandata (app già installate): identica, nessuna nuova revisione.
    again = client.put(_lineup_url(setup), headers=_headers(setup["token_a"]), json=payload)
    assert again.status_code == 200, again.json()
    assert again.json()["lineup"]["revision"] == lineup["revision"]


def test_draft_with_the_excess_player_in_the_tribuna_succeeds_without_him(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup, excess_id, _ = _excess_team(
        client, db_session, competition_ids, prefix="esu.bozza", id_offset=9_820_000
    )
    payload = _app_payload(db_session, setup, excess_id, where="tribuna")

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
    assert str(excess_id) not in {*stored.starter_athlete_ids, *stored.bench_athlete_ids}


@pytest.mark.parametrize(
    ("endpoint", "where", "id_offset"),
    [
        ("", "starter", 9_830_000),
        ("", "panchina", 9_840_000),
        ("/bozza", "starter", 9_850_000),
        ("/bozza", "panchina", 9_860_000),
    ],
)
def test_excess_player_as_starter_or_in_the_active_bench_is_rejected_by_name(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    endpoint: str,
    where: str,
    id_offset: int,
) -> None:
    setup, excess_id, name = _excess_team(
        client,
        db_session,
        competition_ids,
        prefix=f"esu{endpoint.replace('/', '.')}.{where}",
        id_offset=id_offset,
    )
    payload = _app_payload(db_session, setup, excess_id, where=where)
    if where == "panchina":
        assert payload["benchAthleteIds"][ACTIVE_BENCH_POSITION] == str(excess_id)
    else:
        assert str(excess_id) in payload["starterAthleteIds"]

    rejected = client.put(
        f"{_lineup_url(setup)}{endpoint}", headers=_headers(setup["token_a"]), json=payload
    )

    assert rejected.status_code == 400, rejected.json()
    assert rejected.json()["code"] == "athlete_exceeds_role_quota"
    assert rejected.json()["message"] == (
        f"{name} è in esubero di ruolo: non può essere schierato finché la rosa non torna "
        "in regola."
    )
    assert _stored_lineup_ids(db_session, setup) == []
