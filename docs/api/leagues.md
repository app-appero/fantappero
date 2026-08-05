# Leghe (EP03-01, EP03-02, EP03-03, EP03-04, EP03-05)

Endpoint sotto `/leagues` per la configurazione iniziale di leghe private.

## Creazione lega

`POST /leagues` — richiede autenticazione e permesso `league:view`.

### Request

```json
{
  "name": "Lega degli amici",
  "seasonYear": 2026,
  "competitionIds": [
    "uuid-premier-league",
    "uuid-serie-a",
    "uuid-bundesliga"
  ]
}
```

### Regole

| Campo | Regola |
| --- | --- |
| `name` | Obbligatorio, trim, max 120 caratteri |
| `seasonYear` | Intero tra 2020 e anno corrente + 1 |
| `competitionIds` | Almeno 3 UUID distinti, tutti presenti nel catalogo MVP |

### Effetti atomici

1. Inserimento lega con `state = draft`
2. Membership del creatore con ruolo `owner` (API: `league_admin`)
3. Associazione campionati su `league_competitions`
4. Evento audit `league_created` in `league_audit_events`

### Response `201`

Restituisce `LeagueDetail` con `state: draft`, `viewerRole: league_admin` e l'elenco campionati selezionati.

### Errori

| HTTP | `code` | Caso |
| --- | --- | --- |
| 400 | `invalid_league_name` | Nome vuoto o troppo lungo |
| 400 | `invalid_season_year` | Stagione fuori range |
| 400 | `insufficient_competitions` | Meno di 3 campionati |
| 400 | `duplicate_competitions` | ID duplicati |
| 400 | `invalid_competition_ids` | ID inesistenti |
| 401 | `invalid_credentials` | Token assente o non valido |
| 422 | — | Payload Pydantic non valido |

## Catalogo campionati

`GET /leagues/competitions` — richiede `league:view`.

Restituisce i 5 campionati MVP seedati dalla migrazione `e0f6a3b4c507` (Premier League, La Liga, Serie A, Bundesliga, Ligue 1).

## Regolamento lega (amministrazione)

`GET /leagues/{league_id}/amministrazione` — richiede `league:admin` nel contesto della lega.

Response include il regolamento corrente:

```json
{
  "leagueId": "uuid-league",
  "message": "Configura il regolamento della lega prima dell'avvio.",
  "rules": {
    "presetName": "standard",
    "participantCount": 8,
    "participantMin": 4,
    "participantMax": 10,
    "roster": {
      "rosterSize": 35,
      "goalkeepers": 3,
      "defenders": 11,
      "midfielders": 11,
      "forwards": 10
    },
    "totalCredits": 1000,
    "options": {
      "allowTrades": true,
      "allowManualInvites": true
    }
  }
}
```

`PUT /leagues/{league_id}/amministrazione/regolamento` — richiede `league:admin`.

### Request

```json
{
  "presetName": "standard",
  "participantCount": 10,
  "roster": {
    "rosterSize": 35,
    "goalkeepers": 3,
    "defenders": 11,
    "midfielders": 11,
    "forwards": 10
  },
  "totalCredits": 1200,
  "options": {
    "allowTrades": true,
    "allowManualInvites": true
  }
}
```

### Regole server-side

| Campo | Regola |
| --- | --- |
| `presetName` | Solo `standard` |
| `participantCount` | Intero 4–10 |
| `roster` | Sempre 35 con distribuzione 3P–11D–11C–10A |
| `totalCredits` | Intero > 0 |

### Effetti atomici

1. Update su `league_rules` (vincoli DB + validazioni applicative)
2. Evento audit `league_rules_updated` su `league_audit_events` se ci sono modifiche
3. Nessun evento aggiuntivo per richieste idempotenti (stesso payload)

### Errori

| HTTP | `code` | Caso |
| --- | --- | --- |
| 400 | `invalid_rules_preset` | Preset diverso da Standard |
| 400 | `invalid_participant_count` | Partecipanti fuori range 4–10 |
| 400 | `invalid_roster_size` / `invalid_roster_distribution` | Rosa non conforme a 35 / 3P–11D–11C–10A |
| 400 | `invalid_total_credits` | Crediti <= 0 |
| 400 | `league_not_draft` | Lega non in bozza |
| 403 | `forbidden` | Utente non admin nella lega |
| 404 | `league_not_found` | Lega non esistente |

## Inviti e ingresso

Gli inviti sono multi-uso: restano validi fino alla scadenza, alla revoca esplicita o al
raggiungimento di `participantCount`. Token e codice vengono restituiti in chiaro solo
alla creazione; nel database sono conservati esclusivamente gli hash SHA-256.

### Gestione amministrativa

- `POST /leagues/{league_id}/amministrazione/inviti` richiede `league:admin` e accetta
  `{"expiresInDays": 7}`. Il valore ammesso è 1–30 giorni. La risposta `201` contiene
  `token`, `code` e `inviteUrl`.
