"""Scarica le formazioni probabili delle partite vicine e le appende come snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from observability.logging import get_logger
from sports_data.fixtures.models import Fixture
from sports_data.predicted.client import FotmobClient, FotmobError
from sports_data.predicted.models import (
    FotmobFixtureLink,
    PredictedLineupPlayer,
    PredictedLineupSnapshot,
)
from sports_data.predicted.names import (
    SquadPlayer,
    clubs_match,
    match_squad_player,
    normalize_person,
)
from sports_data.predicted.oracle_client import SoccerOracleClient, SoccerOracleError
from sports_data.predicted.oracle_parse import (
    OracleFixtureLineup,
    OraclePlayer,
    OracleTeam,
    parse_lookup_response,
    parse_oracle_lineups_response,
)
from sports_data.predicted.parse import (
    ParsedLineup,
    ParsedMatchRef,
    ParsedPlayer,
    ParsedSide,
    parse_lineup_payload,
    parse_matches_by_date,
)
from sports_data.predicted.validate import (
    RELIABILITY_PARTIAL,
    RELIABILITY_REJECTED,
    RELIABILITY_UNVERIFIED,
    RELIABILITY_VALIDATED,
    blocks_selection,
    check_side,
    classify_reliability,
    grids_for_starters,
    side_starters,
    starter_key,
)
from sports_data.roster.models import Athlete, SquadMembership

logger = get_logger(__name__)
_ORACLE_LINEUPS_BATCH_SIZE = 50

UPCOMING_STATUSES = ("NS", "TBD", "PST", "SUSP")
_MISSING_KEY = "Chiave RapidAPI assente: le formazioni probabili non sono state aggiornate."


@dataclass
class PredictedSyncSummary:
    fixtures_considered: int = 0
    matches_linked: int = 0
    snapshots_saved: int = 0
    skipped_recent: int = 0
    skipped_unmatched: int = 0
    rejected: int = 0
    warnings: int = 0
    requests_made: int = 0
    message: str | None = None


def sync_predicted_lineups(
    session: Session,
    client: FotmobClient | None,
    *,
    now: datetime | None = None,
    horizon: timedelta = timedelta(days=4),
    max_lineup_calls: int = 40,
    force: bool = False,
    league_id: UUID | None = None,
    min_age: timedelta = timedelta(hours=20),
    oracle: SoccerOracleClient | None = None,
    oracle_min_confidence: float = 0.6,
    oracle_max_lookup_calls: int = 30,
) -> PredictedSyncSummary:
    """Aggiorna le partite non iniziate della finestra.

    Se ``oracle`` è configurato, le formazioni arrivano da Soccer-Oracle
    (ID esatti invece dell'abbinamento per nome). Se l'API non risponde o la
    chiave manca, si ricade sull'abbinamento FotMob per nome di sempre.
    Senza né client né oracle non si chiama nulla.
    """
    summary = PredictedSyncSummary()
    if client is None and oracle is None:
        summary.message = _MISSING_KEY
        return summary
    moment = now or datetime.now(UTC)
    fixtures = _candidate_fixtures(session, now=moment, horizon=horizon, league_id=league_id)
    summary.fixtures_considered = len(fixtures)
    pending: list[Fixture] = []
    for fixture in fixtures:
        if not force and _has_recent_snapshot(session, fixture.id, moment - min_age):
            summary.skipped_recent += 1
            continue
        pending.append(fixture)
    pending = pending[: max(0, max_lineup_calls)]

    remaining = pending
    if oracle is not None:
        try:
            _sync_via_oracle(
                session,
                oracle,
                pending,
                summary,
                moment,
                oracle_min_confidence,
                oracle_max_lookup_calls,
            )
            remaining = []
        except SoccerOracleError:
            logger.warning("soccer_oracle_sync_unavailable_falling_back_to_fotmob", exc_info=True)
            remaining = pending

    if remaining:
        if client is None:
            summary.message = _MISSING_KEY
        else:
            by_date: dict[str, tuple[ParsedMatchRef, ...] | None] = {}
            try:
                for fixture in remaining:
                    _sync_one(
                        session, client, fixture, by_date=by_date, summary=summary, now=moment
                    )
            except FotmobError as exc:
                if exc.status in {401, 403}:
                    summary.message = (
                        "Il provider ha rifiutato l'accesso alle formazioni probabili."
                    )
                    logger.warning("fotmob_auth_failed", extra={"status": exc.status})
                else:
                    summary.warnings += 1
                    summary.message = "Aggiornamento interrotto: il provider non ha risposto."
                    logger.warning("fotmob_sync_failed", extra={"status": exc.status})
            summary.requests_made = client.requests_made
    logger.info(
        "fotmob_predicted_lineups_synced",
        extra={
            "fixtures_considered": summary.fixtures_considered,
            "snapshots_saved": summary.snapshots_saved,
            "requests_made": summary.requests_made,
            "rejected": summary.rejected,
        },
    )
    return summary


class _LookupBudget:
    """Tetto alle chiamate extra ``/players/lookup`` per giro di sync — non
    vogliamo una lookup per ogni giocatore non abbinato, potrebbero essere
    centinaia tra tutte le leghe."""

    def __init__(self, remaining: int) -> None:
        self.remaining = remaining

    def take(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


def _sync_via_oracle(
    session: Session,
    oracle: SoccerOracleClient,
    fixtures: list[Fixture],
    summary: PredictedSyncSummary,
    now: datetime,
    min_confidence: float,
    max_lookup_calls: int,
) -> None:
    """Interamente o niente: se una chiamata fallisce, il chiamante ricade su FotMob."""
    if not fixtures:
        return
    by_provider_id = {fixture.provider_id: fixture for fixture in fixtures}
    provider_ids = list(by_provider_id)
    pending_links: list[dict[str, object]] = []
    lookup_budget = _LookupBudget(max_lookup_calls)
    for start in range(0, len(provider_ids), _ORACLE_LINEUPS_BATCH_SIZE):
        batch = provider_ids[start : start + _ORACLE_LINEUPS_BATCH_SIZE]
        payload = oracle.lineups(batch, prefer="predicted")
        parsed = parse_oracle_lineups_response(payload)
        for provider_id in batch:
            fixture = by_provider_id[provider_id]
            _store_oracle_snapshot(
                session,
                fixture,
                parsed.get(provider_id),
                summary,
                now,
                min_confidence,
                pending_links,
                oracle,
                lookup_budget,
            )
    if pending_links:
        try:
            oracle.links_bulk(pending_links)
        except SoccerOracleError:
            logger.warning("soccer_oracle_links_bulk_failed", exc_info=True)


def _candidate_fixtures(
    session: Session,
    *,
    now: datetime,
    horizon: timedelta,
    league_id: UUID | None,
) -> list[Fixture]:
    window_start = now - timedelta(hours=6)
    window_end = now + horizon
    stmt = (
        select(Fixture)
        .join(FantasyRoundFixture, FantasyRoundFixture.fixture_id == Fixture.id)
        .join(FantasyRound, FantasyRound.id == FantasyRoundFixture.round_id)
        .where(
            FantasyRoundFixture.excluded_at.is_(None),
            Fixture.status_short.in_(UPCOMING_STATUSES),
            or_(Fixture.kickoff_at.is_(None), Fixture.kickoff_at >= window_start),
            or_(Fixture.kickoff_at.is_(None), Fixture.kickoff_at <= window_end),
        )
        .options(
            selectinload(Fixture.home_club),
            selectinload(Fixture.away_club),
        )
        .distinct()
        .order_by(Fixture.kickoff_at.asc().nulls_last())
    )
    if league_id is not None:
        stmt = stmt.where(FantasyRound.league_id == league_id)
    return list(session.scalars(stmt).all())


def _has_recent_snapshot(session: Session, fixture_id: UUID, cutoff: datetime) -> bool:
    fetched_at = session.scalar(
        select(PredictedLineupSnapshot.fetched_at)
        .where(PredictedLineupSnapshot.fixture_id == fixture_id)
        .order_by(PredictedLineupSnapshot.fetched_at.desc())
        .limit(1)
    )
    return fetched_at is not None and fetched_at >= cutoff


def _sync_one(
    session: Session,
    client: FotmobClient,
    fixture: Fixture,
    *,
    by_date: dict[str, tuple[ParsedMatchRef, ...] | None],
    summary: PredictedSyncSummary,
    now: datetime,
) -> None:
    if fixture.kickoff_at is None:
        summary.skipped_unmatched += 1
        return
    link = session.scalar(
        select(FotmobFixtureLink).where(FotmobFixtureLink.fixture_id == fixture.id)
    )
    if link is None:
        link = _link_fixture(session, client, fixture, by_date, summary)
    if link is None:
        summary.skipped_unmatched += 1
        return
    try:
        payload = client.lineups(link.fotmob_match_id)
    except FotmobError as exc:
        if exc.status in {401, 403}:
            raise
        summary.warnings += 1
        logger.warning(
            "fotmob_lineup_failed",
            extra={"status": exc.status, "fixture_id": str(fixture.id)},
        )
        return
    parsed = parse_lineup_payload(payload)
    _store_snapshot(session, fixture, link.fotmob_match_id, parsed, summary, now)


def _link_fixture(
    session: Session,
    client: FotmobClient,
    fixture: Fixture,
    by_date: dict[str, tuple[ParsedMatchRef, ...] | None],
    summary: PredictedSyncSummary,
) -> FotmobFixtureLink | None:
    assert fixture.kickoff_at is not None
    day = fixture.kickoff_at.astimezone(UTC).strftime("%Y%m%d")
    if day not in by_date:
        try:
            by_date[day] = parse_matches_by_date(client.matches_by_date(day))
        except FotmobError as exc:
            if exc.status in {401, 403}:
                raise
            by_date[day] = None
            summary.warnings += 1
            logger.warning("fotmob_by_date_failed", extra={"status": exc.status, "date": day})
    matches = by_date.get(day) or ()
    hits = [
        match
        for match in matches
        if clubs_match(fixture.home_club.name, match.home_name)
        and clubs_match(fixture.away_club.name, match.away_name)
    ]
    if len(hits) != 1:
        return None
    hit = hits[0]
    taken = session.scalar(
        select(FotmobFixtureLink).where(FotmobFixtureLink.fotmob_match_id == hit.fotmob_match_id)
    )
    if taken is not None:
        return taken if taken.fixture_id == fixture.id else None
    link = FotmobFixtureLink(
        fixture_id=fixture.id,
        fotmob_match_id=hit.fotmob_match_id,
        home_name=hit.home_name[:160],
        away_name=hit.away_name[:160],
    )
    session.add(link)
    session.flush()
    summary.matches_linked += 1
    return link


def _store_snapshot(
    session: Session,
    fixture: Fixture,
    fotmob_match_id: int,
    parsed: ParsedLineup,
    summary: PredictedSyncSummary,
    now: datetime,
) -> None:
    extra: list[str] = list(parsed.warnings)
    aligned = _align(fixture.home_club.name, fixture.away_club.name, parsed)
    if aligned is None:
        extra.append("match_mismatch")
        home, away = parsed.home, parsed.away
    else:
        home, away, swapped = aligned
        if swapped:
            extra.append("sides_swapped")

    home_squad = _squad(session, fixture.home_club_id, fixture.sport_season_id)
    away_squad = _squad(session, fixture.away_club_id, fixture.sport_season_id)
    home_mapped = _mapped_starter_keys(home, home_squad)
    away_mapped = _mapped_starter_keys(away, away_squad)
    player_count = (0 if home is None else len(home.players)) + (
        0 if away is None else len(away.players)
    )
    if "match_mismatch" in extra:
        reliability_code = RELIABILITY_REJECTED
        warnings = tuple(dict.fromkeys(extra))
    else:
        reliability = classify_reliability(
            check_side(home, mapped_starter_keys=home_mapped),
            check_side(away, mapped_starter_keys=away_mapped),
            player_count=player_count,
            extra_warnings=tuple(extra),
        )
        reliability_code = reliability.code
        warnings = reliability.warnings

    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture.id,
        fotmob_match_id=fotmob_match_id,
        lineup_type=parsed.lineup_type,
        source=(parsed.source or None),
        reliability=reliability_code,
        warning_codes=list(warnings),
        home_formation=None if home is None else home.formation,
        away_formation=None if away is None else away.formation,
        home_coach=None if home is None else home.coach_name,
        away_coach=None if away is None else away.coach_name,
        fetched_at=now,
    )
    session.add(snapshot)
    session.flush()
    _add_players(
        session,
        snapshot,
        side="home",
        parsed=home,
        squad=home_squad,
        club_id=fixture.home_club_id,
        kickoff_at=fixture.kickoff_at,
    )
    _add_players(
        session,
        snapshot,
        side="away",
        parsed=away,
        squad=away_squad,
        club_id=fixture.away_club_id,
        kickoff_at=fixture.kickoff_at,
    )
    summary.snapshots_saved += 1
    summary.warnings += len(warnings)
    if reliability_code == RELIABILITY_REJECTED:
        summary.rejected += 1


def _align(
    home_name: str,
    away_name: str,
    parsed: ParsedLineup,
) -> tuple[ParsedSide | None, ParsedSide | None, bool] | None:
    home = parsed.home
    away = parsed.away
    if home is None or away is None or not home.name or not away.name:
        return None
    if clubs_match(home_name, home.name) and clubs_match(away_name, away.name):
        return home, away, False
    if clubs_match(home_name, away.name) and clubs_match(away_name, home.name):
        return away, home, True
    return None


def _squad(session: Session, club_id: UUID, season_id: UUID) -> list[SquadPlayer]:
    rows = session.scalars(
        select(SquadMembership)
        .where(
            SquadMembership.club_id == club_id,
            SquadMembership.sport_season_id == season_id,
            SquadMembership.is_active.is_(True),
        )
        .options(selectinload(SquadMembership.athlete))
    ).all()
    return [
        SquadPlayer(
            athlete_id=row.athlete_id,
            canonical_name=row.athlete.canonical_name,
            first_name=row.athlete.first_name,
            last_name=row.athlete.last_name,
        )
        for row in rows
        if row.athlete is not None
    ]


def _mapped_starter_keys(side: ParsedSide | None, squad: list[SquadPlayer]) -> set[str]:
    keys: set[str] = set()
    for player in side_starters(side):
        if match_squad_player(player.name, squad) is not None:
            keys.add(starter_key(player))
    return keys


def _add_players(
    session: Session,
    snapshot: PredictedLineupSnapshot,
    *,
    side: str,
    parsed: ParsedSide | None,
    squad: list[SquadPlayer],
    club_id: UUID,
    kickoff_at: datetime | None,
) -> None:
    if parsed is None:
        return
    starters = side_starters(parsed)
    starter_keys = {starter_key(player) for player in starters}
    grids = grids_for_starters(starters)
    unavailable_keys: set[str] = set()
    order = 0
    for player in starters:
        order += 1
        _add_player(
            session,
            snapshot,
            player,
            side=side,
            squad=squad,
            club_id=club_id,
            kickoff_at=kickoff_at,
            is_starter=True,
            is_unavailable=False,
            grid=grids.get(starter_key(player)),
            sort_order=order,
        )
    for player in parsed.players:
        if player.is_starter or player.is_unavailable:
            continue
        if starter_key(player) in starter_keys:
            continue
        order += 1
        _add_player(
            session,
            snapshot,
            player,
            side=side,
            squad=squad,
            club_id=club_id,
            kickoff_at=kickoff_at,
            is_starter=False,
            is_unavailable=False,
            grid=None,
            sort_order=order,
        )
    for player in parsed.players:
        if not player.is_unavailable:
            continue
        key = starter_key(player)
        if key in unavailable_keys:
            continue
        unavailable_keys.add(key)
        order += 1
        _add_player(
            session,
            snapshot,
            player,
            side=side,
            squad=squad,
            club_id=club_id,
            kickoff_at=kickoff_at,
            is_starter=False,
            is_unavailable=True,
            grid=None,
            sort_order=order,
        )


def _add_player(
    session: Session,
    snapshot: PredictedLineupSnapshot,
    player: ParsedPlayer,
    *,
    side: str,
    squad: list[SquadPlayer],
    club_id: UUID,
    kickoff_at: datetime | None,
    is_starter: bool,
    is_unavailable: bool,
    grid: str | None,
    sort_order: int,
) -> None:
    athlete_id = match_squad_player(player.name, squad)
    expected = player.expected_return_at
    kickoff = kickoff_at
    if (
        expected is not None
        and kickoff is not None
        and (expected.tzinfo is None or kickoff.tzinfo is None)
    ):
        expected = None
    session.add(
        PredictedLineupPlayer(
            snapshot_id=snapshot.id,
            club_id=club_id,
            athlete_id=athlete_id,
            side=side,
            display_name=player.name[:160],
            shirt_number=player.shirt_number,
            fotmob_player_id=player.fotmob_id,
            is_starter=is_starter,
            is_unavailable=is_unavailable,
            unavailability_type=None if not is_unavailable else player.unavailability_type,
            unavailability_label=(
                None
                if not is_unavailable or player.unavailability_label is None
                else player.unavailability_label[:160]
            ),
            blocks_selection=blocks_selection(
                mapped=athlete_id is not None,
                unavailability_type=player.unavailability_type,
                uncertain=player.uncertain,
                expected_return_at=expected,
                kickoff_at=kickoff,
            )
            if is_unavailable
            else False,
            grid=grid,
            sort_order=sort_order,
        )
    )


@dataclass(frozen=True)
class _OracleSquadMember:
    """Rosa interna con maglia e data di nascita, per il riscontro dei giocatori
    che Soccer-Oracle segnala come ``mapped=false``."""

    athlete_id: UUID
    provider_id: int
    last_name: str
    shirt_number: int | None
    birth_date: date | None


def _oracle_squad(session: Session, club_id: UUID, season_id: UUID) -> list[_OracleSquadMember]:
    rows = session.scalars(
        select(SquadMembership)
        .where(
            SquadMembership.club_id == club_id,
            SquadMembership.sport_season_id == season_id,
            SquadMembership.is_active.is_(True),
        )
        .options(selectinload(SquadMembership.athlete))
    ).all()
    return [
        _OracleSquadMember(
            athlete_id=row.athlete_id,
            provider_id=row.athlete.provider_id,
            last_name=_oracle_last_name(row.athlete),
            shirt_number=row.shirt_number,
            birth_date=row.athlete.birth_date,
        )
        for row in rows
        if row.athlete is not None
    ]


def _oracle_last_name(athlete: Athlete) -> str:
    explicit = normalize_person(athlete.last_name)
    if explicit:
        return explicit
    parts = normalize_person(athlete.canonical_name).split()
    return parts[-1] if parts else ""


def _confident_shirt_match(
    name: str,
    shirt_number: int | None,
    squad: list[_OracleSquadMember],
) -> _OracleSquadMember | None:
    """Maglia + cognome, univoco: l'unico indizio forte che possiamo mandare
    indietro a Soccer-Oracle per un giocatore che loro segnano come non abbinato."""
    if shirt_number is None:
        return None
    tokens = normalize_person(name).split()
    if not tokens:
        return None
    target_last = tokens[-1]
    candidates = [
        member
        for member in squad
        if member.shirt_number == shirt_number and member.last_name == target_last
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _team_for_club(teams: tuple[OracleTeam, ...], club_provider_id: int) -> OracleTeam | None:
    for team in teams:
        if team.team_api_id == club_provider_id:
            return team
    return None


def _count_oracle_mapped(team: OracleTeam | None, min_confidence: float) -> tuple[int, int]:
    if team is None:
        return 0, 0
    total = len(team.starters)
    mapped = sum(
        1 for player in team.starters if player.mapped and player.confidence >= min_confidence
    )
    return mapped, total


def _store_oracle_snapshot(
    session: Session,
    fixture: Fixture,
    lineup: OracleFixtureLineup | None,
    summary: PredictedSyncSummary,
    now: datetime,
    min_confidence: float,
    pending_links: list[dict[str, object]],
    oracle: SoccerOracleClient,
    lookup_budget: _LookupBudget,
) -> None:
    if lineup is None or lineup.lineup_type is None or not lineup.teams:
        return
    home_team = _team_for_club(lineup.teams, fixture.home_club.provider_id)
    away_team = _team_for_club(lineup.teams, fixture.away_club.provider_id)
    if home_team is None and away_team is None:
        return

    home_mapped, home_total = _count_oracle_mapped(home_team, min_confidence)
    away_mapped, away_total = _count_oracle_mapped(away_team, min_confidence)
    total_starters = home_total + away_total
    total_mapped = home_mapped + away_mapped
    warnings: list[str] = []
    if lineup.unmapped_starters:
        warnings.append(f"oracle_unmapped_starters:{lineup.unmapped_starters}")
    if total_starters == 0:
        reliability_code = RELIABILITY_REJECTED
    elif total_mapped == total_starters:
        reliability_code = RELIABILITY_VALIDATED
    elif total_mapped > 0:
        reliability_code = RELIABILITY_PARTIAL
    else:
        reliability_code = RELIABILITY_UNVERIFIED

    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture.id,
        fotmob_match_id=None,
        lineup_type="confirmed" if lineup.lineup_type == "official" else "predicted",
        source=f"soccer_oracle:{lineup.source or 'unknown'}",
        reliability=reliability_code,
        warning_codes=warnings,
        home_formation=None if home_team is None else home_team.formation,
        away_formation=None if away_team is None else away_team.formation,
        home_coach=None,
        away_coach=None,
        fetched_at=now,
    )
    session.add(snapshot)
    session.flush()

    home_squad = _oracle_squad(session, fixture.home_club_id, fixture.sport_season_id)
    away_squad = _oracle_squad(session, fixture.away_club_id, fixture.sport_season_id)
    _add_oracle_team(
        session,
        snapshot,
        home_team,
        side="home",
        club_id=fixture.home_club_id,
        squad=home_squad,
        kickoff_at=fixture.kickoff_at,
        min_confidence=min_confidence,
        pending_links=pending_links,
        oracle=oracle,
        lookup_budget=lookup_budget,
    )
    _add_oracle_team(
        session,
        snapshot,
        away_team,
        side="away",
        club_id=fixture.away_club_id,
        squad=away_squad,
        kickoff_at=fixture.kickoff_at,
        min_confidence=min_confidence,
        pending_links=pending_links,
        oracle=oracle,
        lookup_budget=lookup_budget,
    )
    summary.snapshots_saved += 1
    summary.warnings += len(warnings)
    if reliability_code == RELIABILITY_REJECTED:
        summary.rejected += 1


def _add_oracle_team(
    session: Session,
    snapshot: PredictedLineupSnapshot,
    team: OracleTeam | None,
    *,
    side: str,
    club_id: UUID,
    squad: list[_OracleSquadMember],
    kickoff_at: datetime | None,
    min_confidence: float,
    pending_links: list[dict[str, object]],
    oracle: SoccerOracleClient,
    lookup_budget: _LookupBudget,
) -> None:
    if team is None:
        return
    order = 0
    for is_starter, is_unavailable, players in (
        (True, False, team.starters),
        (False, False, team.bench),
        (False, True, team.unavailable),
    ):
        for player in players:
            order += 1
            _add_oracle_player(
                session,
                snapshot,
                player,
                side=side,
                club_id=club_id,
                squad=squad,
                kickoff_at=kickoff_at,
                is_starter=is_starter,
                is_unavailable=is_unavailable,
                min_confidence=min_confidence,
                sort_order=order,
                pending_links=pending_links,
                oracle=oracle,
                lookup_budget=lookup_budget,
            )


def _resolve_via_oracle_lookup(
    session: Session, oracle: SoccerOracleClient, fotmob_id: int
) -> UUID | None:
    """Ultimo tentativo per ID esatto, quando né Soccer-Oracle né il nostro
    riscontro interno hanno abbinato il giocatore. Niente ambiguità di nome:
    o lo trova per ID o niente."""
    try:
        payload = oracle.lookup(provider="fotmob", provider_id=fotmob_id)
    except SoccerOracleError:
        logger.warning("soccer_oracle_lookup_failed", exc_info=True)
        return None
    result = parse_lookup_response(payload)
    if result.status != "found" or result.api_sports_id is None:
        return None
    athlete = session.scalar(select(Athlete).where(Athlete.provider_id == result.api_sports_id))
    return None if athlete is None else athlete.id


def _add_oracle_player(
    session: Session,
    snapshot: PredictedLineupSnapshot,
    player: OraclePlayer,
    *,
    side: str,
    club_id: UUID,
    squad: list[_OracleSquadMember],
    kickoff_at: datetime | None,
    is_starter: bool,
    is_unavailable: bool,
    min_confidence: float,
    sort_order: int,
    pending_links: list[dict[str, object]],
    oracle: SoccerOracleClient,
    lookup_budget: _LookupBudget,
) -> None:
    athlete_id: UUID | None = None
    if player.mapped and player.confidence >= min_confidence and player.api_sports_id is not None:
        athlete = session.scalar(select(Athlete).where(Athlete.provider_id == player.api_sports_id))
        if athlete is not None:
            athlete_id = athlete.id
    if athlete_id is None:
        own_match = _confident_shirt_match(player.name, player.shirt_number, squad)
        if own_match is not None:
            athlete_id = own_match.athlete_id
            if player.fotmob_id is not None:
                pending_links.append(
                    {
                        "api_sports_id": own_match.provider_id,
                        "fotmob_id": player.fotmob_id,
                        "name": player.name,
                        "birth_date": (
                            own_match.birth_date.isoformat()
                            if own_match.birth_date is not None
                            else None
                        ),
                    }
                )
        elif player.fotmob_id is not None and lookup_budget.take():
            athlete_id = _resolve_via_oracle_lookup(session, oracle, player.fotmob_id)

    expected = player.absence_expected_return_at
    kickoff = kickoff_at
    if (
        expected is not None
        and kickoff is not None
        and (expected.tzinfo is None or kickoff.tzinfo is None)
    ):
        expected = None
    session.add(
        PredictedLineupPlayer(
            snapshot_id=snapshot.id,
            club_id=club_id,
            athlete_id=athlete_id,
            side=side,
            display_name=player.name[:160],
            shirt_number=player.shirt_number,
            fotmob_player_id=player.fotmob_id,
            is_starter=is_starter,
            is_unavailable=is_unavailable,
            unavailability_type=None if not is_unavailable else player.absence_type,
            unavailability_label=(
                None
                if not is_unavailable or player.absence_label is None
                else player.absence_label[:160]
            ),
            blocks_selection=blocks_selection(
                mapped=athlete_id is not None,
                unavailability_type=player.absence_type,
                uncertain=player.absence_uncertain,
                expected_return_at=expected,
                kickoff_at=kickoff,
            )
            if is_unavailable
            else False,
            grid=None,
            sort_order=sort_order,
        )
    )
