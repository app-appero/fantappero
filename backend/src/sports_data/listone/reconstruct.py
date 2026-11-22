"""Ruolo ufficiale di un calciatore prima di un certo momento, dalle risposte del fornitore.

Ogni sincronizzazione delle rose salva in ``provider_snapshots`` le risposte di
``/players/squads`` e ``/players`` di ogni club (una riga nuova solo se il contenuto cambia).
Da quelle salvate prima di ``before`` si rifà il calcolo del listone di allora: posizione del
calciatore nella rosa del club (``/players/squads``, scritta per ultima dalla sync, quindi
vince) o, se lì non c'è, nelle statistiche (``/players``), mappata con lo stesso mapping; fra
più club vale lo stesso ordine della scelta della membership (`membership_preference`).

Serve a «Ripristina i ruoli» del pannello operatore, dopo l'aggiornamento del 21/11 che ha
cambiato ruoli già assegnati.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from sports_data.catalog.models import Club, SportSeason
from sports_data.listone.generate import membership_preference
from sports_data.listone.mapping import map_provider_position_to_role
from sports_data.listone.models import RoleAssignment
from sports_data.provider.constants import MVP_LEAGUE_IDS, PROVIDER_NAME
from sports_data.provider.hashing import request_fingerprint
from sports_data.provider.models import ProviderSnapshot
from sports_data.roster.models import Athlete, SquadMembership, Transfer

SQUADS_ENDPOINT = "/players/squads"
PLAYERS_ENDPOINT = "/players"
_CHUNK = 1000


@dataclass(frozen=True)
class ReconstructedRole:
    role: FantasyRole
    provider_position_raw: str
    club_id: UUID
    #: ``squads`` (rosa del club) o ``players`` (statistiche).
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class _ClubPositions:
    by_athlete: dict[int, str]
    fetched_at: datetime


def _chunks(ids: list[UUID]) -> Iterator[list[UUID]]:
    for start in range(0, len(ids), _CHUNK):
        yield ids[start : start + _CHUNK]


def _latest_snapshot_before(
    session: Session,
    *,
    endpoint: str,
    params: dict[str, Any],
    before: datetime,
) -> ProviderSnapshot | None:
    return session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.provider == PROVIDER_NAME,
            ProviderSnapshot.endpoint == endpoint,
            ProviderSnapshot.request_fingerprint == request_fingerprint(endpoint, params),
            ProviderSnapshot.fetched_at < before,
        )
        .order_by(ProviderSnapshot.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _position(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _squad_positions(payload: dict[str, Any], club_provider_id: int) -> dict[int, str]:
    """Come `map_squad_memberships`: posizione di ogni calciatore nella rosa del club."""
    out: dict[int, str] = {}
    for row in payload.get("response") or []:
        if not isinstance(row, dict):
            continue
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        if _as_int(team.get("id")) != club_provider_id:
            continue
        for player in row.get("players") or []:
            if not isinstance(player, dict):
                continue
            athlete_provider_id = _as_int(player.get("id"))
            position = _position(player.get("position"))
            if athlete_provider_id is not None and position is not None:
                out[athlete_provider_id] = position
    return out


def _players_positions(
    payload: dict[str, Any],
    club_provider_id: int,
    season_year: int,
) -> dict[int, str]:
    """Come `map_squad_memberships_from_players`: l'ultima statistica del club vince."""
    out: dict[int, str] = {}
    for row in payload.get("response") or []:
        if not isinstance(row, dict):
            continue
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        athlete_provider_id = _as_int(player.get("id"))
        if athlete_provider_id is None:
            continue
        for stat in row.get("statistics") or []:
            if not isinstance(stat, dict):
                continue
            league = stat.get("league") if isinstance(stat.get("league"), dict) else {}
            team = stat.get("team") if isinstance(stat.get("team"), dict) else {}
            games = stat.get("games") if isinstance(stat.get("games"), dict) else {}
            if _as_int(team.get("id")) != club_provider_id:
                continue
            if _as_int(league.get("id")) not in MVP_LEAGUE_IDS:
                continue
            if _as_int(league.get("season")) != season_year:
                continue
            position = _position(games.get("position"))
            if position is not None:
                out[athlete_provider_id] = position
    return out


def _club_positions(
    session: Session,
    *,
    endpoint: str,
    club_provider_id: int,
    season_year: int,
    before: datetime,
) -> _ClubPositions | None:
    if endpoint == SQUADS_ENDPOINT:
        params: dict[str, Any] = {"team": club_provider_id}
    else:
        params = {"team": club_provider_id, "season": season_year}
    snapshot = _latest_snapshot_before(session, endpoint=endpoint, params=params, before=before)
    if snapshot is None:
        return None
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
    if endpoint == SQUADS_ENDPOINT:
        positions = _squad_positions(payload, club_provider_id)
    else:
        positions = _players_positions(payload, club_provider_id, season_year)
    fetched_at = snapshot.fetched_at
    # Il payload può essere grande (statistiche): non resta nella sessione.
    session.expunge(snapshot)
    return _ClubPositions(by_athlete=positions, fetched_at=fetched_at)


