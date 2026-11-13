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
