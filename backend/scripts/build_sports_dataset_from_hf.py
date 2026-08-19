#!/usr/bin/env python3
"""Build minimized offline API-Football-shaped fixtures from the public HF corpus.

Source: HuggingFace dataset eatpizzanot/soccer-dataset (API-Football derived).
This is a freeze for offline tests when a live API key is unavailable.
Prefer backend/scripts/acquire_sports_dataset.py when API_FOOTBALL_KEY is set.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
TMP = REPO_ROOT / "_tmp_dataset"
OUT = BACKEND_ROOT / "tests" / "fixtures" / "api_football"
DATASET_VERSION = "0.1.0"
HF_SOURCE = "https://huggingface.co/datasets/eatpizzanot/soccer-dataset"
PROVIDER = "api-football-v3"
LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
}
RARE_TAGS = (
    "penalty_scored",
    "penalty_missed",
    "penalty_saved",
    "red_card",
    "substitution",
    "clean_sheet",
    "own_goal",
    "postponement",
    "post_match_correction",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_dump(path: Path, obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw + "\n", encoding="utf-8", newline="\n")
    return _sha256_bytes((raw + "\n").encode("utf-8"))


def _clean_num(v: Any) -> Any:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:
            pass
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _clean_str(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip()
    return s or None


def envelope(endpoint: str, parameters: dict[str, Any], response: list[Any]) -> dict[str, Any]:
    return {
        "get": endpoint,
        "parameters": {k: str(v) for k, v in parameters.items()},
        "errors": [],
        "results": len(response),
        "paging": {"current": 1, "total": 1},
        "response": response,
    }


def select_matches(ft: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    agg = (
        stats.groupby("fixture_id")
        .agg(
            red=("cards_red", "sum"),
            pen_sc=("penalty_scored", "sum"),
            pen_mi=("penalty_missed", "sum"),
            pen_sa=("penalty_saved", "sum"),
            subs=("games_substitute", "sum"),
            players=("player_id", "count"),
        )
        .reset_index()
    )
    # simpler clean sheet flag from match score
    merged = ft.merge(agg, left_on="id", right_on="fixture_id", how="inner")
    merged["clean_sheet"] = (
        (merged["goals_home"].fillna(-1) == 0) | (merged["goals_away"].fillna(-1) == 0)
    ).astype(int)
    merged["score_rarity"] = (
        (merged["pen_sa"] > 0).astype(int) * 8
        + (merged["pen_mi"] > 0).astype(int) * 6
        + (merged["pen_sc"] > 0).astype(int) * 4
        + (merged["red"] > 0).astype(int) * 3
        + (merged["clean_sheet"] > 0).astype(int) * 2
        + (merged["subs"] > 0).astype(int)
    )
    selected_rows: list[pd.Series] = []
    covered = {t: False for t in ("pen_sa", "pen_mi", "pen_sc", "red", "clean_sheet", "subs")}

    # first pass: 2 high-rarity + 2 ordinary recent matches per league
    for league_api_id, group in merged.groupby("league_api_id"):
        g_rare = group.sort_values(["score_rarity", "date_utc"], ascending=[False, False])
        g_ord = group.sort_values(["score_rarity", "date_utc"], ascending=[True, False])
        pick = pd.concat([g_rare.head(2), g_ord.head(2)]).drop_duplicates(subset=["id"])
        selected_rows.extend([row for _, row in pick.iterrows()])
        for _, row in pick.iterrows():
            for key in covered:
                if row[key] > 0:
                    covered[key] = True

    selected = pd.DataFrame(selected_rows).drop_duplicates(subset=["id"])

    # second pass: fill missing rare tags globally
    for key, flag in list(covered.items()):
        if flag:
            continue
        cand = merged[~merged["id"].isin(selected["id"])].sort_values(
            ["score_rarity", "date_utc"], ascending=[False, False]
        )
        cand = cand[cand[key] > 0]
        if cand.empty:
            continue
        selected = pd.concat([selected, cand.head(1)], ignore_index=True)
        covered[key] = True

    # ensure >=20
    if len(selected) < 20:
        need = 20 - len(selected)
        extra = (
            merged[~merged["id"].isin(selected["id"])]
            .sort_values(["score_rarity", "date_utc"], ascending=[False, False])
            .head(need)
        )
        selected = pd.concat([selected, extra], ignore_index=True)

    return selected.sort_values(["league_api_id", "date_utc"]).reset_index(drop=True)


def tags_for_row(row: pd.Series, player_stats: pd.DataFrame) -> list[str]:
    tags: list[str] = []
    if row.get("pen_sc", 0) > 0:
        tags.append("penalty_scored")
    if row.get("pen_mi", 0) > 0:
        tags.append("penalty_missed")
    if row.get("pen_sa", 0) > 0:
        tags.append("penalty_saved")
    if row.get("red", 0) > 0:
        tags.append("red_card")
    if row.get("subs", 0) > 0:
        tags.append("substitution")
    if row.get("clean_sheet", 0) > 0:
        tags.append("clean_sheet")
    # confirm CS also from keeper stats if available
    if "clean_sheet" not in tags:
        keepers = player_stats[
            player_stats["games_position"].isin(["G", "Goalkeeper"])
            & (player_stats["goals_conceded"].fillna(1) == 0)
            & (player_stats["games_minutes"].fillna(0) >= 90)
        ]
        if not keepers.empty:
            tags.append("clean_sheet")
    return tags


def build_fixture_payload(row: pd.Series, teams: pd.DataFrame) -> dict[str, Any]:
    home = teams[teams["id"] == row["home_team_id"]]
    away = teams[teams["id"] == row["away_team_id"]]
    home_name = _clean_str(home.iloc[0]["name"]) if len(home) else f"team-{int(row['home_team_id'])}"
    away_name = _clean_str(away.iloc[0]["name"]) if len(away) else f"team-{int(row['away_team_id'])}"
    home_api = _clean_num(home.iloc[0]["api_football_id"]) if len(home) and "api_football_id" in home.columns else _clean_num(row["home_team_id"])
    away_api = _clean_num(away.iloc[0]["api_football_id"]) if len(away) and "api_football_id" in away.columns else _clean_num(row["away_team_id"])
    date = _clean_str(row["date_utc"]) or "1970-01-01T00:00:00+00:00"
    if " " in date and "T" not in date:
        date = date.replace(" ", "T") + "+00:00"
    ts = int(pd.Timestamp(date, tz="UTC").timestamp())
    fid = int(row["api_football_id"])
    league_api = int(row["league_api_id"])
    item = {
        "fixture": {
            "id": fid,
            "referee": None,
            "timezone": "UTC",
            "date": date if "+" in date or date.endswith("Z") else date + "+00:00",
            "timestamp": ts,
            "periods": {"first": None, "second": None},
            "venue": {"id": None, "name": None, "city": None},
            "status": {"long": "Match Finished", "short": "FT", "elapsed": 90, "extra": None},
        },
        "league": {
            "id": league_api,
            "name": LEAGUES[league_api],
            "country": _clean_str(row.get("country")),
            "logo": None,
            "flag": None,
            "season": int(str(date)[:4]),
            "round": None,
        },
        "teams": {
            "home": {"id": home_api, "name": home_name, "logo": None, "winner": None},
            "away": {"id": away_api, "name": away_name, "logo": None, "winner": None},
        },
        "goals": {"home": _clean_num(row["goals_home"]), "away": _clean_num(row["goals_away"])},
        "score": {
            "halftime": {"home": None, "away": None},
            "fulltime": {"home": _clean_num(row["goals_home"]), "away": _clean_num(row["goals_away"])},
            "extratime": {"home": None, "away": None},
            "penalty": {"home": None, "away": None},
        },
    }
    gh, ga = item["goals"]["home"], item["goals"]["away"]
    if gh is not None and ga is not None:
        item["teams"]["home"]["winner"] = gh > ga
        item["teams"]["away"]["winner"] = ga > gh
        if gh == ga:
            item["teams"]["home"]["winner"] = None
            item["teams"]["away"]["winner"] = None
    return envelope("fixtures", {"id": fid}, [item])


def build_events_from_stats(
    fid: int,
    players: pd.DataFrame,
    stats: pd.DataFrame,
    team_api_by_internal: dict[int, int],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Approximate events from per-player match stats (timeline minutes unknown)."""
    joined = players.merge(stats, on=["fixture_id", "player_id"], how="left", suffixes=("", "_s"))
    events: list[dict[str, Any]] = []
    counts = defaultdict(int)
    minute = 1

    def add_event(team_id: int, player_id: int, player_name: str | None, type_: str, detail: str, assist_id=None, assist_name=None):
        nonlocal minute
        events.append(
            {
                "time": {"elapsed": minute, "extra": None},
                "team": {"id": team_id, "name": None, "logo": None},
                "player": {"id": player_id, "name": player_name},
                "assist": {"id": assist_id, "name": assist_name},
                "type": type_,
                "detail": detail,
                "comments": None,
            }
        )
        minute = min(90, minute + 1)

    for _, r in joined.iterrows():
        team_internal = int(r["team_id"])
        team_api = int(team_api_by_internal.get(team_internal, team_internal))
        pid = int(r["player_id"])
        pname = _clean_str(r.get("player_name"))
        pen_sc = int(_clean_num(r.get("penalty_scored")) or 0)
        pen_mi = int(_clean_num(r.get("penalty_missed")) or 0)
        goals = int(_clean_num(r.get("goals_total")) or 0)
        assists = int(_clean_num(r.get("goals_assists")) or 0)
        yellow = int(_clean_num(r.get("cards_yellow")) or 0)
        red = int(_clean_num(r.get("cards_red")) or 0)
        # penalties scored counted as Penalty, remaining goals as Normal Goal
        normal_goals = max(0, goals - pen_sc)
        for _ in range(pen_sc):
            add_event(team_api, pid, pname, "Goal", "Penalty")
            counts["penalty_scored"] += 1
        for _ in range(normal_goals):
            add_event(team_api, pid, pname, "Goal", "Normal Goal")
            counts["normal_goal"] += 1
        for _ in range(pen_mi):
            add_event(team_api, pid, pname, "Goal", "Missed Penalty")
            counts["penalty_missed"] += 1
        for _ in range(assists):
            # assist-only marker event not standard; attach as synthetic comment goal assist proxy skipped
            counts["assist_stat"] += 1
        for _ in range(yellow):
            add_event(team_api, pid, pname, "Card", "Yellow Card")
            counts["yellow_card"] += 1
        for _ in range(red):
            detail = "Red Card"
            add_event(team_api, pid, pname, "Card", detail)
            counts["red_card"] += 1
        if bool(r.get("games_substitute")) and (_clean_num(r.get("games_minutes")) or 0) > 0:
            add_event(team_api, pid, pname, "subst", "Substitution 1")
            counts["substitution"] += 1
        pen_sa = int(_clean_num(r.get("penalty_saved")) or 0)
        for _ in range(pen_sa):
            # no dedicated event detail in public docs; keep count for players endpoint validation
            counts["penalty_saved"] += 1

    return envelope("fixtures/events", {"fixture": fid}, events), dict(counts)


