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
| `GET` | `/notifications/preferences` | autenticato | Preferenze per categoria **ed eventi granulari** (TASK5, v. sotto) |
| `PUT` | `/notifications/preferences` | autenticato | Aggiorna una preferenza di categoria **o** di evento granulare (TASK5) |
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

## Email (EP09-05) — spenta di default per le notifiche di routine (Task 6b)

Oltre all'in-app (sempre), ogni notifica creata prova anche a mandare
un'email a chi ha `notifications_email` attivo nel profilo — **ma solo se
`NOTIFICATIONS_ROUTINE_EMAIL_ENABLED=true`** (default `false`). Il dettaglio
di quali trigger generavano email e perché sono stati spenti è in
[`docs/operations/email_notifications.md`](../operations/email_notifications.md).
Non riguarda le email di autenticazione (`docs/api/auth.md`), che usano un
percorso separato, né l'email operatore descritta più sotto.

## Deep link allo scontro H2H specifico (TASK4)

I template di evento calciatore (`risultati.gol` v2, `risultati.assist`,
`risultati.ammonizione`, `risultati.espulsione` v2, `risultati.sostituzione`)
non puntano più al generico `/turni`: `notifications/match_events.py`
(`_notify_owners`) risolve, **per ogni destinatario**, lo scontro H2H preciso
in cui il suo fantasy team gioca nella giornata della fixture che ha
generato l'evento (`notifications/matchup_links.py`,
`resolve_matchup_deep_link`). Due destinatari della stessa fixture, in leghe
o con avversari diversi, possono finire con deep link diversi.

Formato quando lo scontro si risolve:

```
/turni/scontro/{slotId}
```

`slotId` è l'id di `LeagueCalendarSlot` (tabella `league_calendar_slots`,
una riga per scontro H2H). Non è una convenzione nuova: è lo stesso path
già registrato lato web (`apps/web/src/routes/routeConfig.ts`, route id
`matchday-matchup`) e usato da `MatchupDetailPage`; lato mobile `/turni*`
instrada già sulla tab Turni (`notificationDestination.ts`), quindi il
sottopercorso non rompe nulla anche prima che mobile implementi la
navigazione al singolo scontro.

Catena di risoluzione: `FantasyTeam(team_id)` → lega e `membership_id` →
`FantasyRoundFixture(league_id, fixture_id)` → `FantasyRound` → calendario
H2H della lega → `h2h_round_numbers_for_round` (giornate H2H ospitate dal
turno) → `LeagueCalendarSlot` (quella/e giornata/e, non bye, con
`home_membership_id`/`away_membership_id` == `membership_id` del
destinatario).

Se un pezzo della catena manca (lega senza calendario confermato, turno non
ancora mappato a una giornata H2H, squadra a riposo quella giornata...) si
torna al percorso generico: **mai un'eccezione**, una notifica non deve mai
fallire per colpa del deep link.

| Evento | Fallback senza scontro risolto |
| --- | --- |
| Gol, assist, ammonizione, espulsione, sostituzione | `/turni` |
| Infortunio, squalifica (solo se la disponibilità è legata a una fixture) | `/formazione` |

`risultati.infortunio`/`risultati.squalifica` nascono da
`PlayerAvailability`, non da un `MatchEvent`: quando la riga ha un
`fixture_id` si tenta comunque la risoluzione allo scontro di quella
giornata, altrimenti resta `/formazione` (il posto giusto da cui togliere
il giocatore, comunque).

## Preferenze granulari per evento (TASK5)

