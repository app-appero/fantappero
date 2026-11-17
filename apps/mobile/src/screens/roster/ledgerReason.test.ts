import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { reasonLabel } from "./ledgerReason.ts";

describe("reasonLabel", () => {
  it("traduce le causali della rosa", () => {
    assert.equal(reasonLabel("initial_allocation"), "Allocazione iniziale");
    assert.equal(reasonLabel("roster_release_refund"), "Rimborso rosa");
  });

  it("traduce le causali di mercato invece di mostrare il codice", () => {
    assert.equal(reasonLabel("market_auction_win"), "Asta vinta");
    assert.equal(reasonLabel("market_waiver_acquisition"), "Acquisto da svincolati");
    assert.equal(reasonLabel("market_release_refund"), "Rimborso svincolo");
    assert.equal(reasonLabel("market_trade_credits_sent"), "Crediti inviati per scambio");
    assert.equal(reasonLabel("market_trade_credits_received"), "Crediti ricevuti da scambio");
  });

  it("lascia invariata una causale sconosciuta", () => {
    assert.equal(reasonLabel("causale_futura"), "causale_futura");
  });
});