def build_players_payload(
    fid: int,
    players: pd.DataFrame,
    stats: pd.DataFrame,
    team_api_by_internal: dict[int, int],
    team_name_by_internal: dict[int, str],
) -> dict[str, Any]:
    joined = players.merge(stats, on=["fixture_id", "player_id"], how="left", suffixes=("", "_s"))
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for _, r in joined.iterrows():
        team_internal = int(r["team_id"])
        team_api = int(team_api_by_internal.get(team_internal, team_internal))
        pos = _clean_str(r.get("games_position")) or _clean_str(r.get("position"))
        entry = {
            "player": {
                "id": int(r["player_id"]),
                "name": _clean_str(r.get("player_name")),
                "photo": None,
            },
            "statistics": [
                {
                    "games": {
                        "minutes": _clean_num(r.get("games_minutes")),
                        "number": _clean_num(r.get("number")),
                        "position": pos,
                        "rating": _clean_str(r.get("games_rating"))
                        if r.get("games_rating") is not None
                        else None,
                        "captain": bool(r.get("captain")) if pd.notna(r.get("captain")) else False,
                        "substitute": bool(r.get("games_substitute"))
                        if pd.notna(r.get("games_substitute"))
                        else bool(r.get("is_starter")) is False
                        if pd.notna(r.get("is_starter"))
                        else None,
                    },
                    "offsides": None,
                    "shots": {"total": _clean_num(r.get("shots_total")), "on": _clean_num(r.get("shots_on"))},
                    "goals": {
                        "total": _clean_num(r.get("goals_total")),
                        "conceded": _clean_num(r.get("goals_conceded")),
                        "assists": _clean_num(r.get("goals_assists")),
                        "saves": _clean_num(r.get("goals_saves")),
                    },
                    "passes": {
                        "total": _clean_num(r.get("passes_total")),
                        "key": _clean_num(r.get("passes_key")),
                        "accuracy": _clean_num(r.get("passes_accuracy")),
                    },
                    "tackles": {
                        "total": _clean_num(r.get("tackles_total")),
                        "blocks": _clean_num(r.get("tackles_blocks")),
                        "interceptions": _clean_num(r.get("tackles_interceptions")),
                    },
                    "duels": {"total": _clean_num(r.get("duels_total")), "won": _clean_num(r.get("duels_won"))},
                    "dribbles": {
                        "attempts": _clean_num(r.get("dribbles_attempts")),
                        "success": _clean_num(r.get("dribbles_success")),
                        "past": _clean_num(r.get("dribbles_past")),
                    },
                    "fouls": {
                        "drawn": _clean_num(r.get("fouls_drawn")),
                        "committed": _clean_num(r.get("fouls_committed")),
                    },
                    "cards": {
                        "yellow": _clean_num(r.get("cards_yellow")),
                        "red": _clean_num(r.get("cards_red")),
                    },
                    "penalty": {
                        "won": _clean_num(r.get("penalty_won")),
                        "commited": _clean_num(r.get("penalty_commited")),
                        "scored": _clean_num(r.get("penalty_scored")),
                        "missed": _clean_num(r.get("penalty_missed")),
                        "saved": _clean_num(r.get("penalty_saved")),
                    },
                }
            ],
        }
        by_team[team_api].append(entry)

    response = []
    for team_api, plist in by_team.items():
        # reverse map name
        name = None
        for internal, api in team_api_by_internal.items():
            if api == team_api:
                name = team_name_by_internal.get(internal)
                break
        response.append(
            {
                "team": {"id": team_api, "name": name, "logo": None, "update": None},
                "players": plist,
            }
        )
    return envelope("fixtures/players", {"fixture": fid}, response)


