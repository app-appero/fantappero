# Auth (EP02-01)

Email/password accounts with revocable bearer sessions, email verification, password reset, rate limiting, and protected routes.

## API surface

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | — | Create account; returns session token |
| `POST` | `/auth/login` | — | Sign in with email/password |
| `POST` | `/auth/logout` | Bearer | Revoke current session |
| `GET` | `/auth/me` | Bearer | Current user profile (account + preferences) |
| `POST` | `/auth/verify-email` | — | Consume one-time verification token |
| `POST` | `/auth/request-password-reset` | — | Queue reset email (always 200) |
| `POST` | `/auth/reset-password` | — | Set new password; revokes all sessions |
| `GET` | `/users/{user_id}` | Bearer | Self-only profile (IDOR guard) |

Profile update, avatar upload, and preference fields: see [profile.md](./profile.md).

League configuration and resource policies: see [leagues.md](./leagues.md) and [authorization.md](./authorization.md).

Errors return `{ "code": "...", "message": "..." }` with appropriate HTTP status.

## Sessions and tokens

- **Session tokens** are opaque bearer values; only SHA-256 hashes are stored in `auth_sessions`.
- **Logout** sets `revoked_at`; revoked or expired sessions return `401 invalid_session`.
- **Email verification / password reset** use single-use rows in `auth_tokens` (`used_at` prevents reuse).
- **Password reset** revokes all active sessions for the account.

## Rate limiting

Login, register, and password-reset requests are limited per client IP (+ email where applicable). Defaults:

- `AUTH_RATE_LIMIT_MAX_ATTEMPTS=5`
- `AUTH_RATE_LIMIT_WINDOW_SECONDS=900`

Uses Redis when `REDIS_URL` is configured; falls back to in-memory counters in test/local fallback.

## Configuration

**Backend** — add to root `.env` (see `.env.example`):

```bash
AUTH_SESSION_TTL_SECONDS=604800
AUTH_ONE_TIME_TOKEN_TTL_SECONDS=3600
AUTH_RATE_LIMIT_MAX_ATTEMPTS=5
AUTH_RATE_LIMIT_WINDOW_SECONDS=900
AUTH_PUBLIC_BASE_URL=http://127.0.0.1:5173
# AUTH_SECRET_KEY=   # reserved for future signed tokens
```

**Clients** — Vite/Expo do not read the root `.env`. With Compose, the `web` service sets `VITE_API_BASE_URL` automatically. For **host-run** web/mobile, copy per-app templates:

```bash
cp apps/web/.env.example apps/web/.env
cp apps/mobile/.env.example apps/mobile/.env
```

Required values: `VITE_API_BASE_URL` (web), `EXPO_PUBLIC_API_BASE_URL` (mobile), both pointing at the API (default `http://127.0.0.1:8000`). Restart dev servers after creating or changing these files.

The API enables CORS for local browser origins by default (`API_CORS_ORIGINS` in root `.env` / `infra/local/.env.example`). Without it, register/login from the web app fail with `OPTIONS … 405`.

Apply schema:

```bash
make migrate
```

## Email delivery (development)

Verification and reset links are logged by the API (`auth.email` logger) until SMTP is wired. Check API logs after register / request-password-reset.

## Verification evidence (EP02-01)

```bash
# Unit tests (validation, hashing, tokens)
cd backend && python -m pytest tests/unit/auth -q

# Integration tests (flows, revocation, IDOR, rate limit) — requires Postgres
DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero \
  python -m pytest tests/integration/auth -q

# Web/mobile UI + contracts
pnpm --filter @fantappero/web test
pnpm --filter @fantappero/mobile test
pnpm --filter @fantappero/contracts test
```

## Clients

- Web: `apps/web/src/auth/AuthApp.tsx` — login, register, forgot/reset password, verify email, account panel with loading/empty/error/success states.
- Mobile: `apps/mobile/src/auth/AuthScreen.tsx` — login/register/account with the same async states.
- Shared types: `packages/contracts/src/index.ts`.
