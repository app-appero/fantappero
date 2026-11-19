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
pubblico, risponde `{"emailRegistrationEnabled": false, "emailVerificationRequired": …}`).

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

## Alternativa con email (registrazione con email accesa, web)
Decisa il 19/11 per dev e pilota, per i tester senza un account Google. Con
`AUTH_EMAIL_REGISTRATION_ENABLED=true` la pagina di accesso resta quella del pilota, con Google per
primo; sotto ci sono «oppure» e il tasto secondario «Continua con email». Il tasto apre, nella stessa
scheda, un pannello con due schede:
- **Accedi**: email, password, «Accedi» e «Password dimenticata?»;
- **Registrati**: nome, email, password e «Crea account»;
- la riga sull'informativa privacy («Accedendo…» / «Registrandoti…») e «Chiudi» per richiuderlo.

`/accedi/registrati` apre la pagina con il pannello già aperto su «Registrati»; senza Google
configurato (in locale) il pannello è aperto da subito. Con la registrazione con email spenta la
pagina resta quella solo Google descritta sopra (e `/accedi?accesso=email` il modulo di sempre).

Con la verifica email spenta (vedi sotto) dopo «Crea account» si entra subito, con le stesse
credenziali; con la verifica accesa compare «Controlla la tua email» come prima.

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

## Verifica email facoltativa (dev e pilota)
| Variabile | Dove | Default | Dev | Pilota |
| --- | --- | --- | --- | --- |
| `AUTH_EMAIL_VERIFICATION_REQUIRED` | servizio **api** | `true` | `false` | **`false`** (decisione del 19/11) |

Con `false` i nuovi account con email e password nascono già verificati (nessuna email inviata)
e un account non ancora verificato viene verificato al primo accesso. `POST /auth/register`
risponde «Registrazione completata: ora puoi accedere.» (stesso testo se l'indirizzo era già
registrato) e il web entra subito dopo la registrazione (`emailVerificationRequired: false` in
`GET /auth/options`). Il valore predefinito resta `true`: senza la variabile nulla cambia.
Attenzione: senza verifica nessuno controlla che l'indirizzo sia davvero di chi si registra.

## Richiesta di accesso per chi non è ancora tester (solo web)
Con la **modalità test** accesa, chi entra con Google e non è tester non crea nessun account: il web
gli mostra un modulo (nome, cognome, **telefono facoltativo**, motivo facoltativo, consenso).
Nome e cognome sono già compilati con quelli dell'account Google (modificabili).
- Il **telefono** è facoltativo e serve solo per aggiungere la persona alla **chat WhatsApp dei
  tester**, per avere info più direttamente: lo dice il modulo ed è l'unico uso previsto. Senza
  numero la richiesta si invia lo stesso.
- Le richieste stanno nella tabella `tester_access_requests` (non sono utenti). Una richiesta per
  indirizzo email, verificato da Google. Il modulo si invia con un gettone firmato valido 30 minuti.
- **Pannello operatore → Utenti → scheda «Richieste tester»**: elenco con quello che hanno scritto;
  Approva (anche più richieste insieme) aggiunge l'email alla lista tester, Rifiuta no.
  Chi approvi non riceve email: al successivo accesso con Google entra da solo. Scrivigli tu, e
  aggiungilo al gruppo WhatsApp.
- Gli operatori ricevono una notifica in app e push a ogni nuova richiesta.
- Le richieste **rifiutate si cancellano dopo 30 giorni** (poi la persona può chiedere di nuovo).
- Con la modalità test **spenta** il modulo non compare e l'invio è rifiutato.
- **Accesso con email e password**: chi non è tester riceve la stessa risposta e lo stesso modulo
  (stesso gettone, stesso invio), ma solo **dopo** il controllo della password: con una password
  sbagliata resta l'errore generico «Email o password non validi.». Il nome è precompilato con
  quello del profilo. A differenza di Google, l'account esiste già; entra quando la richiesta è
  approvata.
- **App (APK)**: «Continua con Google» apre già la pagina web di accesso nel browser del telefono;
  se chi accede non è tester, lo stesso modulo compare lì (stesso testo, stesso invio). Dopo
  l'invio torna all'app e al successivo accesso vale la stessa risposta della richiesta.
- **Gestione**: la scheda «Richieste tester» c'è sia sul web (Utenti) sia nell'app (Amministrazione →
  Utenti). Nell'app il telefono si tocca per aprire WhatsApp.

## Eliminazione account e accesso tester

Quando un account viene eliminato (dall'operatore o dall'utente stesso) la sua email viene tolta
anche dalla lista dei tester e la sua richiesta di accesso viene cancellata. Lo stesso accade se
l'operatore toglie un tester dalla lista. Chi si registra di nuovo non entra come tester: deve
rifare la richiesta.

## Limiti per IP dietro Railway (`FORWARDED_ALLOW_IPS`)

Su Railway il server vede come mittente gli indirizzi interni dei proxy (`100.64.0.x`, una
quindicina, diversi a ogni richiesta), non quello di chi si collega. Senza correzione i limiti per
IP di login (5 al minuto) e registrazione (10 all'ora) si spargono su quei contatori e non
scattano mai, e utenti diversi condividono gli stessi contatori.

Impostare sul servizio `api` di ogni ambiente `FORWARDED_ALLOW_IPS=100.64.0.0/10`: Uvicorn si fida
dell'intestazione `X-Forwarded-For` solo se la richiesta arriva da quella rete, quindi un utente non
può scegliersi l'IP. Verifica: 30 login sbagliati con email diverse dallo stesso IP devono dare
risposte 429 dopo i primi 5. Il blocco progressivo per singolo account funziona già senza questa
impostazione. Impostata su dev il 15/11; da impostare su pilota e produzione.