def _destinations_known_before(
    session: Session,
    athlete_ids: list[UUID],
    before: datetime,
) -> dict[UUID, UUID]:
    """Club di arrivo dell'ultimo trasferimento già noto al sistema prima di ``before``."""
    out: dict[UUID, UUID] = {}
    for chunk in _chunks(athlete_ids):
        rows = session.execute(
            select(Transfer.athlete_id, Transfer.to_club_id)
            .where(Transfer.athlete_id.in_(chunk), Transfer.created_at < before)
            .distinct(Transfer.athlete_id)
            .order_by(
                Transfer.athlete_id,
                Transfer.transfer_date.desc(),
                Transfer.created_at.desc(),
            )
        ).all()
        for athlete_id, to_club_id in rows:
            if to_club_id is not None:
                out[athlete_id] = to_club_id
    return out


def reconstruct_roles_before(
    session: Session,
    *,
    season_year: int,
    before: datetime,
    athlete_ids: Collection[UUID],
) -> dict[UUID, ReconstructedRole]:
    """Ruolo che il listone dava a ogni calciatore con le risposte salvate prima di ``before``.

    I club guardati sono quelli delle membership della stagione (attive o no) e quello
    dell'assegnazione attuale. Un calciatore che nessuna risposta salvata prima di
    ``before`` elenca, o con una posizione senza ruolo, non compare: non è ricostruibile.
    """
    ids = list(dict.fromkeys(athlete_ids))
    if not ids:
        return {}
    athlete_provider: dict[UUID, int] = {}
    clubs_of: dict[UUID, set[UUID]] = {athlete_id: set() for athlete_id in ids}
    for chunk in _chunks(ids):
        athlete_provider.update(
            session.execute(
                select(Athlete.id, Athlete.provider_id).where(Athlete.id.in_(chunk))
            ).all()
        )
        for athlete_id, club_id in session.execute(
            select(SquadMembership.athlete_id, SquadMembership.club_id)
            .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
            .where(SquadMembership.athlete_id.in_(chunk), SportSeason.year == season_year)
        ).all():
            clubs_of[athlete_id].add(club_id)
        for athlete_id, club_id in session.execute(
            select(RoleAssignment.athlete_id, RoleAssignment.club_id).where(
                RoleAssignment.athlete_id.in_(chunk),
                RoleAssignment.season_year == season_year,
                RoleAssignment.club_id.is_not(None),
            )
        ).all():
            clubs_of[athlete_id].add(club_id)

    all_clubs = sorted({club_id for clubs in clubs_of.values() for club_id in clubs}, key=str)
    club_provider: dict[UUID, int] = {}
    for chunk in _chunks(all_clubs):
        club_provider.update(
            session.execute(select(Club.id, Club.provider_id).where(Club.id.in_(chunk))).all()
        )

    squads: dict[UUID, _ClubPositions | None] = {
        club_id: _club_positions(
            session,
            endpoint=SQUADS_ENDPOINT,
            club_provider_id=provider_id,
            season_year=season_year,
            before=before,
        )
        for club_id, provider_id in club_provider.items()
    }
    # Le statistiche (/players) sono pesanti: si leggono solo per i club di chi non è in
    # nessuna rosa salvata.
    players_needed: set[UUID] = set()
    for athlete_id, clubs in clubs_of.items():
        provider_id = athlete_provider.get(athlete_id)
        listed = any(
            (snap := squads.get(club_id)) is not None and provider_id in snap.by_athlete
            for club_id in clubs
        )
        if not listed:
            players_needed.update(club_id for club_id in clubs if club_id in club_provider)
    players: dict[UUID, _ClubPositions | None] = {
        club_id: _club_positions(
            session,
            endpoint=PLAYERS_ENDPOINT,
            club_provider_id=club_provider[club_id],
            season_year=season_year,
            before=before,
        )
        for club_id in sorted(players_needed, key=str)
    }

    destinations = _destinations_known_before(session, ids, before)
    out: dict[UUID, ReconstructedRole] = {}
    for athlete_id in ids:
        provider_id = athlete_provider.get(athlete_id)
        if provider_id is None:
            continue
        best: tuple[tuple[bool, bool, bool], datetime] | None = None
        chosen: ReconstructedRole | None = None
        for club_id in clubs_of[athlete_id]:
            candidate: tuple[str, str, datetime] | None = None
            squad = squads.get(club_id)
            if squad is not None and provider_id in squad.by_athlete:
                candidate = ("squads", squad.by_athlete[provider_id], squad.fetched_at)
            else:
                stats = players.get(club_id)
                if stats is not None and provider_id in stats.by_athlete:
                    candidate = ("players", stats.by_athlete[provider_id], stats.fetched_at)
            if candidate is None:
                continue
            source, position, fetched_at = candidate
            role = map_provider_position_to_role(position)
            if role is None:
                continue
            rank = (
                membership_preference(
                    club_id=club_id,
                    source=source,
                    provider_position_raw=position,
                    current_club_id=destinations.get(athlete_id),
                ),
                fetched_at,
            )
            if best is None or rank > best:
                best = rank
                chosen = ReconstructedRole(
                    role=role,
                    provider_position_raw=position,
                    club_id=club_id,
                    source=source,
                    fetched_at=fetched_at,
                )
        if chosen is not None:
            out[athlete_id] = chosen
    return out
