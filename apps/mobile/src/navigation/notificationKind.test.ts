import assert from "node:assert/strict";
import test from "node:test";
import { notificationDayLabel, notificationKind } from "./notificationKind.ts";

test("eventi dei giocatori", () => {
  assert.deepEqual(notificationKind({ title: "Gol di Lautaro Martinez", category: "risultati" }), { group: "giocatori", glyph: "⚽" });
  assert.equal(notificationKind({ title: "Espulso Bastoni", category: "risultati" }).glyph, "🟥");
  assert.equal(notificationKind({ title: "Esce Leao, entra Chiesa", category: "risultati" }).group, "giocatori");
});

test("scambi, asta e formazione", () => {
  assert.equal(notificationKind({ title: "Giulia United ti propone uno scambio", category: "mercato" }).group, "scambi");
  assert.equal(notificationKind({ title: "Sei stato sorpassato su Y. Diouf", category: "mercato" }).group, "asta");
  assert.equal(notificationKind({ title: "Scadenza formazione in arrivo", category: "formazione" }).group, "formazione");
});

test("gli esiti degli svincolati stanno con l'asta, non con gli scambi", () => {
  for (const title of [
    "Svincolato aggiudicato",
    "Svincolato perso",
    "Spareggio svincolati aperto",
    "Spareggio svincolati annullato",
  ]) {
    assert.deepEqual(notificationKind({ title, category: "mercato" }), { group: "asta", glyph: "🔨" }, title);
  }
});

test("gli spareggi dell'asta a buste stanno con l'asta, non con gli scambi (QA 22→23/11)", () => {
  // Titoli di mercato.esito_busta (backend/src/notifications/templates.py), categoria «mercato».
  for (const title of ["Spareggio aperto", "Spareggio annullato"]) {
    assert.deepEqual(notificationKind({ title, category: "mercato" }), { group: "asta", glyph: "🔨" }, title);
  }
});

test("giorni", () => {
  const now = new Date(2026, 9, 20, 12, 0);
  assert.equal(notificationDayLabel(new Date(2026, 9, 20, 9, 0).toISOString(), now), "Oggi");
  assert.equal(notificationDayLabel(new Date(2026, 9, 19, 23, 0).toISOString(), now), "Ieri");
});
