# Registrazione del pilota: solo Google

Per il pilota la registrazione con email e password è **spenta**: si crea un account solo con
«Continua con Google». Il codice della registrazione con email resta (spento, non cancellato).

## Interruttore
| Variabile | Dove | Default | Pilota |
| --- | --- | --- | --- |
| `AUTH_EMAIL_REGISTRATION_ENABLED` | servizio **api** | `true` | **`false`** |

Per riaccenderla basta rimettere `true` (o togliere la variabile) e rifare il deploy dell'API:
non serve ricompilare l'app, perché web e app leggono lo stato dal server (`GET /auth/options`,
pubblico, risponde `{"emailRegistrationEnabled": false}`).

## Cosa cambia
- `POST /auth/register` risponde **403** con codice `email_registration_disabled` e **non crea
  nessun account né invia email di verifica**.
- Le schermate di registrazione (web e app) mostrano solo «Continua con Google» e la frase
  «In questa fase la registrazione è solo con Google». Mentre il server non ha ancora risposto non
  compare il modulo con email; se la richiesta fallisce si torna al modulo e decide il server.
- Con Google l'account nasce **già verificato**: nessuna email di verifica e nessun reset password.

## Cosa non cambia
- Chi ha già un account con password continua ad **accedere** con email e password (per esempio gli
  operatori). «Password dimenticata» resta, ma richiede che l'invio email funzioni.
- L'**email dal pannello operatore** resta disponibile (oggi soggetta al blocco dell'invio).
- Le notifiche di gioco restano in app e push; le email di routine restano spente
  (`NOTIFICATIONS_ROUTINE_EMAIL_ENABLED=false`, vedi `email_notifications.md`).

## Notifiche push: per chi funzionano
Le push passano dall'Expo Push API e arrivano **solo all'app mobile** con le notifiche attive nel
profilo (`notifications_push`, acceso di default; `NOTIFICATIONS_PUSH_ENABLED=true`, default).
- **Android (APK)**: in app + push.
- **Web**: solo in app (il sito non ha notifiche push del browser).
- **iPhone**: oggi solo web (nessuna build iOS nel pilota), quindi solo in app.
Un tester che non apre mai l'app o che ha negato il permesso alle notifiche non riceve la push.
