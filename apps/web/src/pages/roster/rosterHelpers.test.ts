import { describe, expect, it } from "vitest";
import type { CreditLedgerEntry, LeagueListoneEntry } from "@fantappero/contracts";
import { foldSearchText, matchesSearch } from "../../utils/searchText";
import { filterListone, ownershipSourceLabel, reasonLabel, sortLedgerNewestFirst } from "./rosterHelpers";

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

describe("ownershipSourceLabel (storico della rosa, QA 19-20/11)", () => {
  it("traduce ogni origine del possesso inviata dal backend", () => {
    expect(ownershipSourceLabel("manual")).toBe("Inserimento manuale");
    expect(ownershipSourceLabel("csv_import")).toBe("Importazione da file");
    expect(ownershipSourceLabel("admin")).toBe("Assegnazione admin");
    expect(ownershipSourceLabel("market")).toBe("Mercato");
  });

  it("un'origine sconosciuta ha un'etichetta generica, mai il codice", () => {
    expect(ownershipSourceLabel("origine_futura")).toBe("Altro");
    expect(ownershipSourceLabel("")).toBe("Altro");
    expect(ownershipSourceLabel("toString")).toBe("Altro");
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

describe("filterListone con campionato e squadra (Rosario, 21/11)", () => {
  const entries = [
    {
      athleteId: "1",
      canonicalName: "Dodô",
      effectiveRole: "D",
      clubId: "fio",
      clubName: "Fiorentina",
      competitionId: "ita",
      competitionName: "Serie A",
    },
    {
      athleteId: "2",
      canonicalName: "L. JovanoviÄ\u0087",
      effectiveRole: "D",
      clubId: "fio",
      clubName: "Fiorentina",
      competitionId: "ita",
      competitionName: "Serie A",
    },
    {
      athleteId: "3",
      canonicalName: "M. Ødegaard",
      effectiveRole: "C",
      clubId: "ars",
      clubName: "Arsenal",
      competitionId: "eng",
      competitionName: "Premier League",
    },
  ] as unknown as LeagueListoneEntry[];

  it("combina campionato e squadra con ruolo, ricerca e «Solo disponibili»", () => {
    const ids = (rows: LeagueListoneEntry[]) => rows.map((row) => row.athleteId);
    const owned = new Set(["1"]);
    const serieA = { competitionId: "ita", clubId: null };
    expect(ids(filterListone(entries, "all", "", false, undefined, serieA))).toEqual(["1", "2"]);
    expect(ids(filterListone(entries, "D", "", true, owned, serieA))).toEqual(["2"]);
    expect(ids(filterListone(entries, "all", "dodo", true, owned, serieA))).toEqual(["1"]);
    expect(ids(filterListone(entries, "all", "odegaard", false, undefined, serieA))).toEqual([]);
    expect(
      ids(filterListone(entries, "all", "", false, undefined, { competitionId: null, clubId: "ars" })),
    ).toEqual(["3"]);
  });

  it("usa la ricerca del sito, che ripara anche la codifica rovinata", () => {
    const fiorentina = { competitionId: "ita", clubId: "fio" };
    expect(filterListone(entries, "all", "jovanovic", false, undefined, fiorentina).map((row) => row.athleteId)).toEqual([
      "2",
    ]);
  });
});

describe("sortLedgerNewestFirst", () => {
  function entry(id: string, createdAt: string, balanceAfter: number): CreditLedgerEntry {
    return {
      id,
      amount: 0,
      reason: "market_auction_win",
      transactionId: id,
      balanceAfter,
      note: null,
      actorId: null,
      createdAt,
    };
  }

  it("mette prima i movimenti più recenti", () => {
    const older = entry("a", "2026-11-19T10:00:00+00:00", 1000);
    const newer = entry("b", "2026-11-19T11:00:00+00:00", 990);
    expect(sortLedgerNewestFirst([older, newer]).map((row) => row.id)).toEqual(["b", "a"]);
  });

  it("a parità di orario tiene l'ordine del server rovesciato, non quello casuale dell'id (QA 19-20/11)", () => {
    // Il server li manda dal più vecchio: rimborso, poi addebito, poi un altro addebito.
    const sameTime = "2026-11-19T10:00:00.123+00:00";
    const fromServer = [
      entry("zzz", sameTime, 1010),
      entry("aaa", sameTime, 1000),
      entry("mmm", sameTime, 990),
    ];
    expect(sortLedgerNewestFirst(fromServer).map((row) => row.balanceAfter)).toEqual([
      990, 1000, 1010,
    ]);
    expect(fromServer.map((row) => row.id)).toEqual(["zzz", "aaa", "mmm"]);
  });
});
