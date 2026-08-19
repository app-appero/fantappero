# Profile API (EP02-02)

Endpoint sotto `/profile` per preferenze dell'utente autenticato. I dati sono visibili e modificabili **solo** dal titolare dell'account.

## Endpoint

| Metodo | Percorso | Descrizione |
| --- | --- | --- |
| `GET` | `/profile/me` | Profilo completo (email, nome, avatar, preferenze, consenso) |
| `PATCH` | `/profile/me` | Aggiorna nome, lingua, fuso, notifiche |
| `POST` | `/profile/me/avatar` | Upload avatar (`multipart/form-data`, campo `file`) |
| `DELETE` | `/profile/me/avatar` | Rimuove avatar |
| `POST` | `/profile/me/policy-consent` | Registra consenso policy |
| `GET` | `/profile/me/export` | Esportazione dati account (EP02-04) |
| `POST` | `/profile/me/delete` | Eliminazione account anonimizzata (EP02-04) |

Dettaglio export/cancellazione: [`privacy.md`](privacy.md).

Tutti gli endpoint richiedono `Authorization: Bearer <access_token>`.

## Validazioni

| Campo | Regole |
| --- | --- |
| Nome visualizzato | 1–80 caratteri, trim |
| Lingua | BCP47; attualmente supportata: `it` |
| Fuso orario | IANA (`Europe/Rome`, …) |
| Avatar | JPEG/PNG/WebP, max 2 MB (configurabile `AVATAR_MAX_BYTES`) |
| Policy | `policyVersion` deve coincidere con `PROFILE_POLICY_VERSION` |

## Avatar

I file sono salvati in `AVATAR_STORAGE_PATH` (default `/data/avatars`) e serviti su `/media/avatars/{user_id}.{ext}`.

In Docker Compose è montato il volume `fantappero_avatar_data` sul servizio `api`.

## Variabili ambiente

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `AVATAR_STORAGE_PATH` | `/data/avatars` | Directory locale avatar |
| `AVATAR_MAX_BYTES` | `2097152` | Dimensione massima upload |
| `PROFILE_POLICY_VERSION` | `2026-01` | Versione policy corrente |

## Metriche

- `profile_update_total`
- `profile_avatar_upload_total`
- `profile_avatar_remove_total`
- `profile_policy_consent_total`
