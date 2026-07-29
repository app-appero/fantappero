# League configuration (EP03-01)

Private league setup before launch: name, sport season, and at least three competitions from the MVP catalog. New leagues are saved in **draft** state with the creator as **owner** (administrator).

## API surface

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/leagues/competitions` | Bearer | List available MVP competitions |
| `POST` | `/leagues` | Bearer (verified email) | Create a draft league |
| `GET` | `/leagues/{league_id}` | Bearer (member or operator) | League configuration |
| `PATCH` | `/leagues/{league_id}` | Bearer (owner or operator) | Rename league |

### Create body (`POST /leagues`)

```json
{
  "name": "Lega degli amici",
  "season_year": 2025,
  "competition_ids": [
    "00000000-0000-0000-0000-000000000001",
    "00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000003"
  ]
}
```

- `season_year` — start year of the sport season (e.g. 2025 for 2025/26)
- `competition_ids` — 3–5 UUIDs from `GET /leagues/competitions` (no duplicates)

### Response shape (`LeagueResponse`)

- `id`, `name`, `season_year`, `state` (`draft` | `active`)
- `role` — caller membership role (`owner`, `member`, or `null` for platform operators)
- `competitions` — selected competition summaries

Errors use `{ "code", "message" }` (`league_validation_error`, `email_not_verified`, `forbidden`).

## Domain rules

- Minimum **3** competitions, maximum **5** (MVP catalog size)
- Season year between **2020** and current calendar year + 2
- League visibility is implicit: only members (or platform operators) can read
- Creation records a `league_audit_events` row with action `league_created`

## Database

Migration `e0f6a3b4c507_league_configuration.py` adds:

- `competitions` — seeded with API-Football provider IDs 39, 140, 135, 78, 61
- `leagues.season_year`, `leagues.state` (default `draft`)
- `league_competitions` — many-to-many join
- `league_audit_events` — configuration audit trail

Apply after pulling:

```powershell
.\infra\scripts\migrate.ps1
```

## Clients

Web and mobile expose a **Crea lega** view from the account panel (`CreateLeaguePanel`). Shared types and `MIN_LEAGUE_COMPETITIONS` live in `@fantappero/contracts`.

## Verification evidence (EP03-01)

```powershell
# Unit tests (validation rules)
cd backend; python -m pytest tests/unit/leagues -q

# Integration tests (create, audit, catalog) — requires Postgres
cd backend; python -m pytest tests/integration/leagues -q

# UI smoke (web)
pnpm test -- apps/web/src/App.test.tsx
```

Expected: draft league with owner role, audit event persisted, UI states for empty/error/success render.
