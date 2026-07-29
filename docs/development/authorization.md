# Authorization (EP02-03)

Resource policies for user profiles and leagues, distinguishing **platform users**, **league administrators** (`owner`), and **platform operators**.

## Actor types

| Actor | Scope | Stored as |
| --- | --- | --- |
| Platform user | Account + league memberships | `users.platform_role = user` (default) |
| League administrator | Single league | `league_memberships.role = owner` |
| Platform operator | Cross-tenant support | `users.platform_role = operator` |

League members use `league_memberships.role = member`.

## Policy matrix

| Resource | Action | Platform user | League member | League owner | Platform operator |
| --- | --- | --- | --- | --- | --- |
| User profile | Read | Self only | Self only | Self only | Any user |
| User profile | Update / avatar | Self only | Self only | Self only | Self only |
| League | Create | Verified email | Verified email | Verified email | Verified email |
| League | Read | — | Member of league | Member of league | Any league |
| League | Update (name) | — | Forbidden | Owner of league | Any league |

All denials return `{ "code": "forbidden", "message": "..." }` with HTTP **403**, except missing resources which return **404** `not_found`.

## API surface

| Method | Path | Policy |
| --- | --- | --- |
| `GET` | `/users/{user_id}` | Self or platform operator |
| `PATCH` | `/users/me` | Self only |
| `POST` | `/users/me/avatar` | Self only |
| `POST` | `/leagues` | Verified email |
| `GET` | `/leagues/competitions` | Authenticated user |
| `GET` | `/leagues/{league_id}` | League member or platform operator |
| `PATCH` | `/leagues/{league_id}` | League owner or platform operator |

Auth/session endpoints remain documented in [auth.md](./auth.md). Profile fields in [profile.md](./profile.md).

## Module layout

```
backend/src/authorization/
  policies.py    # Pure rules (unit-tested)
  service.py     # DB lookups + policy enforcement
backend/src/leagues/
  service.py     # League domain operations
  schemas.py
  validation.py  # Season and competition rules (EP03-01)
  catalog.py     # MVP competition provider IDs
backend/src/app/
  deps_authorization.py
  deps_league.py
```

Domain services (`ProfileService`, `LeagueService`) delegate authorization to `AuthorizationService` rather than inlining checks.

## Configuration

Platform operators are assigned in the database (`users.platform_role = 'operator'`). No env flag — bootstrap via migration/seed or direct SQL in non-production environments.

Apply schema (includes `platform_role` column):

```bash
make migrate
```

## Verification evidence (EP02-03)

```bash
# Unit tests — policy rules
cd backend && python -m pytest tests/unit/authorization -q

# Integration tests — authorization matrix, IDOR, cross-league
DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero \
  python -m pytest tests/integration/authorization -q

# Regression — auth + profile flows still pass
DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero \
  python -m pytest tests/integration/auth tests/integration/profile -q
```

## IDOR protection

- **Cross-user profiles**: non-operators receive `403 forbidden` when requesting another user's profile.
- **Cross-league access**: non-members receive `403 forbidden`; unknown league IDs return `404 not_found`.
- **League admin actions**: members cannot rename leagues; only owners (or operators) can `PATCH /leagues/{id}`.

Future league-scoped resources should join through `league_memberships` in the same query rather than fetch-then-check.
