#!/usr/bin/env python3
"""Acquire canonical API-Football v3 payloads and refresh the offline corpus.

Uses batched `GET /fixtures?ids=` (max 20) so events/lineups/players come embedded
when the provider returns them — far fewer quota hits than 4 calls per match.

Requires API_FOOTBALL_KEY from the process environment or repo-root `.env`
(never commit `.env`; see `.env.example`).

Usage:
  python backend/scripts/acquire_sports_dataset.py --from-manifest
  python backend/scripts/acquire_sports_dataset.py --fixture-ids 1208021,1208022 --league-id 39
  python backend/scripts/acquire_sports_dataset.py --from-manifest --enrich-rare
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from config.settings.dotenv import load_repo_dotenv

OUT = BACKEND_ROOT / "tests" / "fixtures" / "api_football"
BASE_URL = "https://v3.football.api-sports.io"
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


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    if path == REPO_ROOT / ".env":
        load_repo_dotenv(REPO_ROOT)
        return
    from config.settings.dotenv import load_dotenv_file

    load_dotenv_file(path)


def resolve_api_key() -> str | None:
    load_dotenv()
    return os.environ.get("API_FOOTBALL_KEY") or os.environ.get("APISPORTS_KEY")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def minimize(obj: Any) -> Any:
    drop_keys = {
        "logo",
        "photo",
        "flag",
        "image",
        "colors",
        "headers",
        "Authorization",
        "x-apisports-key",
        "x-rapidapi-key",
    }
    if isinstance(obj, dict):
        return {k: minimize(v) for k, v in obj.items() if k not in drop_keys}
    if isinstance(obj, list):
        return [minimize(v) for v in obj]
    return obj


def dump_json(path: Path, obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw + "\n", encoding="utf-8", newline="\n")
    return sha256_bytes((raw + "\n").encode("utf-8"))


def envelope(endpoint: str, parameters: dict[str, Any], response: list[Any]) -> dict[str, Any]:
    return {
        "get": endpoint.lstrip("/"),
        "parameters": {k: str(v) for k, v in parameters.items()},
        "errors": [],
        "results": len(response),
        "paging": {"current": 1, "total": 1},
        "response": response,
    }


def api_get(key: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    url = f"{BASE_URL}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "x-apisports-key": key,
            "Accept": "application/json",
            "User-Agent": "fantappero-ep00-02-acquire",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            remaining = resp.headers.get("x-ratelimit-requests-remaining")
            body = resp.read()
            if remaining is not None:
                print(f"  quota remaining today: {remaining}")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HTTP {exc.code} for {path}: {exc.read()[:300]!r}") from exc
    data = json.loads(body.decode("utf-8"))
    errors = data.get("errors")
    if errors:
        # empty list is ok; dict/list with content is not
        if isinstance(errors, dict) and errors:
            raise SystemExit(f"API errors for {path} {params}: {errors}")
        if isinstance(errors, list) and errors:
            raise SystemExit(f"API errors for {path} {params}: {errors}")
    return minimize(data)


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def load_manifest_fixture_ids(manifest_path: Path) -> list[tuple[int, int]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [(int(f["league_id"]), int(f["fixture_id"])) for f in manifest.get("fixtures") or []]


def derive_tags(item: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    events = item.get("events") or []
    players_blocks = item.get("players") or []
    goals = item.get("goals") or {}

    for ev in events:
        detail = str(ev.get("detail") or "")
        type_ = str(ev.get("type") or "")
        if detail == "Own Goal":
            tags.add("own_goal")
        elif detail == "Penalty":
            tags.add("penalty_scored")
        elif detail == "Missed Penalty":
            tags.add("penalty_missed")
        elif detail in {"Red Card", "Yellow Red Card", "Yellow-Red Card"}:
            tags.add("red_card")
        elif type_.lower().startswith("subst") or detail.startswith("Substitution"):
            tags.add("substitution")

    for block in players_blocks:
        for pl in block.get("players") or []:
            for st in pl.get("statistics") or []:
                pen = st.get("penalty") or {}
                cards = st.get("cards") or {}
                games = st.get("games") or {}
                if (pen.get("scored") or 0) not in (0, None):
                    tags.add("penalty_scored")
                if (pen.get("missed") or 0) not in (0, None):
                    tags.add("penalty_missed")
                if (pen.get("saved") or 0) not in (0, None):
                    tags.add("penalty_saved")
                if (cards.get("red") or 0) not in (0, None):
                    tags.add("red_card")
                if games.get("substitute") is True:
                    tags.add("substitution")

    gh, ga = goals.get("home"), goals.get("away")
    if gh == 0 or ga == 0:
        tags.add("clean_sheet")

    status = ((item.get("fixture") or {}).get("status") or {}).get("short")
    if status == "PST":
        tags.add("postponement")

    return sorted(tags)


def split_and_write(
    league_id: int,
    item: dict[str, Any],
    files_meta: list[dict[str, Any]],
) -> tuple[int, list[str], list[str], dict[str, Any]]:
    fixture = item.get("fixture") or {}
    fid = int(fixture["id"])
    base = OUT / "matches" / str(league_id) / str(fid)

    fixture_only = {
        "fixture": item.get("fixture"),
        "league": item.get("league"),
        "teams": item.get("teams"),
        "goals": item.get("goals"),
        "score": item.get("score"),
    }
    events = item.get("events") or []
    lineups = item.get("lineups") or []
    players = item.get("players") or []

    payloads = {
        "fixtures.json": ("/fixtures", {"id": fid}, [fixture_only]),
        "fixtures_events.json": ("/fixtures/events", {"fixture": fid}, events),
        "fixtures_lineups.json": ("/fixtures/lineups", {"fixture": fid}, lineups),
        "fixtures_players.json": ("/fixtures/players", {"fixture": fid}, players),
    }

    file_paths: list[str] = []
    for name, (endpoint, params, response) in payloads.items():
        path = base / name
        digest = dump_json(path, envelope(endpoint, params, response))
        rel = path.relative_to(OUT).as_posix()
        files_meta.append(
            {"path": rel, "endpoint": endpoint, "sha256": digest, "fixture_id": fid}
        )
        file_paths.append(rel)

    tags = derive_tags(item)
    meta = {
        "fixture_id": fid,
        "league_id": league_id,
        "league_name": LEAGUES.get(league_id) or (item.get("league") or {}).get("name"),
        "date_utc": fixture.get("date"),
        "status": (fixture.get("status") or {}).get("short"),
        "home_team_id": ((item.get("teams") or {}).get("home") or {}).get("id"),
        "away_team_id": ((item.get("teams") or {}).get("away") or {}).get("id"),
        "score": {
            "home": (item.get("goals") or {}).get("home"),
            "away": (item.get("goals") or {}).get("away"),
        },
        "tags": tags,
        "files": file_paths,
        "notes": {
            "provenance": "provider_v3_batch_ids",
            "embedded_events": bool(events),
            "embedded_lineups": bool(lineups),
            "embedded_players": bool(players),
        },
    }
    return fid, tags, file_paths, meta


def fetch_missing_parts(key: str, item: dict[str, Any], sleep_s: float) -> dict[str, Any]:
    """Fallback to dedicated endpoints if batch payload lacks embeds."""
    fid = int((item.get("fixture") or {})["id"])
    out = dict(item)
    if not out.get("events"):
        print(f"  fallback /fixtures/events for {fid}")
        data = api_get(key, "/fixtures/events", {"fixture": fid})
        out["events"] = data.get("response") or []
        time.sleep(sleep_s)
    if not out.get("lineups"):
        print(f"  fallback /fixtures/lineups for {fid}")
        data = api_get(key, "/fixtures/lineups", {"fixture": fid})
        out["lineups"] = data.get("response") or []
        time.sleep(sleep_s)
    if not out.get("players"):
        print(f"  fallback /fixtures/players for {fid}")
        data = api_get(key, "/fixtures/players", {"fixture": fid})
        out["players"] = data.get("response") or []
        time.sleep(sleep_s)
    return out


def refresh_reference(key: str, sleep_s: float, files_meta: list[dict[str, Any]]) -> None:
    print("Refreshing /leagues coverage for big-5…")
    leagues_resp: list[Any] = []
    for lid in LEAGUES:
        data = api_get(key, "/leagues", {"id": lid, "current": "true"})
        leagues_resp.extend(data.get("response") or [])
        time.sleep(sleep_s)
    path = OUT / "reference" / "leagues.json"
    digest = dump_json(path, envelope("/leagues", {"current": "true"}, leagues_resp))
    files_meta.append(
        {"path": path.relative_to(OUT).as_posix(), "endpoint": "/leagues", "sha256": digest, "fixture_id": None}
    )

    # teams from selected matches will be filled after acquire; placeholder kept if empty
    teams_path = OUT / "reference" / "teams.json"
    if not teams_path.exists():
        dump_json(teams_path, envelope("/teams", {"ids": "selected"}, []))


def write_teams_reference(
    items: list[dict[str, Any]], files_meta: list[dict[str, Any]]
) -> None:
    by_id: dict[int, dict[str, Any]] = {}
    for item in items:
        for side in ("home", "away"):
            team = ((item.get("teams") or {}).get(side)) or {}
            tid = team.get("id")
            if tid is None:
                continue
            by_id[int(tid)] = {
                "team": {
                    "id": int(tid),
                    "name": team.get("name"),
                    "code": team.get("code"),
                    "country": None,
                    "founded": None,
                    "national": False,
                    "logo": None,
                },
                "venue": {
                    "id": None,
                    "name": None,
                    "address": None,
                    "city": None,
                    "capacity": None,
                    "surface": None,
                    "image": None,
                },
            }
    path = OUT / "reference" / "teams.json"
    digest = dump_json(
        path, envelope("/teams", {"ids": "selected"}, list(by_id.values()))
    )
    # replace any prior teams entry
    files_meta[:] = [f for f in files_meta if f.get("path") != path.relative_to(OUT).as_posix()]
    files_meta.append(
        {
            "path": path.relative_to(OUT).as_posix(),
            "endpoint": "/teams",
            "sha256": digest,
            "fixture_id": None,
        }
    )


def enrich_rare_cases(
    key: str,
    sleep_s: float,
    existing: list[tuple[int, int]],
    tag_index: dict[str, list[int]],
) -> list[tuple[int, int]]:
    """Spend a few extra calls to hunt own goals / postponements if missing."""
    extras: list[tuple[int, int]] = []
    have = {fid for _, fid in existing}

    if not tag_index.get("own_goal"):
        print("Enrich: scanning recent FT fixtures for Own Goal…")
        for lid in LEAGUES:
            data = api_get(key, "/fixtures", {"league": lid, "season": 2024, "status": "FT", "last": 20})
            time.sleep(sleep_s)
            ids = [int(x["fixture"]["id"]) for x in (data.get("response") or []) if x.get("fixture")]
            for batch in chunked(ids, 20):
                detail = api_get(key, "/fixtures", {"ids": "-".join(str(i) for i in batch)})
                time.sleep(sleep_s)
                for item in detail.get("response") or []:
                    fid = int(item["fixture"]["id"])
                    if fid in have:
                        continue
                    if any(
                        (ev.get("detail") == "Own Goal") for ev in (item.get("events") or [])
                    ):
                        lid_item = int((item.get("league") or {}).get("id") or lid)
                        extras.append((lid_item, fid))
                        have.add(fid)
                        print(f"  found own_goal fixture {fid} (league {lid_item})")
                        break
                if extras:
                    break
            if extras:
                break

    if not tag_index.get("postponement"):
        print("Enrich: scanning for PST…")
        for lid in LEAGUES:
            data = api_get(key, "/fixtures", {"league": lid, "season": 2024, "status": "PST"})
            time.sleep(sleep_s)
            resp = data.get("response") or []
            if resp:
                item = resp[0]
                fid = int(item["fixture"]["id"])
                if fid not in have:
                    extras.append((lid, fid))
                    print(f"  found postponement fixture {fid} (league {lid})")
                break

    return extras


def acquire(
    fixtures: list[tuple[int, int]],
    sleep_s: float,
    *,
    refresh_refs: bool = True,
    enrich_rare: bool = False,
) -> None:
    key = resolve_api_key()
    if not key:
        raise SystemExit(
            "Missing API_FOOTBALL_KEY. Set it in the environment or in repo-root .env "
            "(see .env.example)."
        )

    old: dict[str, Any] = {}
    manifest_path = OUT / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))

    files_meta: list[dict[str, Any]] = []
    if refresh_refs:
        refresh_reference(key, sleep_s, files_meta)

    # preserve order, unique by fixture id
    ordered: list[tuple[int, int]] = []
    seen: set[int] = set()
    for league_id, fid in fixtures:
        if fid not in seen:
            ordered.append((league_id, fid))
            seen.add(fid)

    league_by_fid = {fid: lid for lid, fid in ordered}
    all_items: list[dict[str, Any]] = []
    id_list = [fid for _, fid in ordered]

    print(f"Fetching {len(id_list)} fixtures via /fixtures?ids= batches…")
    for batch in chunked(id_list, 20):
        ids_param = "-".join(str(i) for i in batch)
        print(f"  batch {ids_param}")
        data = api_get(key, "/fixtures", {"ids": ids_param})
        time.sleep(sleep_s)
        for item in data.get("response") or []:
            fid = int(item["fixture"]["id"])
            item = fetch_missing_parts(key, item, sleep_s)
            all_items.append(item)
            # ensure league mapping
            lid = league_by_fid.get(fid) or int((item.get("league") or {}).get("id") or 0)
            league_by_fid[fid] = lid

    matches_meta: list[dict[str, Any]] = []
    tag_index: dict[str, list[int]] = defaultdict(list)

    for item in all_items:
        fid = int(item["fixture"]["id"])
        league_id = league_by_fid[fid]
        _, tags, _, meta = split_and_write(league_id, item, files_meta)
        matches_meta.append(meta)
        for t in tags:
            tag_index[t].append(fid)

    if enrich_rare:
        extras = enrich_rare_cases(key, sleep_s, ordered, tag_index)
        if extras:
            print(f"Fetching {len(extras)} enrichment fixtures…")
            for batch in chunked([fid for _, fid in extras], 20):
                data = api_get(key, "/fixtures", {"ids": "-".join(str(i) for i in batch)})
                time.sleep(sleep_s)
                for item in data.get("response") or []:
                    item = fetch_missing_parts(key, item, sleep_s)
                    fid = int(item["fixture"]["id"])
                    league_id = next(lid for lid, x in extras if x == fid)
                    league_by_fid[fid] = league_id
                    _, tags, _, meta = split_and_write(league_id, item, files_meta)
                    matches_meta.append(meta)
                    for t in tags:
                        tag_index[t].append(fid)

    write_teams_reference(all_items, files_meta)

    found = {k: sorted(set(v)) for k, v in tag_index.items() if v}
    not_found = [t for t in RARE_TAGS if t not in found]
    # post_match_correction requires dual snapshots — always explicit if absent
    if "post_match_correction" not in found and "post_match_correction" not in not_found:
        not_found.append("post_match_correction")

    endpoints_present = sorted({f["endpoint"] for f in files_meta})
    coverage = {
        "fixture_count": len(matches_meta),
        "leagues_represented": sorted({int(m["league_id"]) for m in matches_meta}),
        "rare_cases_found": found,
        "rare_cases_not_found": sorted(set(not_found)),
        "endpoints_present": endpoints_present,
        "endpoints_not_reperito": {
            "/players": "not in match freeze; acquire separately for listone",
            "/players/squads": "not in match freeze; acquire separately",
            "/injuries": "not fetched in this acquire run",
            "/transfers": "not fetched in this acquire run",
            "/standings": "not fetched in this acquire run",
            "/predictions": "not fetched in this acquire run",
        },
    }

    version = (old.get("dataset") or {}).get("version", "0.1.0")
    # bump minor when switching to live provider payloads
    if (old.get("dataset") or {}).get("provenance", {}).get("kind") != "provider_v3":
        version = "0.2.0"

    manifest = {
        "dataset": {
            "name": "api_football_offline_corpus",
            "version": version,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provider": "api-football-v3",
            "card": "EP00-02",
            "provenance": {
                "kind": "provider_v3",
                "source": BASE_URL,
                "source_note": "Canonical payloads via GET /fixtures?ids= (embedded events/lineups/players when available); sanitized/minimized before write.",
                "contains_secrets": False,
            },
        },
        "leagues_required": [{"id": k, "name": v} for k, v in LEAGUES.items()],
        "fixtures": sorted(matches_meta, key=lambda m: (m["league_id"], m["fixture_id"])),
        "coverage": coverage,
        "files": files_meta,
        "sanitization": {
            "removed": ["auth headers", "provider API credentials", "photo", "logo", "flag"],
            "minimization": "Drop media URLs and auth material; keep EP00-01 fields",
            "deterministic_json": "sort_keys=True, compact separators, trailing newline",
        },
    }
    dump_json(manifest_path, manifest)

    keep = {(int(m["league_id"]), int(m["fixture_id"])) for m in matches_meta}
    matches_root = OUT / "matches"
    if matches_root.is_dir():
        for league_dir in matches_root.iterdir():
            if not league_dir.is_dir() or not league_dir.name.isdigit():
                continue
            for fx_dir in list(league_dir.iterdir()):
                if not fx_dir.is_dir() or not fx_dir.name.isdigit():
                    continue
                key = (int(league_dir.name), int(fx_dir.name))
                if key not in keep:
                    shutil.rmtree(fx_dir)
                    print(f"  removed orphan match dir {fx_dir.relative_to(OUT).as_posix()}")

    lines = [f"{f['sha256']}  {f['path']}" for f in sorted(files_meta, key=lambda x: x["path"])]
    lines.append(f"{sha256_bytes(manifest_path.read_bytes())}  manifest.json")
    (OUT / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "fixtures": len(matches_meta),
                "leagues": coverage["leagues_represented"],
                "rare_found": {k: len(v) for k, v in found.items()},
                "rare_not_found": coverage["rare_cases_not_found"],
                "out": str(OUT),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-manifest", action="store_true")
    parser.add_argument("--fixture-ids", type=str)
    parser.add_argument("--league-id", type=int)
    parser.add_argument("--sleep", type=float, default=0.4)
    parser.add_argument("--enrich-rare", action="store_true", help="Extra calls to hunt own_goal/PST")
    parser.add_argument("--skip-refs", action="store_true", help="Skip /leagues refresh")
    args = parser.parse_args()

    fixtures: list[tuple[int, int]] = []
    if args.from_manifest:
        fixtures = load_manifest_fixture_ids(OUT / "manifest.json")
    elif args.fixture_ids and args.league_id:
        fixtures = [(args.league_id, int(x)) for x in args.fixture_ids.split(",") if x.strip()]
    else:
        parser.error("Use --from-manifest or --fixture-ids with --league-id")

    acquire(
        fixtures,
        args.sleep,
        refresh_refs=not args.skip_refs,
        enrich_rare=args.enrich_rare,
    )


if __name__ == "__main__":
    main()
