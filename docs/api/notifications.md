# Notifiche in-app (EP09-01 … EP09-04 / EP13-P07)

| Metadato | Valore |
| --- | --- |
| Modulo | `backend/src/notifications/` |
| Card | EP09-01 (infrastruttura), EP09-02/03/04 (produttori), EP13-P07 (inviti e badge) |

> Questo documento è stato creato da EP13-P07: le card lo citavano come
> `docs/api/notifications.md`, ma il file non esisteva.

## Endpoint

| Metodo | Path | Permesso | Descrizione |
| --- | --- | --- | --- |
| `GET` | `/notifications` | autenticato | Elenco paginato con `unreadCount`; filtri `category`, `unreadOnly` |
| `POST` | `/notifications/{id}/read` | autenticato | Segna una notifica come letta |
| `POST` | `/notifications/read-all` | autenticato | Segna tutte come lette |
| `GET` | `/notifications/preferences` | autenticato | Preferenze per categoria |
| `PUT` | `/notifications/preferences` | autenticato | Aggiorna una preferenza |
| `GET` | `/leagues/inviti-ricevuti/conteggio` | `league:view` | Inviti nominativi pendenti (EP13-P07) |

## Categorie e template

Categorie: `sistema`, `formazione`, `mercato`, `risultati`.

Ogni notifica è resa da un template versionato `(template_key, version)` in
`notifications/templates.py`: il contenuto è ricalcolabile e una modifica di
copy non riscrive le notifiche già inviate.

| Template | Versione | Prodotto da |
| --- | --- | --- |
| `sistema.generico` | 1 | Uso generico |
| `sistema.invito_lega` | 1 | Invito nominativo (EP13-P07) |
| `formazione.scadenza_turno` | 1 | Reminder formazione (EP09-02) |
| `mercato.esito_busta` | 1 | Esito asta a buste (EP09-03) |

## Push (EP09-05)

Oltre all'in-app (sempre) e all'email (se `notifications_email` è attivo nel
profilo), ogni notifica creata prova anche a mandare una push Expo — stessa
logica dell'email: mai bloccante, mai propaga un errore, salta se l'utente
ha `notifications_push` spento nel profilo (il campo esisteva già ma prima
non era collegato a nulla) o se siamo in orario di silenzio.

| Metodo | Path | Permesso | Descrizione |
| --- | --- | --- | --- |
| `POST` | `/notifications/push-devices` | autenticato | Registra (o sposta su questo utente) il token Expo del dispositivo. Body: `{ "token": "ExponentPushToken[...]", "platform": "ios"\|"android" }` |
| `DELETE` | `/notifications/push-devices/{token}` | autenticato | Rimuove il token. No-op silenzioso se il token non è tuo. |

L'upsert è per `token`, non per `(user, token)`: un reinstall o un login con
un altro account sullo stesso dispositivo sposta il token al nuovo
proprietario invece di duplicarlo.

Quando Expo risponde `DeviceNotRegistered` per un token (disinstallazione),
il token viene marcato `revoked_at` e non viene più usato — non c'è ancora
un job di pulizia dei receipt differiti di Expo (il controllo è solo sul
ticket immediato), è un miglioramento futuro, non un bug noto.

### Variabili

