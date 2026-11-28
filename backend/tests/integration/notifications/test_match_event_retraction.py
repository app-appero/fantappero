"""«Gol annullato» e «Assist annullato»: la notifica dopo un gol o assist ritirato (28/11).

Si usa la partita del corpus 1035055 (West Ham 3–1 Chelsea): il gol di Antonio al 53' con
assist di Ward-Prowse (e il gol di Aguerd al 7' con assist dello stesso Ward-Prowse) viene
notificato mentre la partita è in corso («Gol di…», «Assist di…») e poi annullato, in due
modi: il fornitore toglie il gol dagli eventi, oppure lascia il gol e aggiunge un evento
«Var» «Goal Disallowed - offside».

Ogni proprietario sta in una sua lega (un utente, una lega, una squadra): così lo stesso
calciatore può stare in rosa di più persone, come in produzione.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from database.enums import (
    FantasyRoundHomologationStatus,
    FantasyTurnKind,
    FantasyTurnStatus,
    NotificationCategory,
)
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from notifications.models import Notification
from notifications.service import NotificationService
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
FIXTURE_ID = 1035055
ANTONIO = 18819  # gol al 53', assist di Ward-Prowse
WARD_PROWSE = 2938  # assist al 7' (gol di Aguerd) e al 53' (gol di Antonio)
FORNALS = 1697
GOAL_INDEX = 8  # Antonio 53'

GOAL_RETRACTED = "risultati.gol_annullato"
ASSIST_RETRACTED = "risultati.assist_annullato"


@pytest.fixture(autouse=True)
def clean_tables(db_session: Session) -> None:
    db_session.execute(update(FantasyRosterSlot).values(athlete_id=None))
    db_session.execute(delete(FantasyRoundFixture))
    db_session.execute(delete(OfficialLineupEntry))
    db_session.execute(delete(OfficialLineup))
    db_session.execute(delete(PlayerMatchStat))
    db_session.execute(delete(MatchEvent))
    db_session.execute(delete(Fixture))
    db_session.execute(delete(Athlete))
    db_session.commit()


# -- Dati del fornitore -----------------------------------------------------------------------


def _load(name: str) -> dict:
    path = DATASET / "matches" / "39" / str(FIXTURE_ID) / name
    return json.loads(path.read_text(encoding="utf-8"))


def _fixtures(*, status: str = "2H", hours_since_kickoff: float = 1.0):
    """La partita del corpus, in corso (o come si vuole) e con l'inizio quando serve."""
    data = copy.deepcopy(_load("fixtures.json"))
    fixture = data["response"][0]["fixture"]
    fixture["status"] = {"short": status, "long": status, "elapsed": 60, "extra": None}
    kickoff = datetime.now(UTC) - timedelta(hours=hours_since_kickoff)
    fixture["date"] = kickoff.isoformat()
    fixture["timestamp"] = int(kickoff.timestamp())
    return parse_envelope(data, endpoint="/fixtures", http_status=200)


def _events(
    *,
    without_goal: bool = False,
    var: str | None = None,
    goal_minute: int | None = None,
    goal_assist: dict | None = None,
) -> dict:
    events = copy.deepcopy(_load("fixtures_events.json"))
    goal = events["response"][GOAL_INDEX]
    assert goal["player"]["id"] == ANTONIO and goal["assist"]["id"] == WARD_PROWSE
    if goal_minute is not None:
        goal["time"]["elapsed"] = goal_minute
    if goal_assist is not None:
        goal["assist"] = goal_assist
    if without_goal:
        events["response"].pop(GOAL_INDEX)
    if var is not None:
        events["response"].insert(
            GOAL_INDEX + 1,
            {
                "assist": {"id": None, "name": None},
                "comments": None,
                "detail": var,
                "player": {"id": ANTONIO, "name": "Michail Antonio"},
                "team": {"id": 48, "name": "West Ham"},
                "time": {"elapsed": 54, "extra": None},
                "type": "Var",
            },
        )
    return events


def _seed_catalog(session: Session) -> None:
    ref = DATASET / "reference"
    leagues = parse_envelope(
        json.loads((ref / "leagues.json").read_text(encoding="utf-8")),
        endpoint="/leagues",
        http_status=200,
    )
    teams = parse_envelope(
        json.loads((ref / "teams.json").read_text(encoding="utf-8")),
        endpoint="/teams",
        http_status=200,
    )
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026)],
    )
    session.commit()


