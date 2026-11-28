import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CONFIRM_CANCEL_LABEL,
  CONFIRM_TITLE,
  broadcastConfirmation,
  memberRemovedMessage,
  operatorEmailConfirmation,
  participantCountAfterRemoval,
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

  it("l'email dell'operatore a un solo destinatario dice «1 utente»", () => {
    assert.equal(
      operatorEmailConfirmation({ recipients: 1 }).message,
      "Inviare l'email a 1 utente? Dopo l'invio non si può annullare.",
    );
  });
});

describe("«allineato agli iscritti» solo se i previsti cambiano davvero (QA 28/11, D1)", () => {
  it("stessa regola del server: si abbassa solo con almeno 4 rimasti e previsti in più", () => {
    // Previsti 4, iscritti 3, ne rimuovo uno: restano 2 (< 4) e il server non tocca i previsti.
    assert.equal(participantCountAfterRemoval({ participantCount: 4, participantMin: 4, remaining: 2 }), 4);
    // Previsti 8, restano 5: si allineano.
    assert.equal(participantCountAfterRemoval({ participantCount: 8, participantMin: 4, remaining: 5 }), 5);
    // Restano esattamente 4 con previsti 6: si allineano a 4.
    assert.equal(participantCountAfterRemoval({ participantCount: 6, participantMin: 4, remaining: 4 }), 4);
    // Previsti già pari o sotto gli iscritti rimasti: nessun cambio.
    assert.equal(participantCountAfterRemoval({ participantCount: 5, participantMin: 4, remaining: 5 }), 5);
    assert.equal(participantCountAfterRemoval({ participantCount: 4, participantMin: 4, remaining: 6 }), 4);
    // Minimo non noto: vale 4, come sul server.
    assert.equal(participantCountAfterRemoval({ participantCount: 8, remaining: 3 }), 8);
    assert.equal(participantCountAfterRemoval({ participantCount: 8, participantMin: null, remaining: 4 }), 4);
    // Minimo più alto di 4: rispettato.
    assert.equal(participantCountAfterRemoval({ participantCount: 8, participantMin: 6, remaining: 5 }), 8);
  });

  it("4 previsti e 2 rimasti: i previsti restano 4, niente «allineato»", () => {
    const counts = { participantCount: 4, participantMin: 4, remaining: 2 };
    assert.equal(
      memberRemovedMessage("Giulia", counts),
      "Giulia è stato rimosso dalla lega. I partecipanti previsti restano 4.",
    );
    const copy = removeMemberConfirmation("Giulia", counts);
    assert.equal(copy.message, "Vuoi rimuovere Giulia dalla lega? I partecipanti previsti restano 4.");
    assert.doesNotMatch(copy.message, /allinea/);
    assert.doesNotMatch(memberRemovedMessage("Giulia", counts), /allineato/);
  });

  it("8 previsti e 5 rimasti: i previsti si allineano e il messaggio dice a quanti", () => {
    const counts = { participantCount: 8, participantMin: 4, remaining: 5 };
    assert.equal(
      memberRemovedMessage("Marco", counts),
      "Marco è stato rimosso dalla lega. Il numero partecipanti previsti è stato allineato agli iscritti (5).",
    );
    assert.equal(
      removeMemberConfirmation("Marco", counts).message,
      "Vuoi rimuovere Marco dalla lega? Il numero dei partecipanti previsti si allinea agli iscritti rimasti.",
    );
  });

  it("previsti non noti: niente frase sui previsti", () => {
    assert.equal(memberRemovedMessage("Giulia"), "Giulia è stato rimosso dalla lega.");
    assert.equal(
      memberRemovedMessage("Giulia", { participantCount: null, remaining: 5 }),
      "Giulia è stato rimosso dalla lega.",
    );
    assert.equal(
      memberRemovedMessage("Giulia", { participantCount: undefined, participantMin: 4, remaining: 5 }),
      "Giulia è stato rimosso dalla lega.",
    );
    assert.equal(removeMemberConfirmation("Giulia").message, "Vuoi rimuovere Giulia dalla lega?");
    assert.equal(
      removeMemberConfirmation("Giulia", { participantCount: null, remaining: 5 }).message,
      "Vuoi rimuovere Giulia dalla lega?",
    );
  });

  it("minimo non noto: vale 4 come sul server", () => {
    assert.match(memberRemovedMessage("Anna", { participantCount: 8, remaining: 3 }), /restano 8\.$/);
    assert.match(
      memberRemovedMessage("Anna", { participantCount: 8, remaining: 4 }),
      /allineato agli iscritti \(4\)\.$/,
    );
  });
});
