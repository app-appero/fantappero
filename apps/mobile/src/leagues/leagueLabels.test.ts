import assert from "node:assert/strict";
import test from "node:test";
import { leagueStateLabel } from "./leagueLabels.ts";

test("lo stato della lega si legge come etichetta, non come codice (come il web)", () => {
  assert.equal(leagueStateLabel("draft"), "Bozza");
  assert.equal(leagueStateLabel("configuring"), "Configurazione");
  assert.equal(leagueStateLabel("auction"), "Asta");
  assert.equal(leagueStateLabel("active"), "Attiva");
  assert.equal(leagueStateLabel("concluded"), "Conclusa");
  assert.equal(leagueStateLabel("archived"), "Archiviata");
});

test("stato assente: trattino", () => {
  for (const value of [undefined, null, ""]) {
    assert.equal(leagueStateLabel(value), "—", JSON.stringify(value));
  }
});

test("uno stato che l'app non conosce ancora resta leggibile col suo codice", () => {
  // Il pannello operatore riceve lo stato come stringa libera (AdminLeague.state).
  assert.equal(leagueStateLabel("suspended"), "suspended");
});