- `GET /leagues/{league_id}/amministrazione/inviti` richiede `league:admin` e restituisce
  solo metadati e stato (`active`, `expired`, `revoked`), mai i segreti.
- `DELETE /leagues/{league_id}/amministrazione/inviti/{invite_id}` richiede
  `league:admin`. La revoca ripetuta è idempotente.

La generazione è consentita solo per una lega in bozza con `allowManualInvites=true`.
Disabilitare in seguito l'opzione impedisce nuovi inviti, ma non revoca quelli già emessi.

### Accettazione

`POST /leagues/inviti/accetta` richiede autenticazione e permesso base `league:view`.
Il body deve contenere esattamente uno tra `{"token": "..."}` e
`{"code": "ABCDE-FGHIJ"}`.

Il server:

1. verifica hash, scadenza e revoca;
2. acquisisce un lock sulla lega;
3. ricontrolla stato e capienza;
4. inserisce membership `member` ed evento audit `league_member_joined` nella stessa
   transazione.

Un secondo tentativo dello stesso utente è idempotente e restituisce
`alreadyMember: true`. Il lock sulla lega serializza gli ingressi concorrenti, mentre il
vincolo univoco `(league_id, user_id)` rimane la garanzia DB contro i duplicati.

Errori di dominio: `invalid_invite`, `invite_expired`, `invite_revoked`, `league_full`,
`league_not_draft`, `manual_invites_disabled`, `invite_not_found`.

Interfacce:

- web admin: `/lega/amministrazione`;
- web ingresso: `/leghe/invito?token=...`, con alternativa codice manuale;
- mobile: schermate demo `LeagueAdmin` e `JoinLeague`, senza integrazione auth/API reale.

## Gestione partecipanti

Le operazioni amministrative usano il prefisso
`/leagues/{league_id}/amministrazione/partecipanti` e richiedono il permesso
`league:admin` nel contesto della lega.

- `GET /partecipanti` restituisce i membri con nome visualizzato, ruolo e data di ingresso.
- `POST /partecipanti/{user_id}/trasferimento-admin` trasferisce atomicamente il ruolo:
  il precedente amministratore diventa partecipante e il destinatario diventa amministratore.
  Ripetere la richiesta verso l'amministratore corrente è un no-op.
- `DELETE /partecipanti/{user_id}` rimuove un partecipante, ma rifiuta sempre la rimozione
  dell'amministratore.

Trasferimento e rimozione sono consentiti solo quando la lega è in bozza. La lega viene
bloccata durante la mutazione; aggiornamento membership ed evento audit avvengono nella
stessa transazione. Gli eventi sono `league_admin_transferred` e `league_member_removed`.
Non vengono registrati nomi o email nei log e nelle metriche.

Errori di dominio: `member_not_found`, `cannot_remove_admin`,
`invalid_transfer_target`, `league_admin_required`, `league_not_draft`.

Metriche:

- `league_member_removed_total{result=success|not_found|cannot_remove_admin|league_not_draft}`
- `league_admin_transferred_total{result=success|noop|not_found|invalid_target|admin_missing|league_not_draft}`

## Stati e avvio stagione

`GET /leagues/{league_id}/amministrazione` include `lifecycle`, con stato corrente,
transizioni immediatamente eseguibili e prerequisiti mancanti:

```json
{
  "state": "auction",
  "allowedTransitions": ["configuring"],
  "blockers": [
    {
      "code": "calendar_not_configured",
      "message": "Genera il calendario prima di avviare la stagione."
    }
  ]
}
```

`POST /leagues/{league_id}/amministrazione/stato` richiede `league:admin` e un body:

```json
{ "targetState": "configuring" }
```

La sequenza principale è:

`draft → configuring → auction → active → concluded → archived`.

Prima dell'avvio è inoltre ammesso `auction → configuring`, per correggere la
configurazione. Le richieste verso lo stato corrente sono idempotenti e non producono
un secondo evento audit. Salti e regressioni non previsti restituiscono
`invalid_league_transition`. Una transizione prevista ma non pronta restituisce
`league_transition_blocked`.

Il passaggio ad asta richiede regolamento valido, almeno tre campionati, un
amministratore e il numero esatto di partecipanti configurato. Il passaggio ad `active`
è il vero avvio stagione e resta bloccato finché non risultano validi calendario,
squadre, rose e crediti. EP03-06 implementa il calendario H2H; rose e crediti restano
dominio delle card successive e continuano a bloccare `auction → active`.

La transizione acquisisce un lock sulla lega e salva stato ed evento
`league_state_changed` nella stessa transazione. L'audit conserva stato precedente e
successivo; log e metriche non includono nomi, email o altri dati personali.

Regolamento, inviti e partecipanti restano modificabili in `draft` e `configuring`.
Per correggerli durante l'asta è necessario riaprire la configurazione.

## Calendario scontri diretti

Endpoint amministrativi (`league:admin`):

- `GET /leagues/{league_id}/amministrazione/calendario`
- `POST /leagues/{league_id}/amministrazione/calendario/genera`
- `POST /leagues/{league_id}/amministrazione/calendario/conferma`

