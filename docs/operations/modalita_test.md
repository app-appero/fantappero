# Modalità test (accesso riservato ai tester)

Serve a tenere chiuso il pilota: con la modalità attiva **solo i tester e gli operatori** possono
accedere; chiunque altro vede «Non autorizzato: l'accesso è riservato ai tester del pilota.» e
**non viene creato nessun account** per lui.

## Come si usa (pannello operatore → Utenti, web e app)

1. **Aggiungi i tester prima degli inviti**: nella scheda «Modalità test», campo «Aggiungi un
   tester (email Google)». Vale l'indirizzo con cui la persona accede con Google. Si può fare anche
   prima che abbia mai acceduto.
2. **Utenti già iscritti**: nell'elenco, pulsante **Abilita tester** accanto al nome (e **Revoca
   tester** per toglierlo). Gli **operatori sono sempre tester**.
3. **Attiva la modalità** con il pulsante «Attiva modalità test». Si spegne con lo stesso pulsante:
   da quel momento chiunque abbia il link può accedere di nuovo.

L'interruttore sta nel database (non in una variabile di Railway): cambia subito, senza riavvii.

## Cosa viene bloccato

Con la modalità attiva il controllo vale per: accesso con Google, accesso con email e password e
**rinnovo della sessione** (chi aveva già una sessione e non è tester viene disconnesso al
prossimo rinnovo, di norma entro pochi minuti). Il sito e le pagine pubbliche (`/accedi`,
`/privacy`) restano raggiungibili: il blocco è all'accesso.

## Note

- Gli indirizzi sono confrontati in minuscolo e senza spazi.
- Se una persona accede con un indirizzo Google diverso da quello in lista, viene bloccata:
  aggiungi quello giusto.
- Dopo aver rimosso un tester, la sua sessione resta valida fino al prossimo rinnovo.
- Database: tabella `tester_allowlist` (migrazione `c4d8e1a7b932`) e chiave `test_mode` in
  `system_flags`.
- API: `GET/PUT /admin/test-mode`, `POST /admin/test-mode/testers`,
  `DELETE /admin/test-mode/testers/{id}` (solo operatori).