def _sync(db_session: Session, *, events: dict, fixtures=None) -> None:
    """Una sincronizzazione della partita (solo calendario ed eventi, come il giro dal vivo)."""
    batch = FixtureDetailBatch(
        fixture_provider_id=FIXTURE_ID,
        events_envelope=parse_envelope(events, endpoint="/fixtures/events", http_status=200),
    )
    sync_fixtures(
        db_session,
        fixtures_envelopes=[fixtures or _fixtures()],
        detail_batches=[batch],
    )
    db_session.commit()


# -- Utenti, leghe e rose ---------------------------------------------------------------------


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


@pytest.fixture
def athletes(db_session: Session) -> dict[int, Athlete]:
    rows = {
        ANTONIO: Athlete(provider_id=ANTONIO, canonical_name="Michail Antonio"),
        WARD_PROWSE: Athlete(provider_id=WARD_PROWSE, canonical_name="James Ward-Prowse"),
        FORNALS: Athlete(provider_id=FORNALS, canonical_name="Pablo Fornals"),
    }
    db_session.add_all(rows.values())
    db_session.commit()
    return rows


class _Owner:
    def __init__(self, user_id: UUID, team_id: UUID, team_name: str, league_id: UUID) -> None:
        self.user_id = user_id
        self.team_id = team_id
        self.team_name = team_name
        self.league_id = league_id


def _owner(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    email: str,
    players: list[Athlete],
) -> _Owner:
    token, user_id = _register_and_login(client, email)
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Lega {email.split('@')[0]}",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = UUID(created.json()["id"])
    team = db_session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == league_id)).one()
    owner = _Owner(user_id, team.id, team.name, league_id)
    _give(db_session, owner, players)
    return owner


def _give(db_session: Session, owner: _Owner, players: list[Athlete]) -> None:
    slots = db_session.scalars(
        select(FantasyRosterSlot)
        .where(FantasyRosterSlot.fantasy_team_id == owner.team_id)
        .order_by(FantasyRosterSlot.slot_index.asc())
    ).all()
    for slot, athlete in zip(slots, players, strict=False):
        slot.athlete_id = athlete.id
        slot.purchase_credits = 1
    db_session.commit()


def _notes(db_session: Session, owner: _Owner, template_key: str) -> list[Notification]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Notification)
            .where(Notification.user_id == owner.user_id, Notification.template_key == template_key)
            .order_by(Notification.created_at.asc())
        ).all()
    )


def _retraction_count(db_session: Session, owners: list[_Owner]) -> int:
    db_session.expire_all()
    return len(
        db_session.scalars(
            select(Notification.id).where(
                Notification.user_id.in_([owner.user_id for owner in owners]),
                Notification.template_key.in_([GOAL_RETRACTED, ASSIST_RETRACTED]),
            )
        ).all()
    )


def _goal_event_id(db_session: Session) -> UUID:
    return db_session.scalars(
        select(MatchEvent.id).where(
            MatchEvent.scoring_kind == "goal", MatchEvent.athlete_provider_id == ANTONIO
        )
    ).one()


# -- Prove ------------------------------------------------------------------------------------


