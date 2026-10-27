# Email automatiche: cosa resta attivo e cosa è stato spento (Task 6)

| Metadato | Valore |
| --- | --- |
| Moduli | `backend/src/mail/`, `backend/src/notifications/`, `backend/src/auth/service.py` |
| Flag | `NOTIFICATIONS_ROUTINE_EMAIL_ENABLED` (API e worker, default `false`) |

## Perché

Fino a questo lavoro, **ogni** notifica di gioco (gol, asta, scambio,
scadenza formazione, omologazione turno, invito a lega, avviso broadcast…)
mandava anche un'email a chi aveva `notifications_email` attivo nel profilo
(acceso di default). Troppo rumore: queste sono notifiche di routine, già
coperte da in-app e push — l'email va riservata a cose che l'utente deve
vedere anche se non apre l'app (sicurezza dell'account) o a cui l'operatore
vuole dare risalto esplicito (invio manuale).

## Audit: ogni trigger che genera un'email oggi (Task 6a)

| # | Trigger | File:riga | Categoria |
| --- | --- | --- | --- |
| 1 | Registrazione utente → verifica email | `backend/src/auth/service.py:339-359` (`_issue_email_verification`) | **MANTENERE** — sicurezza account |
| 2 | Richiesta reset password | `backend/src/auth/service.py:361-376` (`_issue_password_reset`) | **MANTENERE** — sicurezza account |
| 3 | Notifica generica (`sistema.generico`) | `notifications/service.py:143-154` → `notifications/email_dispatch.py:25` | DISATTIVATA (routine) |
| 4 | Invito nominativo a una lega | `leagues/named_invite_service.py:363-376` (`sistema.invito_lega`) | DISATTIVATA (routine) |
| 5 | Esito di un invito nominativo (a chi ha invitato) | `leagues/named_invite_service.py:579-590` (`sistema.invito_lega_esito`) | DISATTIVATA (routine) |
| 6 | Omologazione turno | `fantasy_turns/homologation_service.py:103-113` (`risultati.omologazione`) | DISATTIVATA (routine) |
| 7 | Correzione di un turno già omologato | `fantasy_turns/homologation_service.py:215-225` (`risultati.correzione`) | DISATTIVATA (routine) |
| 8 | Esito busta di mercato (asta assegnata/persa) | `market/service.py:384-397` (`mercato.esito_busta`) | DISATTIVATA (routine) |
| 9 | Apertura asta live | `market/live_service.py:1309-1319` (`mercato.asta_live_iniziata`) | DISATTIVATA (routine) |
| 10 | Lotto aggiudicato in asta live | `market/live_service.py:1322-1334` (`mercato.asta_live_aggiudicato`) | DISATTIVATA (routine) |
| 11 | Scambio proposto su un lotto live | `market/live_service.py:1336-1350` (`mercato.asta_live_scambio_richiesto`) | DISATTIVATA (routine) |
| 12 | Sorpasso in asta live | `market/live_service.py:1353-1365` (`mercato.asta_live_sorpassato`) | DISATTIVATA (routine) |
| 13 | Stato di una proposta di scambio (proposta/accettata/rifiutata/controproposta) | `market/trade_service.py:596-610` (`mercato.scambio`) | DISATTIVATA (routine) |
| 14 | Reminder scadenza formazione | `notifications/reminder_service.py:70-90` (`formazione.scadenza_turno`) | DISATTIVATA (routine) |
| 15 | Gol/rigore segnato (giocatore in rosa) | `notifications/match_events.py:95-110` (`risultati.gol`, `risultati.assist`) | DISATTIVATA (routine) |
| 16 | Espulsione / ammonizione | `notifications/match_events.py:111-135` (`risultati.espulsione`, `risultati.ammonizione`) | DISATTIVATA (routine) |
| 17 | Sostituzione in campo | `notifications/match_events.py:149-156` (`risultati.sostituzione`) | DISATTIVATA (routine) |
| 18 | Infortunio / squalifica (creazione disponibilità) | `notifications/match_events.py:171-178` (`risultati.infortunio`, `risultati.squalifica`) | DISATTIVATA (routine) |
| 19 | Avviso broadcast dell'operatore (`/admin/notifications/broadcasts`) | `notifications/broadcast_service.py:176-258` | Già **disattivata prima di questo lavoro**: `create_broadcast` rifiuta `channels.email: true` con `email_unavailable` e `deliver()` chiama sempre `create_notification(..., email=False)`. Non toccata. |
| 20 | Notifiche di prova (`/admin/notifications/test-samples`) | `notifications/admin_router.py:276-306` | Passa per lo stesso `create_notification` di #3–18 → segue lo stesso interruttore (DISATTIVATA di default). |
| 21 | Segnalazioni/abusi, errori critici verso l'operatore | — nessun trigger esistente nel codice (nessun modulo di moderazione/alerting trovato in `backend/src`) | **MANTENERE** in linea di principio (categoria da preservare se/quando introdotta); nulla da disattivare oggi. |
| 22 | Email operatore dal portale (nuova, Task 6c) | `notifications/operator_email_service.py` | **Nuova funzionalità**, non un trigger automatico: l'operatore sceglie di mandarla. Non passa dall'interruttore di routine (vedi sotto). |

