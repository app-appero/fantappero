# Accesso del pilota: solo Google

Per il pilota la registrazione **e il modulo di accesso** con email e password sono **spenti**:
si entra solo con «Continua con Google». Il codice di registrazione e login con email resta
(non cancellato).

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
- Le schermate di **registrazione** e di **accesso** (web e app) mostrano solo «Continua con
  Google», **senza altri testi né link**: con Google si accede e ci si registra nello stesso gesto,
  quindi spariscono email, password, «Password dimenticata?», «Registrati» e «Hai già un account?».
  Mentre il server non ha ancora risposto non compare il modulo con email; se la richiesta fallisce
  si torna al modulo e decide il server.
- **Account con password** (per esempio un operatore): sul web si apre
  **`/accedi?accesso=email`**, che mostra il modulo. L'app non ha questo ingresso: lì si usa Google.
  Chi entra con Google con lo stesso indirizzo email dell'account esistente accede allo stesso account.
- Con Google l'account nasce **già verificato**: nessuna email di verifica e nessun reset password.

## Cosa non cambia
- Il **server** accetta ancora il login con email e password (`POST /auth/login`): l'interruttore
  nasconde il modulo, non blocca l'API. Gli account esistenti non vengono toccati.
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

## Verifica email facoltativa (solo dev)
| Variabile | Dove | Default | Dev | Pilota |
| --- | --- | --- | --- | --- |
| `AUTH_EMAIL_VERIFICATION_REQUIRED` | servizio **api** | `true` | `false` | **`true`** (non toccare) |

Con `false` i nuovi account con email e password nascono già verificati (nessuna email inviata)
e un account non ancora verificato viene verificato al primo accesso. Serve ai test automatici su
dev con indirizzi inventati. Il valore predefinito resta `true`: senza la variabile nulla cambia.
