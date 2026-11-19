import assert from "node:assert/strict";
import test from "node:test";
import { TRADE_OFFERED_LABEL, TRADE_REQUESTED_LABEL, tradeExpiryLabel } from "./tradeCardLabels.ts";

test("le due parti della proposta hanno le etichette del web", () => {
  assert.equal(TRADE_OFFERED_LABEL, "Offerti");
  assert.equal(TRADE_REQUESTED_LABEL, "Richiesti");
});

test("senza scadenza la scheda lo dice, come il web", () => {
  for (const value of [null, undefined, "", "   "]) {
    assert.equal(tradeExpiryLabel(value), "Nessuna scadenza", JSON.stringify(value));
  }
});

test("con una scadenza mostra «Scade il …» con giorno, mese e ora", () => {
  // L'ora è quella del fuso del dispositivo: il test fissa quello italiano.
  const previousTz = process.env.TZ;
  process.env.TZ = "Europe/Rome";
  try {
    assert.equal(tradeExpiryLabel("2026-11-19T12:00:00Z"), "Scade il 19 nov, 13:00");
  } finally {
    if (previousTz === undefined) {
      delete process.env.TZ;
    } else {
      process.env.TZ = previousTz;
    }
  }
});
