# Lista nera, eliminazione utenti e operatore protetto

Funzioni del pannello operatore (pagina **Utenti**, web e app), decise il 05/11/2026.

## Operatore protetto
- Gli indirizzi nella variabile `PROTECTED_OPERATOR_EMAILS` (default: `trottarosario@gmail.com`;
  più indirizzi separati da virgola) non possono **mai** essere declassati, eliminati né messi
  in lista nera, nemmeno da un altro operatore. Nell'elenco al posto di «Revoca operator»
  compare «Protetto».
- Per cambiare chi è protetto si modifica la variabile su Railway (API).

## Elimina utente
- Pulsante **Elimina** accanto a ogni utente non operatore; chiede conferma («Sei sicuro…») con due scelte: **Elimina** (solo eliminazione: la persona potrà registrarsi di nuovo) ed **Elimina e lista nera** (elimina e blocca l'email).
- L'account viene **anonimizzato** (come l'eliminazione fatta dall'utente: dati personali, avatar e
  segnalazioni rimossi, storici di lega preservati con un nome anonimo) e l'indirizzo email finisce
  in **lista nera**.
- Un operatore non si elimina: prima va revocato il ruolo. Non si elimina se stessi.

## Lista nera
- Scheda **Lista nera** nella pagina Utenti: elenco, aggiunta manuale di un'email (con motivo
  facoltativo) e pulsante per toglierla.
- Chi è in lista nera non può: accedere con Google, accedere con email e password, rinnovare la
  sessione (è disconnesso al prossimo rinnovo), registrarsi di nuovo (anche con maiuscole o
  spazi nell'indirizzo). Messaggio: «Accesso non consentito: questo account è stato bloccato.»
- Il blocco è per **indirizzo email**: se la persona usa un altro account Google, va aggiunto
  anche quello.
- Database: tabella `blocked_accounts` (migrazione `d6f2a9c1e385`).
- API (solo operatori): `POST /admin/users/{id}/delete`, `GET/POST /admin/blocklist`,
  `DELETE /admin/blocklist/{id}`.

## Cosa succede se un utente eliminato era in una lega
Il partecipante resta in lega con un nome anonimo («deleted+…»), con la sua squadra, rosa e punti.
L'**amministratore di lega** lo sostituisce da **Amministrazione lega → Partecipanti → Sostituisci**:
sceglie un fantallenatore dal catalogo (solo quelli disponibili e non già in lega) e questo
**subentra** ereditando squadra, rosa, formazioni e punti. Vale in qualsiasi fase della lega.
- Non si sostituisce l'amministratore (prima si trasferisce il ruolo), né con chi è già in lega,
  né con chi non è disponibile o è in lista nera.
- API: `POST /leagues/{id}/amministrazione/partecipanti/{userId}/sostituzione` con `{newUserId}`.