Oltre alla preferenza per categoria (`sistema`/`formazione`/`mercato`/
`risultati`, § sotto), esiste un secondo livello più fine — per singolo
evento, canali in-app e push indipendenti — definito in
`notifications/event_catalog.py` e persistito in
`notification_event_preferences` (`notifications/models.py`,
`NotificationEventPreference`). Un evento granulare può raggruppare più
`template_key` (es. `sistema.asta` copre tutte le fasi dell'asta live).

| Categoria evento | Evento | `template_key` coperti |
| --- | --- | --- |
| `calciatori` | `calciatori.gol` | `risultati.gol` |
| `calciatori` | `calciatori.assist` | `risultati.assist` |
| `calciatori` | `calciatori.ammonizione` | `risultati.ammonizione` |
| `calciatori` | `calciatori.espulsione` | `risultati.espulsione` |
| `calciatori` | `calciatori.sostituzione` | `risultati.sostituzione` |
| `calciatori` | `calciatori.infortunio` | `risultati.infortunio` |
| `calciatori` | `calciatori.squalifica` | `risultati.squalifica` |
| `sistema` | `sistema.scambi` | `mercato.scambio` |
| `sistema` | `sistema.asta` | `mercato.esito_busta`, `mercato.asta_live_iniziata`, `mercato.asta_live_aggiudicato`, `mercato.asta_live_sorpassato`, `mercato.asta_live_scambio_richiesto` |
| `sistema` | `sistema.formazione` | `formazione.scadenza_turno` |
| `sistema` | `sistema.turno_omologato` | `risultati.omologazione`, `risultati.correzione` |
| `sistema` | `sistema.avvisi_operatori` | `sistema.generico` (avvisi EP09-06) |

Un `template_key` non in questa tabella (es. `sistema.invito_lega`) resta
governato **solo** dalla preferenza di categoria: nessuna regressione per
gli eventi non ancora granularizzati.

Default: nessuna riga per (utente, evento) = **tutto attivo**, sia in-app
che push.

Gating all'invio (`notifications/service.py`, `create_notification`):
1. preferenza di categoria spenta → nessuna riga creata (comportamento
   preesistente, invariato);
2. altrimenti, se l'evento granulare ha `inAppEnabled: false` → nessuna riga
   creata (stesso effetto della categoria, ma per un solo evento);
3. altrimenti, se l'evento granulare ha `pushEnabled: false` → la riga
   in-app viene creata normalmente (compare in campanella), ma la push per
   *questa* notifica viene saltata.

Non esiste "solo push senza riga in-app": push ed email sono sempre state
agganciate all'esistenza della riga (vedi `email_dispatch.py`), ed è lo
stesso principio esteso qui — spegnere l'in-app di un evento spegne anche
la sua push.

### Contratto

`GET /notifications/preferences` → `200`:

```json
{
  "items": [
    { "category": "sistema", "inAppEnabled": true },
    { "category": "formazione", "inAppEnabled": true },
    { "category": "mercato", "inAppEnabled": true },
    { "category": "risultati", "inAppEnabled": true }
  ],
  "events": [
    {
      "eventKey": "calciatori.gol",
      "category": "calciatori",
      "label": "Gol",
      "inAppEnabled": true,
      "pushEnabled": true
    }
  ]
}
```

`items` resta per compatibilità (EP09-01); `events` è l'aggiunta di TASK5.

`PUT /notifications/preferences` accetta due forme nello stesso corpo,
selezionate da quale campo è presente (non entrambe insieme):

```json
// forma per categoria (compatibilità)
{ "category": "mercato", "inAppEnabled": false }

// forma granulare per evento — almeno uno dei due booleani, l'altro resta invariato
{ "eventKey": "calciatori.gol", "pushEnabled": false }
```

Risposta: stesso corpo di `GET /notifications/preferences` con lo stato
aggiornato. Errori `400` con `code`:

| `code` | Quando |
| --- | --- |
| `invalid_category` | `category` non è una categoria valida |
| `invalid_event_key` | `eventKey` non è un evento del catalogo |
| `invalid_preference_request` | `category` ed `eventKey` insieme, nessuno dei due, o `eventKey` senza alcun canale specificato |

## Push (EP09-05)

Oltre all'in-app (sempre) e all'email (se abilitata, vedi sopra), ogni
notifica creata prova anche a mandare una push Expo — stessa logica
dell'email: mai bloccante, mai propaga un errore, salta se l'utente ha
`notifications_push` spento nel profilo (il campo esisteva già ma prima non
era collegato a nulla) o se siamo in orario di silenzio.

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
| `NOTIFICATIONS_ROUTINE_EMAIL_ENABLED` | API e worker | Interruttore globale per l'email delle notifiche di routine, default **spento** (Task 6b). |
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

## Email operatore dal portale (Task 6c)

Tutte sotto `/admin/notifications`, permesso `global:operate` (stesso schema
dei broadcast sopra). L'operatore sceglie i destinatari con lo **stesso**
meccanismo dei broadcast (`GET /recipients` per sfogliarli, stesso oggetto
`audience` di `POST /broadcasts`: `all`, `leagues` o `users`, più
`excludeUserIds`), ma qui l'invio è un'email vera, non una notifica in-app.

| Metodo | Path | Request | Response |
| --- | --- | --- | --- |
| `POST` | `/admin/notifications/emails` | `{ "subject": string (1-120), "body": string (1-5000), "audience": { "mode": "all"\|"leagues"\|"users", "leagueIds": [uuid], "userIds": [uuid], "excludeUserIds": [uuid] } }` | `{ "id": uuid, "recipientCount": number }` |
| `GET` | `/admin/notifications/emails?page&pageSize` | — | `{ "items": [{ "id", "subject", "audienceLabel", "recipientCount", "sentAt", "createdByUserId" }], "total", "page", "pageSize" }` |

Errori 422 con `code`: `empty_message` (oggetto o testo vuoti dopo trim),
`empty_audience` (nessun destinatario per il pubblico scelto), più gli stessi
errori di validazione del pubblico già usati da `/broadcasts`
(`invalid_audience` se `mode` non è uno dei tre valori).

Dettagli di implementazione:

- Riusa `broadcast_service.resolve_audience`/`audience_label` — stessa
  risoluzione destinatari (solo utenti umani, non cancellati) dei broadcast.
- Non passa dal centro notifiche (`NotificationService`): nessuna riga in
  `notifications`, nessun `dedup_key`. Lo storico vive in una tabella
  dedicata, `operator_email_logs` (migrazione
  `backend/alembic/versions/98ca03d4135d_operator_email_logs.py`):
  `subject`, `body`, `audience`, `audience_label`, `recipient_count`,
  `created_by_user_id`, `sent_at`.
- Invia tramite lo stesso outbox email di sempre
  (`mail.tasks.send_message_task`, template `operator_email`); un fallimento
  di invio per un singolo destinatario non blocca gli altri né impedisce la
  registrazione nello storico (stesso "non deve mai bloccare" di
  `email_dispatch.py` / `push_dispatch.py`).
- **Non** passa dal flag `NOTIFICATIONS_ROUTINE_EMAIL_ENABLED` né dal toggle
  di profilo `notifications_email`: è un invio deciso da un operatore, non
  un trigger automatico. Motivazione completa in
  [`docs/operations/email_notifications.md`](../operations/email_notifications.md).

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
