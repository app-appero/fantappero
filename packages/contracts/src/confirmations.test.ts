import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CONFIRM_CANCEL_LABEL,
  CONFIRM_TITLE,
  broadcastConfirmation,
  operatorEmailConfirmation,
  removeMemberConfirmation,
} from "./confirmations.ts";

describe("«Sei sicuro?» di sito e app (release 1.5)", () => {
  it("«Rimuovi partecipante» chiede conferma con il nome", () => {
    const copy = removeMemberConfirmation("Giulia");
    assert.equal(copy.title, "Sei sicuro?");
    assert.equal(CONFIRM_TITLE, "Sei sicuro?");
    assert.match(copy.message, /^Vuoi rimuovere Giulia dalla lega\?/);
    assert.equal(copy.confirmLabel, "Rimuovi");
    assert.equal(copy.cancelLabel, "Annulla");
    assert.equal(CONFIRM_CANCEL_LABEL, "Annulla");
  });

  it("l'invio di notifiche dice a quanti utenti e con quali canali", () => {
    const copy = broadcastConfirmation({
      title: "Nuova versione",
      recipients: 12,
      scheduled: false,
      push: true,
      email: false,
    });
    assert.equal(copy.title, "Sei sicuro?");
    assert.equal(
      copy.message,
      "Stai per inviare la notifica «Nuova versione» a 12 utenti. Canali: App + push. Dopo l'invio non si può annullare.",
    );
    assert.equal(copy.confirmLabel, "Invia");
    assert.equal(copy.cancelLabel, "Annulla");
  });

  it("un solo destinatario al singolare, tutti gli utenti quando il numero non è noto", () => {
    assert.match(
      broadcastConfirmation({ title: "A", recipients: 1, scheduled: false, push: true, email: true }).message,
      /a 1 utente\. Canali: App \+ push \+ email\./,
    );
    assert.match(
      broadcastConfirmation({ title: "A", recipients: null, scheduled: false, push: false, email: false }).message,
      /a tutti gli utenti\. Canali: App\./,
    );
  });

  it("una notifica programmata si «programma»", () => {
    const copy = broadcastConfirmation({
      title: "Avviso",
      recipients: 3,
      scheduled: true,
      push: true,
      email: false,
    });
    assert.equal(copy.confirmLabel, "Programma");
    assert.match(copy.message, /^Stai per programmare la notifica «Avviso» per 3 utenti\./);
    assert.doesNotMatch(copy.message, /non si può annullare/);
  });

  it("l'email dell'operatore chiede conferma con il numero dei destinatari", () => {
    assert.equal(
      operatorEmailConfirmation({ recipients: 4 }).message,
      "Inviare l'email a 4 utenti? Dopo l'invio non si può annullare.",
    );
    assert.match(operatorEmailConfirmation({ recipients: null }).message, /a tutti gli utenti\?/);
    assert.equal(operatorEmailConfirmation({ recipients: 2 }).confirmLabel, "Invia");
  });
});
