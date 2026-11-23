import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  type AthleteMarketFields,
  compareBySeasonAverageDesc,
  seasonLabel,
  sortBySeasonAverageDesc,
} from "./athleteValue.ts";

describe("seasonLabel", () => {
  it("scrive la stagione come «25/26»", () => {
    assert.equal(seasonLabel(2025), "25/26");
    assert.equal(seasonLabel(2026), "26/27");
    assert.equal(seasonLabel(2009), "09/10");
    assert.equal(seasonLabel(2099), "99/00");
  });
});

describe("Ordina per media", () => {
  const row = (name: string, value: number | null | undefined): AthleteMarketFields & {
    name: string;
  } => ({
    name,
    marketValue: 10,
    seasonAverage:
      value === undefined
        ? undefined
        : value === null
          ? null
          : { value, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true },
  });

  it("dalla media più alta alla più bassa, chi non ha media in fondo", () => {
    const sorted = sortBySeasonAverageDesc([
      row("senza", null),
      row("bassa", 5.5),
      row("assente", undefined),
      row("alta", 7.25),
      row("media", 6.5),
    ]);
    assert.deepEqual(
      sorted.map((item) => item.name),
      ["alta", "media", "bassa", "senza", "assente"],
    );
  });

  it("a parità resta l'ordine dato e non modifica l'elenco originale", () => {
    const input = [row("b", 6), row("a", 6), row("c", null)];
    const sorted = sortBySeasonAverageDesc(input);
    assert.deepEqual(
      sorted.map((item) => item.name),
      ["b", "a", "c"],
    );
    assert.deepEqual(
      input.map((item) => item.name),
      ["b", "a", "c"],
    );
    assert.equal(compareBySeasonAverageDesc(row("x", null), row("y", undefined)), 0);
  });
});
