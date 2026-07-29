# Profile (EP02-02)

Private user preferences: display name, avatar, language, timezone, notification toggles, and privacy policy consent.

## API surface

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/auth/me` | Bearer | Current account + profile preferences |
| `GET` | `/users/me` | Bearer | Same as `/auth/me` (profile alias) |
| `PATCH` | `/users/me` | Bearer | Update profile fields (partial) |
| `POST` | `/users/me/avatar` | Bearer | Upload avatar (`multipart/form-data`, field `avatar`) |
| `GET` | `/users/{user_id}` | Bearer | Self-only profile (403 for other users) |

### Response shape (`UserProfileResponse`)

Includes account fields (`id`, `email`, `email_verified`, `created_at`) plus:

- `display_name` — optional string (max 80)
- `avatar_url` — data URL or `null`
- `language` — supported BCP-47 code (`it`, `en`, `es`, `fr`, `de`)
- `timezone` — IANA timezone (e.g. `Europe/Rome`)
- `notifications` — `{ email, push }` booleans
- `policy_consent_at`, `policy_version` — recorded when user accepts policy

### Update body (`PATCH /users/me`)

All fields optional:

```json
{
  "display_name": "Mario Rossi",
  "language": "en",
  "timezone": "Europe/London",
  "notifications_email": false,
  "notifications_push": true,
  "accept_policy": true,
  "policy_version": "2026-01",
  "clear_avatar": false
}
```

Policy consent requires `accept_policy: true` and `policy_version` matching `PROFILE_POLICY_VERSION`.

### Avatar upload

- Allowed types: JPEG, PNG, WebP
- Max size: `PROFILE_AVATAR_MAX_BYTES` (default 512 KB)
- Magic-byte validation; stored as a data URL in `avatar_url`

Errors use the same `{ "code", "message" }` envelope as auth (`profile_validation_error`, `invalid_avatar`, `forbidden`).

## Privacy

Profile endpoints are **self-only**. Requesting another user's profile returns `403 forbidden`. Notification preferences and policy consent are never exposed cross-user.

## Configuration

Add to root `.env` (see `.env.example`):

```bash
PROFILE_AVATAR_MAX_BYTES=524288
PROFILE_POLICY_VERSION=2026-01
```

Clients use `PROFILE_POLICY_VERSION` from `@fantappero/contracts` when recording consent.

Apply schema after pulling:

```bash
make migrate
```

## Verification evidence (EP02-02)

```bash
# Unit tests (validation rules)
cd backend && python -m pytest tests/unit/profiles -q

# Integration tests (update, avatar, IDOR) — requires Postgres
DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero \
  python -m pytest tests/integration/profile -q

# Web UI states (profile form)
cd apps/web && npm test

# Contracts + mobile client
cd packages/contracts && npm test
cd apps/mobile && npm test
```

## Client integration

- Web: `apps/web/src/profile/ProfilePanel.tsx`, API in `apps/web/src/api/auth.ts`
- Mobile: `apps/mobile/src/profile/ProfilePanel.tsx`, API in `apps/mobile/src/api/auth.ts`
- Shared types: `packages/contracts/src/index.ts`

See also [auth.md](./auth.md) for session requirements.
