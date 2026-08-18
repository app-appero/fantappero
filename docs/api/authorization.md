# Autorizzazioni (EP02-03)

Policy lato server per utenti, amministratori di lega e operatori piattaforma.

## Ruoli

| Livello | Valore DB / API | Descrizione |
| --- | --- | --- |
| Piattaforma | `users.platform_role`: `user` → `globalRole: member` | Utente registrato |
| Piattaforma | `users.platform_role`: `operator` → `globalRole: global_operator` | Staff piattaforma |
| Lega | `league_memberships.role`: `owner` → `league_admin` | Amministratore lega |
| Lega | `league_memberships.role`: `member` → `member` | Partecipante lega |

La matrice permessi Python (`authorization/permissions.py`) rispecchia `@fantappero/contracts` (`auth.ts`).

## Permessi

| Permesso | Membro lega | Admin lega | Operatore |
| --- | --- | --- | --- |
| `league:view` | sì | sì | sì |
| `league:admin` | no | sì | sì |
| `roster:view` / `roster:edit` | sì | sì | sì |
| `market:view` | sì | sì | sì |
| `market:manage` | no | sì | sì |
| `matchday:view` | sì | sì | sì |
| `profile:view` | sì | sì | sì |
| `global:operate` | no | no | sì |

## Confini tenant (lega)

Ogni richiesta con `league_id` nel path verifica:

1. esistenza della lega;
2. appartenenza dell’utente (`league_memberships`) **oppure** ruolo operatore piattaforma;
3. permessi effettivi sulla risorsa.

Risposte di errore coerenti:

| Codice HTTP | `code` | Caso |
| --- | --- | --- |
| 403 | `league_access_denied` | Lega esistente, utente non membro |
| 403 | `forbidden` | Membro senza permesso richiesto |
| 404 | `league_not_found` | Lega inesistente |
| 401 | `invalid_credentials` | Token assente o non valido |

## Endpoint con policy

| Endpoint | Policy |
| --- | --- |
| `GET /profile/me` e mutazioni profilo | `profile:view` |
| `GET /leagues/mine` | `league:view` |
| `GET /leagues/competitions` | `league:view` |
| `POST /leagues` | `league:view` |
| `GET /leagues/{league_id}` | `league:view` + membership |
| `GET /leagues/{league_id}/amministrazione` | `league:admin` + membership |
| `GET/POST/DELETE /leagues/{league_id}/amministrazione/partecipanti/*` | `league:admin` + membership |
| `GET/POST /sports-data/quality/*` | `global:operate` (solo operatore) |
| `GET /admin/overview` | `global:operate` (solo operatore) |
| `GET /admin/users` | `global:operate` (solo operatore) |
| `POST /admin/users/{user_id}/promote` | `global:operate` (solo operatore) |
| `POST /admin/users/{user_id}/revoke` | `global:operate` (solo operatore) |
| `GET /admin/leagues` | `global:operate` (solo operatore) |
| `GET /admin/listone` | `global:operate` (solo operatore) |
| `POST /admin/listone/aggiorna` | `global:operate` (solo operatore) |
| `GET /admin/listone/aggiorna/{job_id}` | `global:operate` (solo operatore) |

`GET /auth/me` richiede solo autenticazione (JWT valido).

## Pannello operatore `/admin` (EP11-04a)

L'accesso a `/admin/*` (frontend e backend) è determinato **solo dal ruolo**, mai da un query param o dall'ambiente: `users.platform_role=operator` in ogni ambiente (development/staging/production usano le stesse route, dati diversi per DB). Non esiste self-promotion né bootstrap via UI: il primo operator si crea con un comando one-shot documentato in [`docs/operations/admin_operator_bootstrap.md`](../operations/admin_operator_bootstrap.md); operatori successivi si promuovono/revocano da `/admin/utenti`, solo da un operator già autenticato, con conferma esplicita. Il gate frontend (`RequireGlobalOperator` + `can(["global:operate"])`) è solo UX — l'autorizzazione reale è `require_permissions(Permission.GLOBAL_OPERATE)` su ciascun endpoint sopra.

## Dipendenze FastAPI

```python
from authorization.dependencies import require_permissions, require_league_permissions
from database.enums import Permission

# Profilo / risorse globali
current_user = Depends(require_permissions(Permission.PROFILE_VIEW))

# Risorsa lega
league_access = Depends(require_league_permissions(Permission.LEAGUE_VIEW))
```

## Metriche

Contatore `authorization_denied_total` con label `reason` (`forbidden`, `league_access_denied`, `league_not_found`).

## Test

```powershell
# Unit (offline)
cd backend && python -m pytest tests/unit/authorization -ra

# Integrazione (Postgres + Redis via Docker Compose)
docker compose --env-file infra/local/.env.example up -d postgres redis mailpit
$env:DATABASE_URL = "postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:JWT_SECRET_KEY = "fantappero_local_jwt_dev_only_change_in_production"
$env:FANTAPPERO_ENV = "test"
cd backend && python -m pytest tests/integration/authorization -ra
```