Endpoint consultazione (`league:view`):

- `GET /leagues/{league_id}/calendario` — solo calendari `confirmed`

Formato Standard MVP: **girone di andata** (`single_round_robin`). Ogni coppia di
partecipanti si affronta una sola volta; con numero dispari ogni turno ha un riposo
esplicito (nessun avversario fantasma). L'algoritmo `circle_rr_v1` è deterministico
sull'insieme ordinato dei membership id e conserva `algorithm_version` + fingerprint
partecipanti. La generazione richiede che gli iscritti coincidano col regolamento ed
è consentita in `configuring` o `auction`.

Flusso: genera anteprima (`draft`) → conferma (`confirmed`, idempotente). Una
rigenerazione sostituisce l'anteprima. Se i partecipanti cambiano dopo la generazione,
il calendario risulta stale e va rigenerato. L'associazione ai turni europei
(`fantasy_round`) è fuori scope e arriva con le card turni.

Decisione prodotto documentata (aperta in FR-LEG-04): in questa card si adotta solo
l'andata; andata/ritorno e mapping a turni europei eccedenti restano decisioni future.

Eventi audit: `league_calendar_generated`, `league_calendar_confirmed`.
Tabelle: `league_calendars`, `league_calendar_slots` (FK ai membership, non alle
future `fantasy_team`).

## Audit

Tabella `league_audit_events`: `league_id`, `actor_id`, `action`, `correlation_id`, timestamp UTC.

Metriche:

- `league_created_total{result=success}`
- `league_rules_updated_total{result=success|noop}`
- `league_invite_created_total{result=success|disabled|league_not_draft}`
- `league_invite_revoked_total{result=success|noop|not_found}`
- `league_invite_accepted_total{result=success|already_member|invalid|expired|revoked|full|league_not_draft|rules_missing}`
- `league_member_removed_total{result=success|not_found|cannot_remove_admin|league_not_draft}`
- `league_admin_transferred_total{result=success|noop|not_found|invalid_target|admin_missing|league_not_draft}`
- `league_state_transition_total{result=success|noop|invalid|blocked}`
- `league_calendar_generated_total{result=success|locked|participant_count_mismatch|rules_invalid}`
- `league_calendar_confirmed_total{result=success|noop|missing|stale|locked}`
- `listone_override_writes_total{provider,action=set|clear}` (EP04-04)

## Listone e override ruoli (EP04-04)

`GET /leagues/{league_id}/listone?currentRound=0` — richiede `league:view`.

Restituisce le voci del listone ufficiale della stagione della lega, con ruolo ufficiale, ruolo effettivo, club e eventuale override.

`POST /leagues/{league_id}/amministrazione/listone/aggiorna` — richiede `league:admin`.

Sincronizza catalogo (se necessario) e roster da **API-Football** lato server, poi rigenera `role_assignments`. Non espone la chiave al client. Richiede `API_FOOTBALL_KEY` nell’ambiente backend.

| HTTP | `code` | Caso |
| --- | --- | --- |
| 400 | `provider_key_missing` | Chiave provider assente |
| 400 | `provider_rate_limited` | Quota / 429 (anche errori `rateLimit` in envelope HTTP 200) |
| 400 | `provider_auth_failed` | Chiave rifiutata |
| 400 | `catalog_not_ready` | Nessun club dopo sync catalogo |
| 400 | `provider_sync_failed` / `listone_refresh_failed` | Errore sync/generazione |

UI: schermata **Asta** (`/asta`) — tabella con tab Tutti/P/D/C/A e pulsante «Aggiorna».

`PUT /leagues/{league_id}/amministrazione/listone/{athlete_id}/ruolo` — richiede `league:admin`.

```json
{
  "role": "A",
  "currentRound": 1,
  "reason": "Correzione pre-asta"
}
```

| Stato lega | Effetto |
| --- | --- |
| `draft` / `configuring` / `auction` | Override immediato (`effectiveFromRound: null`) |
| `active` | Decorre dal turno `currentRound + 1` |
| `concluded` / `archived` | Rifiutato (`league_role_override_locked`) |

`DELETE /leagues/{league_id}/amministrazione/listone/{athlete_id}/ruolo` — ripristina il ruolo ufficiale (supersede override attivo).

Dettagli operativi: [`../operations/sports_listone.md`](../operations/sports_listone.md).

## Test

```powershell
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test redis mailpit
docker compose --env-file infra/local/.env.example --profile test run --rm api sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/leagues tests/integration/leagues tests/integration/database -ra'
docker compose --env-file infra/local/.env.example run --rm web pnpm --filter @fantappero/web test
docker compose --env-file infra/local/.env.example run --rm web pnpm --filter @fantappero/mobile test
```

I test d'integrazione rifiutano database il cui nome non termina con `_test`; non usare il
database di sviluppo `fantappero`, perché fixture e test di migrazione eseguono downgrade
e ricreazione dello schema.

Interfaccia web: `/leghe` (elenco) e `/leghe/crea` (form creazione).
