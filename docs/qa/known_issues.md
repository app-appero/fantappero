# Problemi noti (dev)

Aggiornato da Rosario/Claude dopo ogni rapporto. I tester non ripetono i dettagli di ciò che è qui.

| Data | Area | Titolo | Stato |
| --- | --- | --- | --- |
| 2026-11-13 | Turni | Formazioni degli altri partecipanti leggibili | Voluto: non segnalare |
| 2026-11-13 | Mercato | Interruttore "scambi consentiti" nelle regole di lega | Voluto: gli scambi sono sempre attivi, si bloccano solo a turno in corso; non segnalare |
| 2026-11-13 | Turni | Turni creati a mano restano `scheduled` e un admin di lega non può aprirli | Voluto: i turni sono automatici (generati e aperti dal sistema), l'apertura manuale è solo override operatore |
| 2026-11-13 | Turni | Turni passati con partite concluse ancora `scheduled`; anteprima finestre con `fixtureCount` 0 | Dipende dai dati sportivi di dev: non segnalare |
| 2026-11-13 | Mercato | Codici 400 invece di 403/404 per azioni vietate sugli scambi | Aperto, stile: nessuna fuga di dati |
| 2026-11-13 | Mercato | Mobile: il tocco su una notifica non cambia ancora la lega attiva (il web sì, con `?lega=`) | Aperto |
| 2026-11-13 | Test | Falliti già prima del lavoro QA: `test_named_invites` (2), `test_update_league_rules_is_idempotent_for_same_payload`, notifiche omologazione e scambio | Aperto, test vecchi da riallineare |
| 2026-11-13 | Web | Contrasto tema chiaro/scuro di badge, podio, tab e pulsante elimina | Corretto, da verificare a vista a 1280 e 390 |
| 2026-11-14 | Mercato | Già CORRETTI il 13/11 (non segnalare): svincolo ripetuto sullo stesso slot senza rimborso; slot extra dopo esubero; lotto live annullato che non torna in coda; notifica di annullo e scadenza scambi; notifica busta persa con motivo; proposta in attesa obsoleta ritirabile; errori 422 nel formato {message, code}; offerta su calciatore senza ruolo rifiutata; risolvi/aggiudica a mercato chiuso bloccati; scambio live dello stesso ruolo con ruolo in sovrannumero; assegnazione slot da parte dei membri vietata; una sola asta live per lega; prezzo d'acquisto che segue il calciatore; crediti richiesti entro il saldo dell'altro | Corretto |
| 2026-11-14 | Mercato | Asta a buste: più sessioni "aperte" insieme quando ce n'è una scaduta e non chiusa; sessione con finestra già passata accettata | In correzione |
| 2026-11-14 | Mercato | 500 con scadenza proposta oltre il 9999 e con importi oltre 2^31 (asta live, rilanci, offerte a buste) | In correzione |
| 2026-11-14 | Mercato | Le rotte /asta/ accettano ancora le sessioni dell'asta live | In correzione |
| 2026-11-14 | Mercato | Svincolo ripetuto con slot rimescolati svincola un altro calciatore (serve athleteId nella richiesta) | In correzione |
| 2026-11-14 | Mercato | Lotto live scaduto non chiuso se nessuno guarda lo stato; a mercato chiuso un GET può vendere | In correzione |
| 2026-11-14 | Mercato | Limite proposte attive aggirabile con approvazione admin; proposta con crediti non più sufficienti resta aperta | Da decidere |
| 2026-11-14 | Mercato | Nessuna notifica di spareggio; link della notifica "Scambio da approvare" rotto dopo la decisione dell'admin | In correzione |
| 2026-11-14 | Mercato | Waiver: il calciatore svincolato per fare posto non viene rimborsato | Da decidere |
| 2026-11-14 | Mercato | "Scambi conclusi" conta anche annullati, rifiutati, scaduti; "Da gestire" non conta le approvazioni dell'admin | Da decidere |
| 2026-11-14 | Notifiche | Mancano le notifiche di turno e di lega (invito accettato, attivazione, turno aperto) | Da decidere |
| 2026-11-14 | Mercato | CORRETTI il 14/11 (non segnalare): più sessioni a buste attive insieme; finestra già passata o oltre 2 anni; 500 su importi oltre 2^31 e scadenze oltre 1 anno; rotte /asta/ che accettavano sessioni live; svincolo che rimuove un altro calciatore (ora c'è l'id); lotto live scaduto non chiuso; notifica di spareggio; link "Scambio da approvare" dopo la decisione; bidCount con ritirate; coda sequenziale svuotabile; messaggio dei 422 | Corretto |
| 2026-11-14 | Scambi | Proposta con crediti non sufficienti: resta aperta ma "in attesa di crediti" (Accetta disabilitato, non conta nel limite, si riattiva da sola) | Voluto |
| 2026-11-14 | Notifiche | Aggiunte notifiche di nuovo partecipante, lega attivata e turno aperto (entro 10 giorni dal blocco) | Corretto |
| 2026-11-14 | Test | Falliti già prima del 14/11 (dipendono dalla data): `test_kickoff_time_shift_before_elapsed_can_delay_cutoff`, `test_recalculate_cutoff_does_not_move_later_after_elapsed_postponement`, `test_a_league_without_rosters_generates_no_turns` | Aperto, test da riallineare |
