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
  const row = (
    name: string,
    value: number | null | undefined,
    isCurrent = true,
  ): AthleteMarketFields & {
    name: string;
  } => ({
    name,
    marketValue: 10,
    seasonAverage:
      value === undefined
        ? undefined
        : value === null
          ? null
          : isCurrent
            ? { value, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true }
            : { value, seasonYear: 2025, seasonLabel: "25/26", isCurrent: false },
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

  it("prima la stagione in corso, poi la stagione scorsa, poi chi non ha media (Rosario 23/11)", () => {
    const sorted = sortBySeasonAverageDesc([
      row("scorsa-alta", 7.4, false),
      row("senza", null),
      row("in-corso-bassa", 5.5),
      row("scorsa-bassa", 5.1, false),
      row("assente", undefined),
      row("in-corso-alta", 6.8),
      row("scorsa-media", 6.3, false),
      row("in-corso-media", 6.0),
    ]);
    assert.deepEqual(
      sorted.map((item) => item.name),
      [
        "in-corso-alta",
        "in-corso-media",
        "in-corso-bassa",
        "scorsa-alta",
        "scorsa-media",
        "scorsa-bassa",
        "senza",
        "assente",
      ],
    );
    // Anche la media più bassa di quest'anno viene prima della più alta della scorsa.
    assert.ok(compareBySeasonAverageDesc(row("a", 4.5), row("b", 8, false)) < 0);
    assert.ok(compareBySeasonAverageDesc(row("b", 8, false), row("a", 4.5)) > 0);
    // La stagione scorsa viene comunque prima di chi non ha media.
    assert.ok(compareBySeasonAverageDesc(row("b", 4, false), row("c", null)) < 0);
  });

  it("a parità resta l'ordine dato, anche dentro la stagione scorsa", () => {
    const sorted = sortBySeasonAverageDesc([
      row("y", 6.1, false),
      row("x", 6.1, false),
      row("n2", null),
      row("n1", undefined),
      row("z", 6.1),
    ]);
    assert.deepEqual(
      sorted.map((item) => item.name),
      ["z", "y", "x", "n2", "n1"],
    );
    assert.equal(compareBySeasonAverageDesc(row("y", 6.1, false), row("x", 6.1, false)), 0);
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
