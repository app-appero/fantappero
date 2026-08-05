# Privacy API (EP02-04)

Endpoint sotto `/profile/me` per esercitare i diritti sui dati dell'utente autenticato. Le operazioni sono **solo self-service** e vengono registrate in `privacy_audit_events`.

## Endpoint

| Metodo | Percorso | Descrizione |
| --- | --- | --- |
| `GET` | `/profile/me/export` | Esportazione JSON completa e leggibile |
| `POST` | `/profile/me/delete` | Eliminazione account con anonimizzazione |

Tutti gli endpoint richiedono `Authorization: Bearer <access_token>` e permesso `profile:view`.

## Esportazione dati

La risposta è un file JSON (`Content-Disposition: attachment`) con:

- metadati export (`exportedAt`, `formatVersion`)
- account (`email`, ruolo, date)
- profilo e preferenze
- membership di lega (nome lega, ruolo, etichetta storica se presente)

Viene scritto un evento audit `data_export` con `correlation_id` della richiesta HTTP.

## Eliminazione account

Body JSON:

```json
{
  "password": "Password123!",
  "confirmPhrase": "ELIMINA"
}
```

Regole applicate lato server:

1. Verifica password e frase di conferma (`ELIMINA`).
2. Per ogni `league_membership`, salva `historical_display_name` con l'ultimo nome visualizzato noto (preserva storici competitivi).
3. Soft-delete dell'utente (`deleted_at`), email anonimizzata `deleted+<uuid>@anon.fantappero.invalid`, password invalidata.
4. Pulizia profilo (nome, avatar, consensi, notifiche).
5. Revoca sessioni e token attivi; rimozione file avatar.
6. Evento audit `account_delete`.

Dopo l'eliminazione, login, refresh e accesso al profilo con i token precedenti falliscono.

## Metriche

- `privacy_export_total`
- `privacy_delete_total`

## Audit (EP11-03 — scope privacy)

Tabella `privacy_audit_events`: `user_id`, `actor_id`, `action`, `correlation_id`, timestamp UTC.

Per EP02-04 non è richiesta l'interfaccia operatore di consultazione audit (card EP11-03 completa).
