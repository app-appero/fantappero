# Lista nera, eliminazione utenti e operatore protetto

Funzioni del pannello operatore (pagina **Utenti**, web e app), decise il 05/11/2026.

## Operatore protetto
- Gli indirizzi nella variabile `PROTECTED_OPERATOR_EMAILS` (default: `trottarosario@gmail.com`;
  più indirizzi separati da virgola) non possono **mai** essere declassati, eliminati né messi
  in lista nera, nemmeno da un altro operatore. Nell'elenco al posto di «Revoca operator»
  compare «Protetto».
- Per cambiare chi è protetto si modifica la variabile su Railway (API).

## Elimina utente
- Pulsante **Elimina** accanto a ogni utente non operatore; chiede conferma («Sei sicuro…»).
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
