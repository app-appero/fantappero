"""Map API-Football envelope rows to internal ACL DTOs (EP04-01+).

Persistence of catalog entities lives in ``sports_data.catalog`` (EP04-02).
Fixture persistence lives in ``sports_data.fixtures`` (EP04-05).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sports_data.normalization.keys import event_provider_key
from sports_data.provider.hashing import payload_sha256
from sports_data.provider.types import (
    MappedAthlete,
    MappedClub,
    MappedCompetition,
    MappedFixture,
    MappedLineupEntry,
    MappedMatchEvent,
    MappedOfficialLineup,
    MappedPlayerMatchStat,
    MappedSeason,
    MappedSquadMembership,
    MappedTransfer,
    ProviderEnvelope,
)


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_kickoff(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _coverage_flags(season: dict[str, Any]) -> dict[str, bool | None]:
    coverage = season.get("coverage") if isinstance(season.get("coverage"), dict) else {}
    fixtures_cov = coverage.get("fixtures") if isinstance(coverage.get("fixtures"), dict) else {}
    return {
        "coverage_events": bool(fixtures_cov["events"]) if "events" in fixtures_cov else None,
        "coverage_lineups": bool(fixtures_cov["lineups"]) if "lineups" in fixtures_cov else None,
        "coverage_statistics_players": (
            bool(fixtures_cov["statistics_players"])
            if "statistics_players" in fixtures_cov
            else None
        ),
        "coverage_injuries": bool(coverage["injuries"]) if "injuries" in coverage else None,
        "coverage_predictions": (
            bool(coverage["predictions"]) if "predictions" in coverage else None
        ),
        "coverage_standings": bool(coverage["standings"]) if "standings" in coverage else None,
    }


def _choose_season(seasons: list[Any]) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for season in seasons:
        if isinstance(season, dict) and season.get("current") is True:
            return season
    if seasons and isinstance(seasons[-1], dict):
        chosen = seasons[-1]
    return chosen


def map_competitions(envelope: ProviderEnvelope) -> list[MappedCompetition]:
    """Map ``/leagues`` response rows (current/latest season summary on each)."""
    out: list[MappedCompetition] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        league = row.get("league") or {}
        country = row.get("country") or {}
        provider_id = _as_optional_int(league.get("id"))
        name = league.get("name")
        if provider_id is None or not isinstance(name, str) or not name.strip():
            continue
        country_name = country.get("name") if isinstance(country, dict) else None
        if not isinstance(country_name, str):
            country_name = ""

        seasons = row.get("seasons") if isinstance(row.get("seasons"), list) else []
        season_year: int | None = None
        season_current: bool | None = None
        coverage_events: bool | None = None
        coverage_lineups: bool | None = None
        coverage_statistics_players: bool | None = None
        chosen = _choose_season(seasons)
        if chosen is not None:
            season_year = _as_optional_int(chosen.get("year"))
            season_current = bool(chosen.get("current")) if "current" in chosen else None
            flags = _coverage_flags(chosen)
            coverage_events = flags["coverage_events"]
            coverage_lineups = flags["coverage_lineups"]
            coverage_statistics_players = flags["coverage_statistics_players"]

        out.append(
            MappedCompetition(
                provider_id=provider_id,
                name=name.strip(),
                country=country_name.strip(),
                season_year=season_year,
                season_current=season_current,
                coverage_events=coverage_events,
                coverage_lineups=coverage_lineups,
                coverage_statistics_players=coverage_statistics_players,
            )
        )
    return out


def map_seasons(envelope: ProviderEnvelope) -> list[MappedSeason]:
    """Map every ``seasons[]`` entry under ``/leagues`` rows."""
    out: list[MappedSeason] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        league = row.get("league") if isinstance(row.get("league"), dict) else {}
        competition_id = _as_optional_int(league.get("id"))
        if competition_id is None:
            continue
        seasons = row.get("seasons") if isinstance(row.get("seasons"), list) else []
        for season in seasons:
            if not isinstance(season, dict):
                continue
            year = _as_optional_int(season.get("year"))
            if year is None:
                continue
            flags = _coverage_flags(season)
            out.append(
                MappedSeason(
                    competition_provider_id=competition_id,
                    year=year,
                    is_current=bool(season.get("current")),
                    start_date=_parse_date(season.get("start")),
                    end_date=_parse_date(season.get("end")),
                    coverage_events=flags["coverage_events"],
                    coverage_lineups=flags["coverage_lineups"],
                    coverage_statistics_players=flags["coverage_statistics_players"],
                    coverage_injuries=flags["coverage_injuries"],
                    coverage_predictions=flags["coverage_predictions"],
                    coverage_standings=flags["coverage_standings"],
                )
            )
    return out


def map_clubs(envelope: ProviderEnvelope) -> list[MappedClub]:
    """Map ``/teams`` response rows (includes national teams; filter at sync)."""
    out: list[MappedClub] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        team = row.get("team") or {}
        if not isinstance(team, dict):
            continue
        provider_id = _as_optional_int(team.get("id"))
        name = team.get("name")
        if provider_id is None or not isinstance(name, str) or not name.strip():
            continue
        code = team.get("code")
        country = team.get("country")
        out.append(
            MappedClub(
                provider_id=provider_id,
                name=name.strip(),
                code=code.strip() if isinstance(code, str) and code.strip() else None,
                country=country.strip() if isinstance(country, str) and country.strip() else None,
                national=bool(team.get("national")),
            )
        )
    return out


def map_fixtures(envelope: ProviderEnvelope) -> list[MappedFixture]:
    """Map ``/fixtures`` response rows."""
    out: list[MappedFixture] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        fixture = row.get("fixture") if isinstance(row.get("fixture"), dict) else {}
        league = row.get("league") if isinstance(row.get("league"), dict) else {}
        teams = row.get("teams") if isinstance(row.get("teams"), dict) else {}
        home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
        away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
        goals = row.get("goals") if isinstance(row.get("goals"), dict) else {}
        status = fixture.get("status") if isinstance(fixture.get("status"), dict) else {}

        provider_id = _as_optional_int(fixture.get("id"))
        competition_id = _as_optional_int(league.get("id"))
        season_year = _as_optional_int(league.get("season"))
        home_id = _as_optional_int(home.get("id"))
        away_id = _as_optional_int(away.get("id"))
        status_short = status.get("short")
        if (
            provider_id is None
            or competition_id is None
            or season_year is None
            or home_id is None
            or away_id is None
            or not isinstance(status_short, str)
            or not status_short
        ):
            continue

        round_label = league.get("round")
        home_name = home.get("name")
        away_name = away.get("name")
        out.append(
            MappedFixture(
                provider_id=provider_id,
                competition_provider_id=competition_id,
                season_year=season_year,
                home_club_provider_id=home_id,
                away_club_provider_id=away_id,
                kickoff_at=_parse_kickoff(fixture.get("date")),
                status_short=status_short,
                home_goals=_as_optional_int(goals.get("home")),
                away_goals=_as_optional_int(goals.get("away")),
                status_elapsed=_as_optional_int(status.get("elapsed")),
                round_label=(
                    round_label.strip()
                    if isinstance(round_label, str) and round_label.strip()
                    else None
                ),
                home_club_name=(
                    home_name.strip() if isinstance(home_name, str) and home_name.strip() else None
                ),
                away_club_name=(
                    away_name.strip() if isinstance(away_name, str) and away_name.strip() else None
                ),
            )
        )
    return out


def map_match_events(
    envelope: ProviderEnvelope,
    *,
    fixture_provider_id: int | None = None,
) -> list[MappedMatchEvent]:
    """Map ``/fixtures/events`` response rows to timeline DTOs."""
    out: list[MappedMatchEvent] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        type_ = row.get("type")
        if not isinstance(type_, str) or not type_.strip():
            continue
        detail = row.get("detail")
        detail_str = detail.strip() if isinstance(detail, str) and detail.strip() else None
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        assist = row.get("assist") if isinstance(row.get("assist"), dict) else {}
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        time_ = row.get("time") if isinstance(row.get("time"), dict) else {}
        player_id = _as_optional_int(player.get("id"))
        assist_id = _as_optional_int(assist.get("id"))
        team_id = _as_optional_int(team.get("id"))
        elapsed = _as_optional_int(time_.get("elapsed"))
        extra = _as_optional_int(time_.get("extra"))
        comments = row.get("comments")
        comments_str = comments.strip() if isinstance(comments, str) and comments.strip() else None
        fid = fixture_provider_id
        if fid is None:
            param = envelope.parameters.get("fixture")
            fid = _as_optional_int(param)
        if fid is None:
            continue
        out.append(
            MappedMatchEvent(
                provider_event_key=event_provider_key(
                    fixture_id=fid,
                    elapsed=elapsed,
                    extra=extra,
                    type_=type_.strip(),
                    detail=detail_str,
                    player_id=player_id,
                    assist_id=assist_id,
                    role="primary",
                ),
                fixture_provider_id=fid,
                event_type=type_.strip(),
                event_detail=detail_str,
                athlete_provider_id=player_id,
                related_athlete_provider_id=assist_id,
                club_provider_id=team_id,
                minute_elapsed=elapsed,
                minute_extra=extra,
                comments=comments_str,
            )
        )
    return out


def map_official_lineups(
    envelope: ProviderEnvelope,
    *,
    fixture_provider_id: int | None = None,
) -> list[MappedOfficialLineup]:
    """Map ``/fixtures/lineups`` response rows."""
    out: list[MappedOfficialLineup] = []
    fid = fixture_provider_id
    if fid is None:
        fid = _as_optional_int(envelope.parameters.get("fixture"))
    if fid is None:
        return out

    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        club_id = _as_optional_int(team.get("id"))
        if club_id is None:
            continue
        formation = row.get("formation")
        formation_str = (
            formation.strip() if isinstance(formation, str) and formation.strip() else None
        )
        entries: list[MappedLineupEntry] = []
        start_xi = row.get("startXI") if isinstance(row.get("startXI"), list) else []
        for idx, item in enumerate(start_xi):
            entry = _lineup_player_entry(item, is_starter=True, sort_order=idx)
            if entry is not None:
                entries.append(entry)
        substitutes = row.get("substitutes") if isinstance(row.get("substitutes"), list) else []
        for idx, item in enumerate(substitutes):
            entry = _lineup_player_entry(item, is_starter=False, sort_order=idx)
            if entry is not None:
                entries.append(entry)
        out.append(
            MappedOfficialLineup(
                fixture_provider_id=fid,
                club_provider_id=club_id,
                formation=formation_str,
                entries=tuple(entries),
            )
        )
    return out


def _lineup_player_entry(
    item: Any,
    *,
    is_starter: bool,
    sort_order: int,
) -> MappedLineupEntry | None:
    if not isinstance(item, dict):
        return None
    player = item.get("player") if isinstance(item.get("player"), dict) else {}
    athlete_id = _as_optional_int(player.get("id"))
    name = player.get("name")
    if athlete_id is None or not isinstance(name, str) or not name.strip():
        return None
    pos = player.get("pos")
    grid = player.get("grid")
    return MappedLineupEntry(
        athlete_provider_id=athlete_id,
        athlete_name=name.strip(),
        is_starter=is_starter,
        shirt_number=_as_optional_int(player.get("number")),
        position_raw=pos.strip() if isinstance(pos, str) and pos.strip() else None,
        grid=grid.strip() if isinstance(grid, str) and grid.strip() else None,
        sort_order=sort_order,
    )


def map_player_match_stats(
    envelope: ProviderEnvelope,
    *,
    fixture_provider_id: int | None = None,
) -> list[MappedPlayerMatchStat]:
    """Map ``/fixtures/players`` nested team/player blocks."""
    out: list[MappedPlayerMatchStat] = []
    fid = fixture_provider_id
    if fid is None:
        fid = _as_optional_int(envelope.parameters.get("fixture"))
    if fid is None:
        return out

    for team_block in envelope.response:
        if not isinstance(team_block, dict):
            continue
        team = team_block.get("team") if isinstance(team_block.get("team"), dict) else {}
        club_id = _as_optional_int(team.get("id"))
        players = team_block.get("players") if isinstance(team_block.get("players"), list) else []
        for item in players:
            if not isinstance(item, dict):
                continue
            player = item.get("player") if isinstance(item.get("player"), dict) else {}
            athlete_id = _as_optional_int(player.get("id"))
            name = player.get("name")
            if athlete_id is None or not isinstance(name, str) or not name.strip():
                continue
            stats_list = item.get("statistics") if isinstance(item.get("statistics"), list) else []
            stats = stats_list[0] if stats_list and isinstance(stats_list[0], dict) else {}
            games = stats.get("games") if isinstance(stats.get("games"), dict) else {}
            position = games.get("position")
            rating = games.get("rating")
            substitute = games.get("substitute")
            out.append(
                MappedPlayerMatchStat(
                    fixture_provider_id=fid,
                    athlete_provider_id=athlete_id,
                    athlete_name=name.strip(),
                    club_provider_id=club_id,
                    minutes=_as_optional_int(games.get("minutes")),
                    position_raw=(
                        position.strip() if isinstance(position, str) and position.strip() else None
                    ),
                    is_substitute=bool(substitute) if isinstance(substitute, bool) else None,
                    provider_rating=(
                        str(rating).strip() if rating is not None and str(rating).strip() else None
                    ),
                    stats=dict(stats),
                    stats_hash=payload_sha256(stats),
                )
            )
    return out


def _canonical_player_name(player: dict[str, Any]) -> str | None:
    name = player.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    first = player.get("firstname")
    last = player.get("lastname")
    if isinstance(first, str) and isinstance(last, str):
        combined = f"{first.strip()} {last.strip()}".strip()
        if combined:
            return combined
    return None


def _athlete_from_player_dict(player: dict[str, Any]) -> MappedAthlete | None:
    provider_id = _as_optional_int(player.get("id"))
    canonical_name = _canonical_player_name(player)
    if provider_id is None or canonical_name is None:
        return None
    birth = player.get("birth") if isinstance(player.get("birth"), dict) else {}
    injured = player.get("injured")
    return MappedAthlete(
        provider_id=provider_id,
        canonical_name=canonical_name,
        first_name=player.get("firstname") if isinstance(player.get("firstname"), str) else None,
        last_name=player.get("lastname") if isinstance(player.get("lastname"), str) else None,
        nationality=(
            player.get("nationality") if isinstance(player.get("nationality"), str) else None
        ),
        birth_date=_parse_date(birth.get("date") if isinstance(birth, dict) else None),
        height=player.get("height") if isinstance(player.get("height"), str) else None,
        weight=player.get("weight") if isinstance(player.get("weight"), str) else None,
        age=_as_optional_int(player.get("age")),
        injured=bool(injured) if isinstance(injured, bool) else None,
    )


def map_athletes_from_players(
    envelope: ProviderEnvelope,
    *,
    league_ids: frozenset[int] | None = None,
) -> list[MappedAthlete]:
    """Map ``/players`` response rows (player profile + season statistics)."""
    allowed = league_ids
    out: list[MappedAthlete] = []
    seen: set[int] = set()
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        mapped = _athlete_from_player_dict(player)
        if mapped is None or mapped.provider_id in seen:
            continue
        if allowed is not None:
            stats = row.get("statistics") if isinstance(row.get("statistics"), list) else []
            in_scope = False
            for stat in stats:
                if not isinstance(stat, dict):
                    continue
                league = stat.get("league") if isinstance(stat.get("league"), dict) else {}
                league_id = _as_optional_int(league.get("id"))
                if league_id is not None and league_id in allowed:
                    in_scope = True
                    break
            if not in_scope:
                continue
        seen.add(mapped.provider_id)
        out.append(mapped)
    return out


def map_squad_memberships(
    envelope: ProviderEnvelope,
    *,
    competition_provider_id: int,
    season_year: int,
    source: str = "squads",
) -> list[MappedSquadMembership]:
    """Map ``/players/squads`` response (current squad for one team)."""
    out: list[MappedSquadMembership] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        club_provider_id = _as_optional_int(team.get("id"))
        if club_provider_id is None:
            continue
        players = row.get("players") if isinstance(row.get("players"), list) else []
        for player in players:
            if not isinstance(player, dict):
                continue
            athlete_provider_id = _as_optional_int(player.get("id"))
            name = player.get("name")
            if athlete_provider_id is None or not isinstance(name, str) or not name.strip():
                continue
            position = player.get("position")
            out.append(
                MappedSquadMembership(
                    athlete_provider_id=athlete_provider_id,
                    athlete_name=name.strip(),
                    club_provider_id=club_provider_id,
                    competition_provider_id=competition_provider_id,
                    season_year=season_year,
                    shirt_number=_as_optional_int(player.get("number")),
                    provider_position_raw=(
                        position.strip() if isinstance(position, str) and position.strip() else None
                    ),
                    athlete_age=_as_optional_int(player.get("age")),
                    source=source,
                )
            )
    return out


def map_squad_memberships_from_players(
    envelope: ProviderEnvelope,
    *,
    league_ids: frozenset[int] | None = None,
) -> list[MappedSquadMembership]:
    """Derive squad memberships from ``/players?team&season`` statistics blocks."""
    allowed = league_ids
    out: list[MappedSquadMembership] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        athlete_provider_id = _as_optional_int(player.get("id"))
        name = _canonical_player_name(player)
        if athlete_provider_id is None or name is None:
            continue
        stats = row.get("statistics") if isinstance(row.get("statistics"), list) else []
        for stat in stats:
            if not isinstance(stat, dict):
                continue
            league = stat.get("league") if isinstance(stat.get("league"), dict) else {}
            team = stat.get("team") if isinstance(stat.get("team"), dict) else {}
            games = stat.get("games") if isinstance(stat.get("games"), dict) else {}
            competition_id = _as_optional_int(league.get("id"))
            season_year = _as_optional_int(league.get("season"))
            club_provider_id = _as_optional_int(team.get("id"))
            if competition_id is None or season_year is None or club_provider_id is None:
                continue
            if allowed is not None and competition_id not in allowed:
                continue
            position = games.get("position")
            out.append(
                MappedSquadMembership(
                    athlete_provider_id=athlete_provider_id,
                    athlete_name=name,
                    club_provider_id=club_provider_id,
                    competition_provider_id=competition_id,
                    season_year=season_year,
                    provider_position_raw=(
                        position.strip() if isinstance(position, str) and position.strip() else None
                    ),
                    athlete_age=_as_optional_int(player.get("age")),
                    source="players",
                )
            )
    return out


def map_transfers(envelope: ProviderEnvelope) -> list[MappedTransfer]:
    """Map ``/transfers`` response rows (player block with nested transfers[])."""
    from sports_data.roster.validators import build_transfer_provider_key

    out: list[MappedTransfer] = []
    for row in envelope.response:
        if not isinstance(row, dict):
            continue
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        athlete_provider_id = _as_optional_int(player.get("id"))
        athlete_name = _canonical_player_name(player) or ""
        if athlete_provider_id is None:
            continue
        transfers = row.get("transfers") if isinstance(row.get("transfers"), list) else []
        for entry in transfers:
            if not isinstance(entry, dict):
                continue
            transfer_date = _parse_date(entry.get("date"))
            if transfer_date is None:
                continue
            teams = entry.get("teams") if isinstance(entry.get("teams"), dict) else {}
            team_in = teams.get("in") if isinstance(teams.get("in"), dict) else {}
            team_out = teams.get("out") if isinstance(teams.get("out"), dict) else {}
            from_id = _as_optional_int(team_out.get("id"))
            to_id = _as_optional_int(team_in.get("id"))
            transfer_type = entry.get("type")
            if not isinstance(transfer_type, str):
                transfer_type = "N/A"
            provider_key = build_transfer_provider_key(
                athlete_provider_id=athlete_provider_id,
                transfer_date=transfer_date.isoformat(),
                from_club_provider_id=from_id,
                to_club_provider_id=to_id,
                transfer_type=transfer_type,
            )
            out.append(
                MappedTransfer(
                    athlete_provider_id=athlete_provider_id,
                    athlete_name=athlete_name,
                    transfer_date=transfer_date,
                    from_club_provider_id=from_id,
                    to_club_provider_id=to_id,
                    transfer_type=transfer_type.strip(),
                    provider_key=provider_key,
                )
            )
    return out