| Variabile | Dove | Effetto |
| --- | --- | --- |
| `NOTIFICATIONS_PUSH_ENABLED` | API e worker | Interruttore globale, default acceso. |
| `EXPO_PUSH_BASE_URL` | opzionale | Default `https://exp.host/--/api/v2/push/send`. |
| `EXPO_PUSH_ACCESS_TOKEN` | opzionale | Token per la modalità "enhanced security" di Expo (stesso schema OAuth usato altrove nell'API). Mai nei log. |
| `EXPO_PUSH_TIMEOUT_SECONDS` | opzionale | Default 10. |

### Cosa manca lato mobile (non toccato da questo lavoro — `apps/mobile` resta di chi fa la grafica)

1. Installare `expo-notifications`.
2. Chiedere il permesso e ottenere l'Expo push token (`Notifications.getExpoPushTokenAsync()`).
3. Chiamare `POST /notifications/push-devices` con quel token dopo login/avvio app, e ad ogni refresh del token.
4. Chiamare `DELETE /notifications/push-devices/{token}` al logout (best-effort).
5. Il payload `data` della push contiene `notificationId`, `deepLink`, `category` — stessa forma dei deep link già gestiti da `notificationDestination.ts` per il tap sulle notifiche in-app, così il tap su una push può riusare la stessa mappatura.

### Cosa manca ancora, in generale (fuori da questo giro)

- Eventi live (`notifications/match_events.py`, categoria `risultati`): gol/rigore segnato e cartellino rosso durante la partita, infortunio/squalifica alla creazione della disponibilità. Solo a chi ha il giocatore in rosa; dedup per evento e utente; mai bloccante per la sync dati. Autogol e gialli ignorati.
- Nessun web push (service worker/VAPID) per `apps/web` — solo mobile per ora.
- Nessun realtime in-app (SSE/WebSocket): il centro notifiche web fa polling ogni 20s (`useNotificationCenter.ts`), il contatore si aggiorna al ritorno di focus, non istantaneamente.

## Sezione operatori (EP09-06)

Tutte sotto `/admin/notifications`, permesso `global:operate`. Tipi TS in `packages/contracts/src/notifications.ts`.

| Metodo | Path | Descrizione |
| --- | --- | --- |
| `GET` | `/recipients` | Utenti umani; filtri `search`, `leagueId`, `pushOnly`, `noPush`, `operatorsOnly`, `page`, `pageSize` (10). Include `counts` `{all, push, noPush, operators}` calcolati con ricerca e lega applicate. |
| `POST` | `/broadcasts` | Crea un avviso. Pubblico `all`, `leagues` o `users` (meno `excludeUserIds`): "seleziona tutti gli N" = `mode: "all"` con gli esclusi, senza elencare gli id. |
| `GET` | `/broadcasts` | Storico; `deliveredCount`/`readCount` si ricavano dalle notifiche create. `kind: "test"` compare con `status: "test"`. |
| `DELETE` | `/broadcasts/{id}` | Annulla un avviso ancora programmato (204, altrimenti 404). |
| `GET` / `POST` | `/test-samples` | Elenco `{items}` dei tipi di prova / invio (`sampleKeys`, `userIds`, default tutti a chi chiama) → `{createdCount, recipientCount}`. |

Errori 422 con `code`: `email_unavailable` (nessun provider email), `invalid_deep_link`, `invalid_kind`, `invalid_category`, `invalid_audience`, `empty_audience`.

`push: true` manda la push solo a chi ha preferenza accesa e un dispositivo registrato (`pushCount`); `inApp` c'è sempre. Un `scheduledAt` futuro salva l'avviso e lo invia il job `notifications.dispatch_broadcasts` (ogni 60 s, `NOTIFICATIONS_BROADCAST_DISPATCH_*`).

**`deepLink` validi** (quelli che l'app mobile sa aprire): `/` (home della lega), `/inviti`, `/formazione`, `/classifica`, `/turni`, `/rosa`, `/asta`, `/svincolati`, `/scambi`, `/mercato`, `/profilo` (anche con sottopercorso o query). Altro: 422.

## Idempotenza

`create_notification` è idempotente su `dedup_key`: se esiste già una riga con
la stessa chiave, viene restituita quella invece di crearne una nuova. Un
retry o due richieste concorrenti non generano duplicati. Se l'utente ha
disattivato la categoria nelle preferenze, non viene creata alcuna riga.

## Invito nominativo e badge inviti (EP13-P07)

### Notifica

Alla creazione di un invito nominativo il destinatario riceve una notifica
`sistema` con template `sistema.invito_lega` v1 e deep link `/inviti`.
Il link porta agli **inviti**, non alla lega: finché l'invito non è accettato
il destinatario non ha accesso alla lega.

`dedup_key = named_invite:<invite_id>`. Un fantallenatore IA non riceve nulla:
entra automaticamente e non ha nulla da decidere.

### Due conteggi distinti

| Conteggio | Cosa misura | Dove |
| --- | --- | --- |
| Notifiche non lette | Notifiche mai aperte, di qualsiasi categoria | Campanella (web) / schermata Notifiche (mobile) |
| `pendingInviteCount` | Inviti nominativi **ancora da decidere** | Badge rosso sulla voce «Inviti ricevuti» |

`GET /leagues/inviti-ricevuti/conteggio` conta solo gli inviti `pending` **non
scaduti**, riconciliando prima quelli scaduti.

I due valori **possono differire, ed è corretto**: leggere la notifica azzera
l'unread ma **non chiude l'invito**, che resta pendente finché non viene
accettato, rifiutato, revocato o scaduto. Un test di integrazione copre
esattamente questa distinzione.

### Aggiornamento del badge

Nessun polling: il conteggio cambia raramente. Si aggiorna quando la superficie
torna attiva — `focus` della finestra sul web, apertura del menu su mobile — e
dopo ogni azione su un invito. Coerente con la sospensione a schermata inattiva
introdotta in EP13-P04.

Il badge mostra `99+` oltre 99 e sparisce a zero; l'etichetta accessibile
riporta il conteggio esteso. Il badge è **accessorio**: se la chiamata
fallisce si degrada a zero senza rompere la navigazione.

### Parità mobile

Prima di EP13-P07 `apps/mobile` **non aveva alcuna superficie notifiche**:
nessun client API, nessun centro, nessuna campanella. La card ha aggiunto
client API, schermata `Notifications` (elenco, segna come letta, segna tutte
lette, apertura deep link) ed entry point nel drawer, oltre al badge sulla voce
inviti.

I deep link interni sono mappati alle route mobili equivalenti
(`/inviti` → `ReceivedInvites`); un deep link senza mappatura segna la notifica
come letta senza navigare, invece di fallire.

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/leagues/test_invite_notifications.py -ra'
```