def build_lineups_payload(
    fid: int,
    lineups: pd.DataFrame,
    players: pd.DataFrame,
    team_api_by_internal: dict[int, int],
    team_name_by_internal: dict[int, str],
) -> dict[str, Any]:
    response = []
    for _, lu in lineups.iterrows():
        team_internal = int(lu["team_id"])
        team_api = int(team_api_by_internal.get(team_internal, team_internal))
        team_players = players[players["team_id"] == team_internal]
        start_xi = []
        subs = []
        for _, pl in team_players.iterrows():
            node = {
                "player": {
                    "id": int(pl["player_id"]),
                    "name": _clean_str(pl.get("player_name")),
                    "number": _clean_num(pl.get("number")),
                    "pos": _clean_str(pl.get("position")),
                    "grid": None,
                }
            }
            if bool(pl.get("is_starter")):
                start_xi.append(node)
            else:
                subs.append(node)
        response.append(
            {
                "team": {
                    "id": team_api,
                    "name": team_name_by_internal.get(team_internal),
                    "logo": None,
                    "colors": None,
                },
                "formation": _clean_str(lu.get("formation")),
                "startXI": start_xi,
                "substitutes": subs,
                "coach": {
                    "id": _clean_num(lu.get("coach_api_id")),
                    "name": _clean_str(lu.get("coach_name")),
                    "photo": None,
                },
            }
        )
    return envelope("fixtures/lineups", {"fixture": fid}, response)


