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
