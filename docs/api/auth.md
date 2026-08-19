# Auth API (EP02-01)

Endpoint sotto `/auth` per registrazione, login, verifica email e reset password.

## Flussi

| Flusso | Endpoint | Note |
| --- | --- | --- |
| Registrazione | `POST /auth/register` | Crea utente non verificato; invia email |
| Verifica email | `POST /auth/verify-email` | Body `{ "token": "..." }` |
| Reinvio verifica | `POST /auth/resend-verification` | Rate-limited |
| Login | `POST /auth/login` | Richiede email verificata |
| Refresh | `POST /auth/refresh` | Ruota refresh token |
| Logout | `POST /auth/logout` | Revoca refresh corrente |
| Sessione | `GET /auth/me` | Bearer access token |
| Password dimenticata | `POST /auth/forgot-password` | Risposta generica anti-enumeration |
| Reset password | `POST /auth/reset-password` | Invalida refresh esistenti |

## Token

- **Access token**: JWT HS256, scadenza configurabile (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 15).
- **Refresh token**: opaco, persistito in `refresh_sessions`, revocabile al logout.
- **Token email/reset**: monouso in `auth_tokens`, consegnati via SMTP.

## Email locale

Con Docker Compose, Mailpit cattura i messaggi su `http://localhost:8025` (SMTP `:1025`).
