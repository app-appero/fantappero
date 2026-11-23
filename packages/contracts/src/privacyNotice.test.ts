import assert from "node:assert/strict";
import { test } from "node:test";

import { PRIVACY_NOTICE_SECTIONS, PRIVACY_NOTICE_VERSION } from "./privacyNotice.ts";

const bullets = (id: string): readonly string[] =>
  PRIVACY_NOTICE_SECTIONS.find((section) => section.id === id)?.bullets ?? [];

test("versione dell'informativa approvata il 23/11/2026", () => {
  assert.equal(PRIVACY_NOTICE_VERSION, "2026-11d");
});

test("l'informativa copre l'accesso con Google e con email e password", () => {
  const account = bullets("dati").find((text) => text.startsWith("Account:"));
  assert.ok(account, "manca la voce Account");
  assert.match(account, /non riceviamo né salviamo la tua password Google/);
  assert.match(account, /Se accedi con email e password, la password la salviamo solo in forma cifrata/);
});

test("l'informativa copre la richiesta di accesso al pilota e il telefono per WhatsApp", () => {
  const request = bullets("dati").find((text) => text.startsWith("Richiesta di accesso al pilota:"));
  assert.ok(request, "manca la voce Richiesta di accesso al pilota");
  assert.match(request, /nome, cognome, l'email con cui hai fatto l'accesso e, se li indichi, il numero di telefono e un motivo/);
  assert.match(request, /gruppo WhatsApp dei tester/);
  assert.match(request, /Puoi chiedere di cancellarlo quando vuoi/);
});

test("l'informativa 2026-11d copre l'uso dell'app e del sito da Android", () => {
  const list = bullets("dati");
  const usage = list.find((text) => text.startsWith("Uso dell'app:"));
  assert.ok(usage, "manca la voce Uso dell'app");
  assert.equal(
    usage,
    "Uso dell'app: la versione dell'app che usi, quando l'hai aperta l'ultima volta e, se usi il sito da un telefono Android, che lo usi da Android: per avvisarti quando c'è un aggiornamento dell'app e sapere chi deve ancora aggiornare.",
  );
  // Nello stile delle altre voci: dopo «Notifiche», ultima della lista.
  assert.equal(list.indexOf(usage), list.length - 1);
  assert.ok(list[list.length - 2]?.startsWith("Notifiche:"));
});
