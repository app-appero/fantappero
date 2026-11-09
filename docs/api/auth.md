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
| Handoff Google mobile (avvio) | `POST /auth/google/handoff` | Solo dalla pagina web `/accedi/google-app`; stesso body/validazione di `/auth/google`, risponde con `{ "code": "..." }` invece della sessione — vedi sotto |
| Handoff Google mobile (ritiro) | `POST /auth/google/handoff/claim` | Solo dall'app; body `{ "code": "..." }`; restituisce la sessione creata da `handoff`, consumando il codice una sola volta |
| Refresh | `POST /auth/refresh` | Ruota refresh token |
| Logout | `POST /auth/logout` | Revoca refresh corrente |
| Sessione | `GET /auth/me` | Bearer access token |
| Password dimenticata | `POST /auth/forgot-password` | Risposta generica anti-enumeration |
| Reset password | `POST /auth/reset-password` | Invalida refresh esistenti |

## Token

- **Access token**: JWT HS256, scadenza configurabile (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 720 minuti / 12 ore).
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

### Handoff Google su mobile

Un browser in-app blocca la finestra di login di Google, quindi l'app apre il bottone Google
nel browser di sistema, sulla pagina web `/accedi/google-app`, e si aspetta di essere
richiamata via deep link (`fantappero://...`) con l'esito. Quel link, non essendo un Android
App Link / iOS Universal Link con dominio verificato, può in teoria essere intercettato da
un'altra app registrata sullo stesso schema — per questo non porta più l'ID token di Google né
una sessione, ma solo un codice monouso:

1. La pagina web ottiene l'ID token da Google e lo scambia subito, lato browser, con
   `POST /auth/google/handoff` (stessa validazione di `/auth/google`): crea la sessione reale e
   riceve indietro solo `{ "code": "..." }` — un codice casuale a 256 bit
   (`secrets.token_urlsafe(32)`), mai l'ID token né i token di sessione.
2. La pagina redireziona a `fantappero://...?code=...`.
3. L'app legge `code` dal deep link e lo scambia con `POST /auth/google/handoff/claim`, che lo
   consuma atomicamente (Redis `GETDEL`, TTL 90s, un solo utilizzo possibile) e restituisce la
   sessione già creata al passo 1.

Implementazione: `auth/mobile_handoff.py` (`MobileHandoffStore`). Vedi
`docs/operations/beta_readiness/ep12-04_security_review.md`, finding #27, per il perché.

## Email locale

Con Docker Compose, Mailpit cattura i messaggi su `http://localhost:8025` (SMTP `:1025`).
