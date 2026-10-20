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

test("giorni", () => {
  const now = new Date(2026, 9, 20, 12, 0);
  assert.equal(notificationDayLabel(new Date(2026, 9, 20, 9, 0).toISOString(), now), "Oggi");
  assert.equal(notificationDayLabel(new Date(2026, 9, 19, 23, 0).toISOString(), now), "Ieri");
});
