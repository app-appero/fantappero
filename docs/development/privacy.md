# Privacy & data rights (EP02-04)

Export personal data and request account deletion while preserving competitive league history.

## API surface

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/users/me/export` | Bearer (self) | Download a JSON bundle of account, profile, league memberships, and session metadata |
| `POST` | `/users/me/delete` | Bearer (self) | Anonymize account, scrub PII, revoke sessions |

### Export response (`UserDataExportResponse`)

Structured JSON with:

- `format_version` — export schema version (`2026-01`)
- `exported_at` — UTC timestamp
- `account` — id, email, verification, created/deleted timestamps (no password hash)
- `profile` — preferences and policy consent (`avatar_present` boolean instead of raw avatar bytes)
- `league_memberships` — league id/name, role, join date, optional `historical_display_name`
- `sessions` — created/expiry/revoked metadata only (no tokens)
- `competitive_summary` — count of preserved memberships; flag for future competitive tables

### Delete body (`POST /users/me/delete`)

```json
{
  "password": "Secret123",
  "confirm": true
}
```

Both fields are required. Wrong password returns `400 invalid_delete_confirmation`.

### Anonymization rules

On deletion:

1. `users.deleted_at` set; email replaced with `deleted+<uuid>@anonymized.local`
2. Password hash rotated to a random unusable value; all sessions revoked
3. Profile PII scrubbed (`display_name` → `Deleted User`, avatar cleared, notifications off)
4. `league_memberships` **kept** with `historical_display_name` snapshot for roster integrity
5. `privacy_audit_events` row recorded (action only — no PII in audit payload)

Future competitive tables should follow the same pattern: retain structural FKs, anonymize display labels.

## Authorization

| Action | Policy |
| --- | --- |
| Data export | Self only — platform operators cannot export on behalf of users |
| Account delete | Self only — operators cannot delete user accounts |

Cross-user access returns `403 forbidden`. Routes are scoped to `/users/me/*`.

## Audit

`privacy_audit_events` stores:

- `user_id`, `actor_id` (always self for EP02-04)
- `action` — `data_export` or `account_delete`
- `correlation_id` — optional from `X-Correlation-ID` request header
- Standard `created_at` / `updated_at` timestamps

No export contents or emails are written to audit rows or structured logs.

## Module layout

```
backend/src/privacy/
  anonymization.py   # competitive-record rules and PII scrubbing
  service.py         # export + delete orchestration
  schemas.py         # API models
  validation.py      # delete confirmation rules
  errors.py
backend/src/database/models/privacy.py
backend/src/app/deps_privacy.py
```

Policies in `authorization/policies.py`: `can_export_own_data`, `can_delete_own_account`.

Apply schema after pulling:

```bash
make migrate
```

## Verification evidence (EP02-04)

```bash
# Unit tests (validation, anonymization, policies)
cd backend && python -m pytest tests/unit/privacy tests/unit/authorization/test_policies.py -q

# Integration tests (export, delete, audit, IDOR) — requires Postgres
DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero \
  python -m pytest tests/integration/privacy -q

# Web UI states (privacy panel)
cd apps/web && npm test

# Contracts
cd packages/contracts && npm test
```

## Client integration

- Web: `apps/web/src/profile/PrivacyPanel.tsx`, linked from account panel in `AuthApp.tsx`
- Mobile: `apps/mobile/src/profile/PrivacyPanel.tsx`, linked from `AuthScreen.tsx`
- API methods: `exportData`, `deleteAccount` on both auth clients
- Shared types: `packages/contracts/src/index.ts` (`UserDataExportResponse`, `DeleteAccountRequest`)

See also [profile.md](./profile.md) and [authorization.md](./authorization.md).
