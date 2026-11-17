import { describe, expect, it } from "vitest";
import { reasonLabel } from "./rosterHelpers";

describe("reasonLabel", () => {
  it("traduce le causali della rosa", () => {
    expect(reasonLabel("initial_allocation")).toBe("Allocazione iniziale");
    expect(reasonLabel("roster_release_refund")).toBe("Rimborso rosa");
  });

  it("traduce le causali di mercato invece di mostrare il codice", () => {
    expect(reasonLabel("market_auction_win")).toBe("Asta vinta");
    expect(reasonLabel("market_waiver_acquisition")).toBe("Acquisto da svincolati");
    expect(reasonLabel("market_release_refund")).toBe("Rimborso svincolo");
    expect(reasonLabel("market_trade_credits_sent")).toBe("Crediti inviati per scambio");
    expect(reasonLabel("market_trade_credits_received")).toBe("Crediti ricevuti da scambio");
  });

  it("lascia invariata una causale sconosciuta", () => {
    expect(reasonLabel("causale_futura")).toBe("causale_futura");
  });
});