Le voci #3–20 condividono tutte lo stesso punto di diramazione:
`NotificationService.create_notification()` (`notifications/service.py:143`)
chiama `_dispatch_email()` → `email_dispatch.dispatch_notification_email()`
per qualunque categoria (`sistema`, `formazione`, `mercato`, `risultati`),
indipendentemente da chi l'ha generata.

## Cosa è stato disattivato e come (Task 6b)

Un solo interruttore reversibile, non la cancellazione del codice:

- **Flag**: `notifications_routine_email_enabled` in
  `backend/src/config/settings/notifications_settings.py` (default `False`),
  letto da entrambi i processi (API e worker) tramite
  `NotificationsSettingsMixin`. Stesso pattern già usato per
  `NOTIFICATIONS_PUSH_ENABLED` (`notifications/push_dispatch.py:35`).
- **Punto di controllo**: `backend/src/notifications/email_dispatch.py:34-39`
  — `dispatch_notification_email()` esce subito se il flag è spento, prima
  del controllo di quiete e dell'enqueue su Celery. Una riga, stesso schema
  del kill switch del push.
- **Effetto**: le voci #3–20 dell'audit restano **in-app e push** (se
  l'utente li ha attivi), ma non generano più email, a prescindere dal
  toggle di profilo `notifications_email` (che resta valutato per primo: se
  l'utente l'ha spento, non si arriva nemmeno al nuovo controllo).
- **Reversibilità**: per riaccendere tutte le email di routine basta
  `NOTIFICATIONS_ROUTINE_EMAIL_ENABLED=true` — nessuna modifica di codice,
  nessuna migrazione da disfare.
- **Non toccato**: `auth/service.py` (verifica email, reset password) manda
  l'email direttamente tramite `mail.tasks.send_message_task`, un percorso
  completamente separato da `notifications/email_dispatch.py` — il flag non
  lo riguarda in alcun modo.

### Perché un solo flag e non uno per categoria

Le quattro categorie di notifica (`sistema`, `formazione`, `mercato`,
`risultati`) finiscono **tutte** nella colonna "da disattivare": nessuna
rientra nella categoria da mantenere (registrazione, verifica, reset,
segnalazioni critiche). Un flag per categoria avrebbe aggiunto complessità
senza un caso d'uso reale oggi; se in futuro una categoria dovesse tornare a
mandare email mentre le altre restano spente, il controllo in
`email_dispatch.py` è il punto giusto per diventare per-categoria (stesso
`notification.category.value` già disponibile lì).

## Email operatore dal portale (Task 6c) — perché non segue il flag

La nuova API `/admin/notifications/emails` (vedi
`docs/api/notifications.md`) non è un trigger automatico: un operatore
compone il testo e sceglie consapevolmente di mandarlo. Non passa da
`NotificationService.create_notification()` né da `email_dispatch.py`, e
quindi non è soggetta a `NOTIFICATIONS_ROUTINE_EMAIL_ENABLED` né al toggle
di profilo `notifications_email` — altrimenti un operatore non potrebbe mai
raggiungere chi ha disattivato le email di routine, nemmeno per una
comunicazione importante decisa caso per caso. Resta comunque "umano nel
mezzo": ogni invio richiede un operatore autenticato con `global:operate` e
finisce nello storico (`operator_email_logs`).

## Verifica

```bash
cd backend
python -m pytest tests/unit/notifications/test_email_dispatch.py \
  tests/unit/notifications/test_operator_email_service.py \
  tests/unit/notifications/test_operator_email_router.py -v

# Richiede DATABASE_URL/REDIS_URL (vedi infra/local/.env.example):
python -m pytest tests/integration/notifications/test_email_dispatch.py -v
```