def build_leagues_payload() -> dict[str, Any]:
    response = []
    for lid, name in LEAGUES.items():
        country = {
            39: "England",
            140: "Spain",
            135: "Italy",
            78: "Germany",
            61: "France",
        }[lid]
        response.append(
            {
                "league": {"id": lid, "name": name, "type": "League", "logo": None},
                "country": {"name": country, "code": None, "flag": None},
                "seasons": [
                    {
                        "year": 2024,
                        "start": None,
                        "end": None,
                        "current": True,
                        "coverage": {
                            "fixtures": {
                                "events": True,
                                "lineups": True,
                                "statistics_fixtures": True,
                                "statistics_players": True,
                            },
                            "standings": True,
                            "players": True,
                            "top_scorers": True,
                            "top_assists": True,
                            "top_cards": True,
                            "injuries": True,
                            "predictions": True,
                            "odds": False,
                        },
                    }
                ],
            }
        )
    return envelope("leagues", {"current": "true"}, response)


def main() -> None:
    required = [
        "fixtures.parquet",
        "leagues.parquet",
        "teams.parquet",
        "fixture_players.parquet",
        "fixture_players_stats_flat.parquet",
        "fixture_lineups.parquet",
    ]
    missing = [n for n in required if not (TMP / n).exists()]
    if missing:
        raise SystemExit(f"Missing local HF extracts in {TMP}: {missing}")

    fx = pd.read_parquet(
        TMP / "fixtures.parquet",
        columns=[
            "id",
            "api_football_id",
            "date_utc",
            "league_id",
            "home_team_id",
            "away_team_id",
            "goals_home",
            "goals_away",
            "status_norm",
        ],
    )
    lg = pd.read_parquet(TMP / "leagues.parquet")
    teams = pd.read_parquet(TMP / "teams.parquet")
    lg["api_football_id"] = pd.to_numeric(lg["api_football_id"], errors="coerce")
    wanted = lg[lg["api_football_id"].isin(LEAGUES.keys())][
        ["id", "api_football_id", "name", "country"]
    ].rename(columns={"id": "league_id", "api_football_id": "league_api_id", "name": "league_name"})
    ft = fx[
        (fx["status_norm"] == "FT")
        & fx["league_id"].isin(set(wanted["league_id"]))
        & fx["api_football_id"].notna()
    ].merge(wanted, on="league_id")

    stats_cols = [
        "fixture_id",
        "player_id",
        "cards_red",
        "cards_yellow",
        "dribbles_attempts",
        "dribbles_past",
        "dribbles_success",
        "duels_total",
        "duels_won",
        "fouls_committed",
        "fouls_drawn",
        "games_minutes",
        "games_position",
        "games_rating",
        "games_substitute",
        "goals_assists",
        "goals_conceded",
        "goals_saves",
        "goals_total",
        "passes_accuracy",
        "passes_key",
        "passes_total",
        "penalty_commited",
        "penalty_missed",
        "penalty_saved",
        "penalty_scored",
        "penalty_won",
        "shots_on",
        "shots_total",
        "tackles_blocks",
        "tackles_interceptions",
        "tackles_total",
    ]
    stats = pd.read_parquet(TMP / "fixture_players_stats_flat.parquet", columns=stats_cols)
    stats = stats[stats["fixture_id"].isin(ft["id"])]

    selected = select_matches(ft, stats)
    selected_ids = set(selected["id"].tolist())

    players = pd.read_parquet(TMP / "fixture_players.parquet")
    players = players[players["fixture_id"].isin(selected_ids)]
    stats = stats[stats["fixture_id"].isin(selected_ids)]
    lineups = pd.read_parquet(TMP / "fixture_lineups.parquet")
    lineups = lineups[lineups["fixture_id"].isin(selected_ids)]

    if OUT.exists():
        for path in OUT.rglob("*"):
            if path.is_file():
                path.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    files_meta: list[dict[str, Any]] = []
    matches_meta: list[dict[str, Any]] = []
    tag_coverage = {t: [] for t in RARE_TAGS}

    # leagues reference
    leagues_path = OUT / "reference" / "leagues.json"
    digest = _json_dump(leagues_path, build_leagues_payload())
    files_meta.append(
        {
            "path": leagues_path.relative_to(OUT).as_posix(),
            "endpoint": "/leagues",
            "sha256": digest,
            "fixture_id": None,
        }
    )

    team_api_by_internal: dict[int, int] = {}
    team_name_by_internal: dict[int, str] = {}
    for _, t in teams.iterrows():
        internal = int(t["id"])
        api = _clean_num(t.get("api_football_id")) or internal
        team_api_by_internal[internal] = int(api)
        team_name_by_internal[internal] = _clean_str(t.get("name")) or f"team-{internal}"

    # teams reference for clubs appearing in selected matches
    team_ids = set(selected["home_team_id"]).union(set(selected["away_team_id"]))
    team_rows = teams[teams["id"].isin(team_ids)]
    teams_response = []
    for _, t in team_rows.iterrows():
        teams_response.append(
            {
                "team": {
                    "id": int(_clean_num(t.get("api_football_id")) or t["id"]),
                    "name": _clean_str(t.get("name")),
                    "code": _clean_str(t.get("code")) if "code" in t else None,
                    "country": _clean_str(t.get("country")) if "country" in t else None,
                    "founded": None,
                    "national": False,
                    "logo": None,
                },
                "venue": {"id": None, "name": None, "address": None, "city": None, "capacity": None, "surface": None, "image": None},
            }
        )
    teams_path = OUT / "reference" / "teams.json"
    digest = _json_dump(teams_path, envelope("teams", {"ids": "selected"}, teams_response))
    files_meta.append(
        {
            "path": teams_path.relative_to(OUT).as_posix(),
            "endpoint": "/teams",
            "sha256": digest,
            "fixture_id": None,
        }
    )

    for _, row in selected.iterrows():
        fid = int(row["api_football_id"])
        league_api = int(row["league_api_id"])
        base = OUT / "matches" / str(league_api) / str(fid)
        pstats = stats[stats["fixture_id"] == row["id"]]
        pplayers = players[players["fixture_id"] == row["id"]]
        plineups = lineups[lineups["fixture_id"] == row["id"]]
        tags = tags_for_row(row, pstats)

        payloads = {
            "fixtures.json": build_fixture_payload(row, teams),
            "fixtures_events.json": None,
            "fixtures_lineups.json": build_lineups_payload(
                fid, plineups, pplayers, team_api_by_internal, team_name_by_internal
            ),
            "fixtures_players.json": build_players_payload(
                fid, pplayers, pstats, team_api_by_internal, team_name_by_internal
            ),
        }
        events_payload, event_counts = build_events_from_stats(
            fid, pplayers, pstats, team_api_by_internal
        )
        payloads["fixtures_events.json"] = events_payload
        if event_counts.get("penalty_saved", 0) > 0 and "penalty_saved" not in tags:
            tags.append("penalty_saved")

        file_entries = []
        for name, payload in payloads.items():
            path = base / name
            digest = _json_dump(path, payload)
            endpoint = {
                "fixtures.json": "/fixtures",
                "fixtures_events.json": "/fixtures/events",
                "fixtures_lineups.json": "/fixtures/lineups",
                "fixtures_players.json": "/fixtures/players",
            }[name]
            entry = {
                "path": path.relative_to(OUT).as_posix(),
                "endpoint": endpoint,
                "sha256": digest,
                "fixture_id": fid,
            }
            files_meta.append(entry)
            file_entries.append(entry)

        match_meta = {
            "fixture_id": fid,
            "league_id": league_api,
            "league_name": LEAGUES[league_api],
            "date_utc": _clean_str(row["date_utc"]),
            "status": "FT",
            "home_team_id": int(team_api_by_internal.get(int(row["home_team_id"]), row["home_team_id"])),
            "away_team_id": int(team_api_by_internal.get(int(row["away_team_id"]), row["away_team_id"])),
            "score": {
                "home": _clean_num(row["goals_home"]),
                "away": _clean_num(row["goals_away"]),
            },
            "tags": sorted(set(tags)),
            "files": [e["path"] for e in file_entries],
            "notes": {
                "events_reconstruction": "events approximated from player match stats; minutes are ordinal placeholders, not official timeline",
                "own_goal": "not derivable from stats corpus",
            },
        }
        matches_meta.append(match_meta)
        for t in tags:
            tag_coverage[t].append(fid)

    # rare cases not found
    not_found = []
    for tag in RARE_TAGS:
        if not tag_coverage.get(tag):
            not_found.append(tag)
            tag_coverage[tag] = []

    # explicit known gaps for this freeze
    for forced in ("own_goal", "postponement", "post_match_correction"):
        if forced not in not_found:
            # ensure listed even if somehow tagged
            if not tag_coverage.get(forced):
                not_found.append(forced)

    # endpoint stubs not present in HF freeze
    missing_endpoints = {
        "/players": "not included in match freeze; acquire via API for listone samples",
        "/players/squads": "not included in match freeze; acquire via API",
        "/injuries": "no injuries table in HF corpus; mark not_reperito",
        "/transfers": "no transfers table in HF corpus; mark not_reperito",
        "/standings": "not included in match freeze; acquire via API for IA context",
        "/predictions": "not included in match freeze; acquire via API for IA signal",
    }

    manifest = {
        "dataset": {
            "name": "api_football_offline_corpus",
            "version": DATASET_VERSION,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provider": PROVIDER,
            "card": "EP00-02",
            "provenance": {
                "kind": "reconstructed_from_api_football_derived_corpus",
                "source": HF_SOURCE,
                "source_note": "Payloads reshaped to API-Football v3 envelopes and minimized for offline tests. Re-fetch with scripts/acquire_sports_dataset.py for canonical provider JSON.",
                "contains_secrets": False,
            },
        },
        "leagues_required": [{"id": k, "name": v} for k, v in LEAGUES.items()],
        "fixtures": matches_meta,
        "coverage": {
            "fixture_count": len(matches_meta),
            "leagues_represented": sorted({m["league_id"] for m in matches_meta}),
            "rare_cases_found": {k: v for k, v in tag_coverage.items() if v},
            "rare_cases_not_found": sorted(set(not_found)),
            "endpoints_present": sorted({f["endpoint"] for f in files_meta}),
            "endpoints_not_reperito": missing_endpoints,
        },
        "files": files_meta,
        "sanitization": {
            "removed": ["auth headers", "provider API credentials", "photo CDN URLs", "logos"],
            "minimization": "Only fields needed for EP00-01 mapping retained; nulls kept where schema expects keys",
            "deterministic_json": "sort_keys=True, compact separators, trailing newline",
        },
    }

    manifest_path = OUT / "manifest.json"
    _json_dump(manifest_path, manifest)

    # checksums file (paths relative to dataset root)
    lines = []
    for f in sorted(files_meta, key=lambda x: x["path"]):
        lines.append(f"{f['sha256']}  {f['path']}")
    # include manifest checksum of content without self-reference: hash file after write
    manifest_hash = _sha256_file(manifest_path)
    lines.append(f"{manifest_hash}  manifest.json")
    (OUT / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "fixtures": len(matches_meta),
                "leagues": sorted({m["league_id"] for m in matches_meta}),
                "rare_found": {k: len(v) for k, v in tag_coverage.items() if v},
                "rare_not_found": sorted(set(not_found)),
                "out": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
