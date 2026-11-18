import { describe, expect, it } from "vitest";
import type { LeagueListoneEntry } from "@fantappero/contracts";
import { foldSearchText, matchesSearch } from "../../utils/searchText";
import { filterListone, reasonLabel } from "./rosterHelpers";

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

describe("filterListone (ricerca senza accenti, QA 18/11)", () => {
  const entries = [
    { athleteId: "1", canonicalName: "A. Dembélé", effectiveRole: "A", clubName: "Paris" },
    { athleteId: "2", canonicalName: "M. Ødegaard", effectiveRole: "C", clubName: "Arsenal" },
    { athleteId: "3", canonicalName: "G. Donnarumma", effectiveRole: "P", clubName: "Paris" },
  ] as unknown as LeagueListoneEntry[];

  it("trova i nomi con l'accento scrivendoli senza", () => {
    expect(filterListone(entries, "all", "dembele").map((row) => row.athleteId)).toEqual(["1"]);
    expect(filterListone(entries, "all", "ODEGAARD").map((row) => row.athleteId)).toEqual(["2"]);
    expect(filterListone(entries, "all", "Dembélé").map((row) => row.athleteId)).toEqual(["1"]);
  });

  it("normalizza accenti, maiuscole e spazi", () => {
    expect(foldSearchText("  Çalhanoğlu ")).toBe("calhanoglu");
    expect(matchesSearch("Müller", "muller")).toBe(true);
  });
});
