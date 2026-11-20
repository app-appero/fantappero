import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { sortLedgerNewestFirst } from "./ledgerOrder.ts";

function entry(id: string, createdAt: string, balanceAfter: number) {
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

describe("sortLedgerNewestFirst", () => {
  it("mette prima i movimenti più recenti", () => {
    const older = entry("a", "2026-11-19T10:00:00+00:00", 1000);
    const newer = entry("b", "2026-11-19T11:00:00+00:00", 990);
    assert.deepEqual(
      sortLedgerNewestFirst([older, newer]).map((row) => row.id),
      ["b", "a"],
    );
  });

  it("a parità di orario tiene l'ordine del server rovesciato, non quello casuale dell'id (QA 19-20/11)", () => {
    // Il server li manda dal più vecchio: rimborso, poi addebito, poi un altro addebito.
    const sameTime = "2026-11-19T10:00:00.123+00:00";
    const fromServer = [
      entry("zzz", sameTime, 1010),
      entry("aaa", sameTime, 1000),
      entry("mmm", sameTime, 990),
    ];
    assert.deepEqual(
      sortLedgerNewestFirst(fromServer).map((row) => row.balanceAfter),
      [990, 1000, 1010],
    );
  });

  it("non modifica l'elenco ricevuto", () => {
    const fromServer = [entry("a", "2026-11-19T10:00:00+00:00", 1000), entry("b", "2026-11-19T11:00:00+00:00", 990)];
    sortLedgerNewestFirst(fromServer);
    assert.deepEqual(
      fromServer.map((row) => row.id),
      ["a", "b"],
    );
  });
});