def test_cancelled_goal_and_assist_reach_only_who_got_the_original(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    _seed_catalog(db_session)
    antonio, ward = athletes[ANTONIO], athletes[WARD_PROWSE]
    both = _owner(client, db_session, competition_ids, "ret-both@example.com", [antonio, ward])
    scorer_only = _owner(client, db_session, competition_ids, "ret-scorer@example.com", [antonio])
    # Ha l'interruttore «Gol» spento fin dall'inizio: l'originale non gli è mai arrivata.
    switched_off = _owner(client, db_session, competition_ids, "ret-off@example.com", [antonio])
    NotificationService(db_session).update_event_preference(
        user_id=switched_off.user_id,
        event_key="calciatori.gol",
        in_app_enabled=False,
        push_enabled=None,
    )
    # Compra Antonio dopo il gol: non aveva l'originale.
    latecomer = _owner(client, db_session, competition_ids, "ret-late@example.com", [])
    db_session.commit()

    _sync(db_session, events=_events())

    assert len(_notes(db_session, both, "risultati.gol")) == 1
    assert len(_notes(db_session, both, "risultati.assist")) == 2  # gol di Aguerd e di Antonio
    assert len(_notes(db_session, scorer_only, "risultati.gol")) == 1
    assert _notes(db_session, switched_off, "risultati.gol") == []
    goal_id = _goal_event_id(db_session)
    _give(db_session, latecomer, [antonio])

    # Il fornitore toglie il gol di Antonio (e con lui l'assist di Ward-Prowse).
    _sync(db_session, events=_events(without_goal=True))

    goal_notes = _notes(db_session, both, GOAL_RETRACTED)
    assert len(goal_notes) == 1
    note = goal_notes[0]
    assert note.category == NotificationCategory.RISULTATI
    assert note.template_version == 1
    assert note.title == "Gol annullato"
    assert note.body == (
        "Il gol di Michail Antonio (West Ham) è stato annullato. "
        f"Il bonus è stato tolto a {both.team_name}."
    )
    assert note.deep_link == f"/turni?lega={both.league_id}"
    assert note.dedup_key == f"match_event_retracted:{goal_id}:{both.user_id}:{both.team_id}"

    assist_notes = _notes(db_session, both, ASSIST_RETRACTED)
    assert len(assist_notes) == 1  # solo quello del gol annullato, non l'assist del 7'
    assert assist_notes[0].title == "Assist annullato"
    assert assist_notes[0].body == (
        "L'assist di James Ward-Prowse (West Ham) sul gol di Michail Antonio è stato annullato. "
        f"Il bonus è stato tolto a {both.team_name}."
    )
    assert assist_notes[0].dedup_key == (
        f"match_event_retracted_assist:{goal_id}:{both.user_id}:{both.team_id}"
    )

    assert len(_notes(db_session, scorer_only, GOAL_RETRACTED)) == 1
    assert _notes(db_session, scorer_only, ASSIST_RETRACTED) == []
    # Nessuna originale, nessun avviso di annullamento.
    for outsider in (switched_off, latecomer):
        assert _notes(db_session, outsider, GOAL_RETRACTED) == []
        assert _notes(db_session, outsider, ASSIST_RETRACTED) == []

    everyone = [both, scorer_only, switched_off, latecomer]
    # «Gol annullato» a chi ha Antonio (2), «Assist annullato» a chi ha Ward-Prowse (1).
    assert _retraction_count(db_session, everyone) == 3

    # La stessa sincronizzazione ripetuta non rimanda nulla.
    _sync(db_session, events=_events(without_goal=True))
    assert _retraction_count(db_session, everyone) == 3

    # Il gol torna valido e viene annullato di nuovo: un solo avviso per evento (limite noto).
    _sync(db_session, events=_events())
    assert _retraction_count(db_session, everyone) == 3
    _sync(db_session, events=_events(without_goal=True))
    assert _retraction_count(db_session, everyone) == 3


def test_goal_cancelled_by_a_var_event_tells_the_reason(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    _seed_catalog(db_session)
    owner = _owner(
        client,
        db_session,
        competition_ids,
        "ret-var@example.com",
        [athletes[ANTONIO], athletes[WARD_PROWSE]],
    )
    _sync(db_session, events=_events())
    assert _notes(db_session, owner, GOAL_RETRACTED) == []

    # Il gol resta fra gli eventi, ma segue «Goal Disallowed - offside».
    _sync(db_session, events=_events(var="Goal Disallowed - offside"))

    (goal_note,) = _notes(db_session, owner, GOAL_RETRACTED)
    assert goal_note.body == (
        "Il gol di Michail Antonio (West Ham) è stato annullato (fuorigioco). "
        f"Il bonus è stato tolto a {owner.team_name}."
    )
    (assist_note,) = _notes(db_session, owner, ASSIST_RETRACTED)
    assert "(fuorigioco)" in assist_note.body
    assert "sul gol di Michail Antonio" in assist_note.body

    # Lo stesso Var visto di nuovo non manda altro.
    _sync(db_session, events=_events(var="Goal Disallowed - offside"))
    assert len(_notes(db_session, owner, GOAL_RETRACTED)) == 1


def test_goal_cancelled_by_a_var_without_a_known_reason_has_no_reason(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    _seed_catalog(db_session)
    owner = _owner(
        client, db_session, competition_ids, "ret-cancel@example.com", [athletes[ANTONIO]]
    )
    _sync(db_session, events=_events())
    _sync(db_session, events=_events(var="Goal cancelled"))
    (goal_note,) = _notes(db_session, owner, GOAL_RETRACTED)
    assert goal_note.body == (
        "Il gol di Michail Antonio (West Ham) è stato annullato. "
        f"Il bonus è stato tolto a {owner.team_name}."
    )


def test_preferences_gol_and_assist_switches_decide_each_cancellation(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    """Stessi interruttori delle notifiche originali, nessuna voce nuova: spegnere «Gol» dopo
    aver ricevuto «Gol di…» zittisce solo «Gol annullato», e così per «Assist»."""
    _seed_catalog(db_session)
    players = [athletes[ANTONIO], athletes[WARD_PROWSE]]
    gol_off = _owner(client, db_session, competition_ids, "ret-goloff@example.com", players)
    assist_off = _owner(client, db_session, competition_ids, "ret-assistoff@example.com", players)
    _sync(db_session, events=_events())

    service = NotificationService(db_session)
    service.update_event_preference(
        user_id=gol_off.user_id, event_key="calciatori.gol", in_app_enabled=False, push_enabled=None
    )
    service.update_event_preference(
        user_id=assist_off.user_id,
        event_key="calciatori.assist",
        in_app_enabled=False,
        push_enabled=None,
    )
    db_session.commit()

    _sync(db_session, events=_events(without_goal=True))

    assert _notes(db_session, gol_off, GOAL_RETRACTED) == []
    assert len(_notes(db_session, gol_off, ASSIST_RETRACTED)) == 1
    assert len(_notes(db_session, assist_off, GOAL_RETRACTED)) == 1
    assert _notes(db_session, assist_off, ASSIST_RETRACTED) == []


def test_push_and_quiet_hours_work_like_the_other_match_notifications(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from auth.models.user_profile import UserProfile

    pushes: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            pushes.append(kwargs)

    monkeypatch.setattr("notifications.tasks.send_push_task", _FakeTask())
    monkeypatch.setattr(
        "notifications.push_dispatch.get_api_settings",
        lambda: SimpleNamespace(notifications_push_enabled=True),
    )
    _seed_catalog(db_session)
    antonio = athletes[ANTONIO]
    normal = _owner(client, db_session, competition_ids, "ret-push@example.com", [antonio])
    quiet = _owner(client, db_session, competition_ids, "ret-quiet@example.com", [antonio])
    push_off = _owner(client, db_session, competition_ids, "ret-nopush@example.com", [antonio])

    # Orari di silenzio intorno all'ora attuale (a Roma): niente push, la campanella sì.
    from zoneinfo import ZoneInfo

    local_hour = datetime.now(ZoneInfo("Europe/Rome")).hour
    profile = db_session.get(UserProfile, quiet.user_id)
    assert profile is not None
    profile.timezone = "Europe/Rome"
    profile.quiet_hours_start_hour = (local_hour - 1) % 24
    profile.quiet_hours_end_hour = (local_hour + 2) % 24
    NotificationService(db_session).update_event_preference(
        user_id=push_off.user_id,
        event_key="calciatori.gol",
        in_app_enabled=None,
        push_enabled=False,
    )
    db_session.commit()

    _sync(db_session, events=_events())
    pushes.clear()
    _sync(db_session, events=_events(without_goal=True))

    for owner in (normal, quiet, push_off):
        assert len(_notes(db_session, owner, GOAL_RETRACTED)) == 1
    cancelled_pushes = [p for p in pushes if p["title"] == "Gol annullato"]
    assert [p["user_id"] for p in cancelled_pushes] == [str(normal.user_id)]
    assert cancelled_pushes[0]["category"] == "risultati"
    assert str(cancelled_pushes[0]["deep_link"]).startswith("/turni")


def test_cancellation_is_not_sent_when_the_round_is_already_homologated(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    _seed_catalog(db_session)
    antonio = athletes[ANTONIO]
    open_round = _owner(client, db_session, competition_ids, "ret-open@example.com", [antonio])
    homologated = _owner(client, db_session, competition_ids, "ret-omo@example.com", [antonio])
    _sync(db_session, events=_events())
    assert len(_notes(db_session, homologated, "risultati.gol")) == 1

    now = datetime.now(UTC)
    fixture = db_session.scalars(select(Fixture).where(Fixture.provider_id == FIXTURE_ID)).one()
    fantasy_round = FantasyRound(
        league_id=homologated.league_id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=1),
        window_end_at=now + timedelta(days=1),
        status=FantasyTurnStatus.LOCKED,
        generated_at=now,
        homologation_status=FantasyRoundHomologationStatus.HOMOLOGATED,
        homologated_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()
    db_session.add(
        FantasyRoundFixture(
            round_id=fantasy_round.id,
            league_id=homologated.league_id,
            fixture_id=fixture.id,
            observed_kickoff_at=fixture.kickoff_at,
        )
    )
    db_session.commit()

    _sync(db_session, events=_events(without_goal=True))

    assert len(_notes(db_session, open_round, GOAL_RETRACTED)) == 1
    assert _notes(db_session, homologated, GOAL_RETRACTED) == []


def test_cancellation_is_not_sent_for_a_match_finished_long_ago(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    _seed_catalog(db_session)
    owner = _owner(client, db_session, competition_ids, "ret-old@example.com", [athletes[ANTONIO]])
    _sync(db_session, events=_events())
    assert len(_notes(db_session, owner, "risultati.gol")) == 1

    # Una correzione tardiva, a più di un giorno dall'inizio della partita.
    _sync(
        db_session,
        events=_events(without_goal=True),
        fixtures=_fixtures(status="FT", hours_since_kickoff=30),
    )

    assert _notes(db_session, owner, GOAL_RETRACTED) == []
    # Il gol è comunque ritirato: il bonus c'è finché il fornitore non lo ricorregge.
    goal = db_session.scalars(
        select(MatchEvent).where(
            MatchEvent.scoring_kind == "goal", MatchEvent.athlete_provider_id == ANTONIO
        )
    ).one()
    assert goal.is_active is False


def test_cancellation_is_not_sent_when_the_goal_never_had_a_live_notification(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    """Partita già finita quando il gol è stato registrato (riempimento di una partita
    passata): nessun «Gol di…», quindi nessun «Gol annullato»."""
    _seed_catalog(db_session)
    owner = _owner(
        client,
        db_session,
        competition_ids,
        "ret-backfill@example.com",
        [athletes[ANTONIO], athletes[WARD_PROWSE]],
    )
    finished = _fixtures(status="FT", hours_since_kickoff=3)
    _sync(db_session, events=_events(), fixtures=finished)
    assert _notes(db_session, owner, "risultati.gol") == []

    _sync(db_session, events=_events(without_goal=True), fixtures=finished)

    assert _notes(db_session, owner, GOAL_RETRACTED) == []
    assert _notes(db_session, owner, ASSIST_RETRACTED) == []


def test_goal_only_recoded_by_the_provider_is_not_announced_as_cancelled(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    athletes: dict[int, Athlete],
) -> None:
    """Il fornitore corregge il minuto (o l'assist) del gol: la riga cambia chiave, la vecchia
    si ritira e ne compare una nuova, ma il gol c'è ancora. Non è un gol annullato."""
    _seed_catalog(db_session)
    owner = _owner(
        client,
        db_session,
        competition_ids,
        "ret-recode@example.com",
        [athletes[ANTONIO], athletes[WARD_PROWSE]],
    )
    _sync(db_session, events=_events())

    # Minuto 53 -> 54: stesso gol e stesso assist.
    _sync(db_session, events=_events(goal_minute=54))
    assert _notes(db_session, owner, GOAL_RETRACTED) == []
    assert _notes(db_session, owner, ASSIST_RETRACTED) == []

    # Assist cambiato da Ward-Prowse a Fornals: il gol resta, l'assist di Ward-Prowse no.
    _sync(
        db_session,
        events=_events(goal_minute=54, goal_assist={"id": FORNALS, "name": "Pablo Fornals"}),
    )
    assert _notes(db_session, owner, GOAL_RETRACTED) == []
    (assist_note,) = _notes(db_session, owner, ASSIST_RETRACTED)
    assert assist_note.body.startswith("L'assist di James Ward-Prowse")
