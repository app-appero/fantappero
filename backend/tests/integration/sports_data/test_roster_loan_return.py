"""Rientro dal prestito e listone: la membership attiva segue la sequenza dei trasferimenti.

Caso Mandas (Rosario 21/11): portiere della Lazio, a settembre 2025 in prestito al
Bournemouth, nell'estate 2026 rientrato («Back from Loan»). Titolare della Lazio
2026/27, ma assente dal listone perché bastava un trasferimento in uscita dalla Lazio,
di qualunque data, per salvare inattiva la sua membership 2026.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from admin.listone_service import AdminListoneService
from auth.models.user import User
from authorization.context import LeagueAccess
from config.settings.loader import get_api_settings
from database.enums import LeagueMemberRole, LeagueState, PlatformRole, UserType
from leagues.listone_service import LeagueListoneService
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from sports_data.catalog.models import Club, SportSeason
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.listone.generate import generate_official_listone
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.provider.envelope import parse_envelope
from sports_data.provider.types import ProviderEnvelope
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.roster.sync import sync_mvp_roster_with_client

SEASON = 2026
SERIE_A = 135
PREMIER = 39
LAZIO = (487, "Lazio")
BOURNEMOUTH = (35, "Bournemouth")
NAPOLI = (492, "Napoli")
MANDAS = 900_101
#: Compagni di squadra, così la rosa non resta vuota.
LAZIO_MATE = 900_102
BOURNEMOUTH_MATE = 900_103


DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


@pytest.fixture(autouse=True)
def clean_tables(session: Session) -> None:
    session.execute(delete(LeagueRoleOverride))
    session.execute(delete(RoleAssignment))
    session.execute(delete(SquadMembership))
    session.execute(delete(Transfer))
    session.execute(delete(Athlete))
    session.commit()


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def _envelope(endpoint: str, response: list[dict[str, Any]], **params: Any) -> ProviderEnvelope:
    payload = {
        "errors": [],
        "get": endpoint.lstrip("/"),
        "parameters": {key: str(value) for key, value in params.items()},
        "paging": {"current": 1, "total": 1},
        "results": len(response),
        "response": response,
    }
    return parse_envelope(payload, endpoint=endpoint, http_status=200)


def _teams(*clubs: tuple[int, str]) -> ProviderEnvelope:
    return _envelope(
        "/teams",
        [{"team": {"id": club_id, "name": name, "national": False}} for club_id, name in clubs],
    )


def _squad(club: tuple[int, str], players: list[tuple[int, str, str]]) -> ProviderEnvelope:
    club_id, name = club
    return _envelope(
        "/players/squads",
        [
            {
                "team": {"id": club_id, "name": name},
                "players": [
                    {"id": pid, "name": pname, "position": position}
                    for pid, pname, position in players
                ],
            }
        ],
        team=club_id,
    )


def _players(
    club: tuple[int, str],
    league_id: int,
    players: list[tuple[int, str, str]],
) -> ProviderEnvelope:
    club_id, name = club
    return _envelope(
        "/players",
        [
            {
                "player": {"id": pid, "name": pname},
                "statistics": [
                    {
                        "team": {"id": club_id, "name": name},
                        "league": {"id": league_id, "season": SEASON},
                        "games": {"position": position},
                    }
                ],
            }
            for pid, pname, position in players
        ],
        team=club_id,
        season=SEASON,
    )


def _transfers(
    athlete_id: int,
    name: str,
    moves: list[tuple[str, str, tuple[int, str], tuple[int, str]]],
) -> ProviderEnvelope:
    """``moves``: (data, tipo, club di uscita, club di arrivo)."""
    return _envelope(
        "/transfers",
        [
            {
                "player": {"id": athlete_id, "name": name},
                "transfers": [
                    {
                        "date": when,
                        "type": kind,
                        "teams": {
                            "out": {"id": out[0], "name": out[1]},
                            "in": {"id": into[0], "name": into[1]},
                        },
                    }
                    for when, kind, out, into in moves
                ],
            }
        ],
    )


class _FakeProvider:
    """Risponde come API-Football alle chiamate di «aggiorna listone» (rose)."""

    def __init__(
        self,
        *,
        squads: dict[int, ProviderEnvelope],
        players: dict[int, ProviderEnvelope],
        transfers: dict[int, ProviderEnvelope],
    ) -> None:
        self._by_endpoint = {
            "/players/squads": squads,
            "/players": players,
            "/transfers": transfers,
        }

    def get(self, endpoint: str, params: dict[str, Any]) -> ProviderEnvelope:
        found = self._by_endpoint[endpoint].get(int(params["team"]))
        return found if found is not None else _envelope(endpoint, [], **params)


def _seed_catalog(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[
            TeamsBatch(
                envelope=_teams(LAZIO, NAPOLI), competition_provider_id=SERIE_A, season_year=SEASON
            ),
            TeamsBatch(
                envelope=_teams(BOURNEMOUTH),
                competition_provider_id=PREMIER,
                season_year=SEASON,
            ),
        ],
    )
    session.commit()


def _aggiorna_listone(session: Session, provider: _FakeProvider) -> None:
    """Stesso percorso del listone operatore: rose dal provider, poi listone ufficiale."""
    sync_mvp_roster_with_client(
        session,
        provider,  # type: ignore[arg-type]
        season_year=SEASON,
        store_snapshots=False,
    )
    generate_official_listone(session, season_year=SEASON)
    session.commit()


def _club(session: Session, provider_id: int) -> Club:
    return session.execute(select(Club).where(Club.provider_id == provider_id)).scalar_one()


def _athlete(session: Session, provider_id: int) -> Athlete:
    return session.execute(select(Athlete).where(Athlete.provider_id == provider_id)).scalar_one()


def _membership(session: Session, athlete_pid: int, club_pid: int) -> SquadMembership | None:
    return session.execute(
        select(SquadMembership)
        .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
        .where(
            SquadMembership.athlete_id == _athlete(session, athlete_pid).id,
            SquadMembership.club_id == _club(session, club_pid).id,
            SportSeason.year == SEASON,
        ),
    ).scalar_one_or_none()


def _membership_state(
    session: Session, athlete_pid: int, club_pid: int
) -> tuple[bool, date | None]:
    row = _membership(session, athlete_pid, club_pid)
    assert row is not None
    session.refresh(row)
    return row.is_active, row.ended_at


def _serie_a_league_access(session: Session) -> LeagueAccess:
    user = User(
        email=f"listone-prestito-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        user_type=UserType.HUMAN,
    )
    session.add(user)
    serie_a = session.execute(
        select(Competition).where(Competition.provider_id == SERIE_A),
    ).scalar_one()
    league = League(
        name="Lega Serie A",
        season_year=SEASON,
        state=LeagueState.AUCTION,
        competitions=[serie_a],
    )
    session.add(league)
    session.flush()
    session.add(LeagueMembership(league_id=league.id, user_id=user.id, role=LeagueMemberRole.OWNER))
    session.commit()
    return LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)


def _loan_and_return_provider() -> _FakeProvider:
    mandas_moves = _transfers(
        MANDAS,
        "C. Mandas",
        [
            ("2026-06-30", "Back from Loan", BOURNEMOUTH, LAZIO),
            ("2025-09-01", "Loan", LAZIO, BOURNEMOUTH),
        ],
    )
    return _FakeProvider(
        squads={
            LAZIO[0]: _squad(
                LAZIO,
                [(MANDAS, "C. Mandas", "Goalkeeper"), (LAZIO_MATE, "M. Compagno", "Defender")],
            ),
            BOURNEMOUTH[0]: _squad(BOURNEMOUTH, [(BOURNEMOUTH_MATE, "B. Altro", "Defender")]),
        },
        players={
            LAZIO[0]: _players(LAZIO, SERIE_A, [(MANDAS, "C. Mandas", "Goalkeeper")]),
        },
        # API-Football restituisce la storia del calciatore per entrambe le squadre.
        transfers={LAZIO[0]: mandas_moves, BOURNEMOUTH[0]: mandas_moves},
    )


def test_back_from_loan_keeps_membership_active_and_athlete_in_both_listoni(
    session: Session,
) -> None:
    _seed_catalog(session)

    _aggiorna_listone(session, _loan_and_return_provider())

    assert _membership_state(session, MANDAS, LAZIO[0]) == (True, None)
    bournemouth = _membership(session, MANDAS, BOURNEMOUTH[0])
    assert bournemouth is None or bournemouth.is_active is False

    mandas_id = str(_athlete(session, MANDAS).id)
    league_entries = {
        entry.athlete_id: entry
        for entry in LeagueListoneService(session).list_entries(_serie_a_league_access(session))
    }
    assert mandas_id in league_entries
    assert league_entries[mandas_id].official_role == "P"
    assert league_entries[mandas_id].club_name == "Lazio"

    operator_entries = {
        entry.athlete_id: entry
        for entry in AdminListoneService(session, get_api_settings()).list_entries(
            season_year=SEASON
        )
    }
    assert mandas_id in operator_entries
    assert operator_entries[mandas_id].club_name == "Lazio"


def test_permanent_transfer_out_during_season_closes_old_membership(session: Session) -> None:
    _seed_catalog(session)
    striker = 900_201
    # Prima sync: in rosa al Napoli, nessun trasferimento.
    _aggiorna_listone(
        session,
        _FakeProvider(
            squads={NAPOLI[0]: _squad(NAPOLI, [(striker, "S. Ceduto", "Attacker")])},
            players={},
            transfers={},
        ),
    )
    assert _membership_state(session, striker, NAPOLI[0]) == (True, None)

    # Ceduto a titolo definitivo a stagione iniziata (Serie A 2026 dal 22/08/2026);
    # la rosa del Napoli lo elenca ancora (dato del provider in ritardo). Con lui un
    # compagno ceduto lo stesso giorno che il sistema vede per la prima volta.
    newcomer = 900_202
    sales = _envelope(
        "/transfers",
        [
            *_transfers(striker, "S. Ceduto", [("2026-09-01", "Transfer", NAPOLI, LAZIO)]).response,
            *_transfers(newcomer, "N. Nuovo", [("2026-09-01", "Transfer", NAPOLI, LAZIO)]).response,
        ],
    )
    napoli_squad = [(striker, "S. Ceduto", "Attacker"), (newcomer, "N. Nuovo", "Defender")]
    provider = _FakeProvider(
        squads={
            NAPOLI[0]: _squad(NAPOLI, napoli_squad),
            LAZIO[0]: _squad(LAZIO, napoli_squad),
        },
        players={},
        transfers={NAPOLI[0]: sales, LAZIO[0]: sales},
    )
    _aggiorna_listone(session, provider)

    assert _membership_state(session, striker, NAPOLI[0]) == (False, date(2026, 9, 1))
    # Riga nuova già inattiva: chiusa alla data della cessione, non senza data.
    assert _membership_state(session, newcomer, NAPOLI[0]) == (False, date(2026, 9, 1))
    assert _membership_state(session, newcomer, LAZIO[0]) == (True, None)
    assert _membership_state(session, striker, LAZIO[0]) == (True, None)
    assignment = session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == _athlete(session, striker).id),
    ).scalar_one()
    assert assignment.club_id == _club(session, LAZIO[0]).id


def test_old_transfer_out_before_season_with_athlete_back_in_squad_stays_active(
    session: Session,
) -> None:
    _seed_catalog(session)
    midfielder = 900_301
    # Uscito dalla Lazio nel 2023 (rientro non tracciato dal provider), di nuovo
    # nella rosa attuale della Lazio. La rosa completa del Bournemouth non lo elenca:
    # chiude la membership 2026 che il vecchio trasferimento gli apre lì.
    bournemouth_squad = [(900_310 + n, f"B. Rosa {n}", "Defender") for n in range(10)]
    provider = _FakeProvider(
        squads={
            LAZIO[0]: _squad(LAZIO, [(midfielder, "R. Tornato", "Midfielder")]),
            BOURNEMOUTH[0]: _squad(BOURNEMOUTH, bournemouth_squad),
        },
        players={},
        transfers={
            LAZIO[0]: _transfers(
                midfielder, "R. Tornato", [("2023-07-01", "Transfer", LAZIO, BOURNEMOUTH)]
            ),
        },
    )
    _aggiorna_listone(session, provider)

    assert _membership_state(session, midfielder, LAZIO[0]) == (True, None)
    assignment = session.execute(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == _athlete(session, midfielder).id,
        ),
    ).scalar_one()
    assert assignment.club_id == _club(session, LAZIO[0]).id


def test_resync_is_idempotent_and_reactivates_a_row_saved_inactive(session: Session) -> None:
    _seed_catalog(session)
    provider = _loan_and_return_provider()
    _aggiorna_listone(session, provider)

    # Com'era salvata prima della correzione: inattiva, chiusa al prestito.
    row = _membership(session, MANDAS, LAZIO[0])
    assert row is not None
    row.is_active = False
    row.ended_at = date(2025, 9, 1)
    session.execute(delete(RoleAssignment))
    session.commit()

    _aggiorna_listone(session, provider)
    first = _membership_state(session, MANDAS, LAZIO[0])
    first_bournemouth = _membership_state(session, MANDAS, BOURNEMOUTH[0])
    assert first == (True, None)
    assert first_bournemouth[0] is False

    _aggiorna_listone(session, provider)
    assert _membership_state(session, MANDAS, LAZIO[0]) == first
    assert _membership_state(session, MANDAS, BOURNEMOUTH[0]) == first_bournemouth
    assert len(session.execute(select(Transfer)).scalars().all()) == 2
    mandas_id = _athlete(session, MANDAS).id
    assignment = session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == mandas_id),
    ).scalar_one()
    assert assignment.club_id == _club(session, LAZIO[0]).id
