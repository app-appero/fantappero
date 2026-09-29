# Auth API (EP02-01)

Endpoint sotto `/auth` per registrazione, login, verifica email e reset password.

## Flussi

| Flusso | Endpoint | Note |
| --- | --- | --- |
| Registrazione | `POST /auth/register` | Crea utente non verificato; invia email |
| Verifica email | `POST /auth/verify-email` | Body `{ "token": "..." }` |
| Reinvio verifica | `POST /auth/resend-verification` | Rate-limited |
| Login | `POST /auth/login` | Richiede email verificata |
| Login con Google | `POST /auth/google` | Body `{ "idToken": "..." }`; crea l'account o collega automaticamente un account esistente con la stessa email verificata |
| Refresh | `POST /auth/refresh` | Ruota refresh token |
| Logout | `POST /auth/logout` | Revoca refresh corrente |
| Sessione | `GET /auth/me` | Bearer access token |
| Password dimenticata | `POST /auth/forgot-password` | Risposta generica anti-enumeration |
| Reset password | `POST /auth/reset-password` | Invalida refresh esistenti |

## Token

- **Access token**: JWT HS256, scadenza configurabile (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 15).
- **Refresh token**: opaco, persistito in `refresh_sessions`, revocabile al logout.
- **Token email/reset**: monouso in `auth_tokens`, consegnati via SMTP.

## Login con Google

`POST /auth/google` verifica l'ID token ricevuto dal client (Google Identity Services su web,
`expo-auth-session` su mobile) contro le chiavi pubbliche JWKS di Google
(`auth/google_oauth.py`), controllando issuer, audience (`GOOGLE_OAUTH_CLIENT_IDS`) e scadenza.
Se l'email Google coincide con un account email/password esistente, l'account viene collegato
automaticamente (fidandosi del flag `email_verified` di Google) invece di crearne uno nuovo.
Un account creato solo via Google non ha `password_hash`: il login con password resta rifiutato
finché l'utente non imposta una password da "Password dimenticata".

## Email locale

Con Docker Compose, Mailpit cattura i messaggi su `http://localhost:8025` (SMTP `:1025`).
