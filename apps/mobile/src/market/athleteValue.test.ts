import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { AthleteSeasonAverage, LeagueListoneEntry } from "@fantappero/contracts";
// Lo stesso ordinamento che l'app passa da `@fantappero/contracts` (qui dal sorgente).
import { sortBySeasonAverageDesc } from "../../../../packages/contracts/src/athleteValue.ts";
import {
  DEFAULT_LISTONE_VIEW_TOGGLES,
  athleteMarketTags,
  formatDecimalIt,
  formatIntegerIt,
  marketValueLabel,
  orderListoneRows,
  resetListoneViewToggles,
  seasonAverageDisplay,
  seasonAverageText,
} from "./athleteValue.ts";

const current: AthleteSeasonAverage = { value: 6.45, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true };
const previous: AthleteSeasonAverage = { value: 6.12, seasonYear: 2025, seasonLabel: "25/26", isCurrent: false };

function entry(athleteId: string, seasonAverage: AthleteSeasonAverage | null | undefined, marketValue?: number | null) {
  return { athleteId, canonicalName: athleteId, seasonAverage, marketValue } as LeagueListoneEntry;
}

describe("media stagionale", () => {
  it("verde con il solo numero se è della stagione in corso", () => {
    assert.deepEqual(seasonAverageDisplay(current), {
      text: "6,45",
      tone: "current",
      accessibilityLabel: "Media 6,45, stagione in corso",
    });
  });

  it("rossa con l'anno se è della stagione scorsa", () => {
    assert.deepEqual(seasonAverageDisplay(previous), {
      text: "6,12 · 25/26",
      tone: "previous",
      accessibilityLabel: "Media 6,12, stagione 25/26",
    });
  });

  it("niente se manca (null, assente da un backend più vecchio)", () => {
    assert.equal(seasonAverageDisplay(null), null);
    assert.equal(seasonAverageDisplay(undefined), null);
    assert.equal(seasonAverageText(null), "—");
  });

  it("virgola italiana e due decimali", () => {
    assert.equal(formatDecimalIt(6), "6,00");
    assert.equal(formatDecimalIt(6.5), "6,50");
    assert.equal(seasonAverageDisplay({ ...current, value: 7 })?.text, "7,00");
    assert.equal(formatIntegerIt(1650), "1.650");
    assert.equal(formatIntegerIt(300), "300");
  });
});

describe("Valore", () => {
  it("«Valore N» solo se c'è", () => {
    assert.equal(marketValueLabel(58), "Valore 58");
    assert.equal(marketValueLabel(0), "Valore 0");
    assert.equal(marketValueLabel(null), null);
    assert.equal(marketValueLabel(undefined), null);
  });

  it("etichette della riga: Valore e media, ognuna solo se c'è", () => {
    assert.deepEqual(athleteMarketTags({ marketValue: 12, seasonAverage: null }), { valueLabel: "Valore 12", average: null });
    assert.equal(athleteMarketTags({}).valueLabel, null);
    assert.equal(athleteMarketTags(null).average, null);
    assert.equal(athleteMarketTags({ seasonAverage: previous }).average?.tone, "previous");
  });
});

describe("Ordina per media", () => {
  const rows = [
    entry("senza-media", null, 3),
    entry("scorsa-612", previous, 12),
    entry("in-corso-645", current, 24),
    entry("scorsa-720", { ...previous, value: 7.2 }, 40),
    entry("in-corso-701", { ...current, value: 7.01 }, 58),
    entry("assente", undefined),
  ];

  it("spenta: resta l'ordine del listone", () => {
    assert.deepEqual(
      orderListoneRows(rows, false, sortBySeasonAverageDesc).map((row) => row.athleteId),
      ["senza-media", "scorsa-612", "in-corso-645", "scorsa-720", "in-corso-701", "assente"],
    );
  });

  it("accesa: prima la stagione in corso, poi la scorsa, chi non ha media in fondo (Rosario 23/11)", () => {
    assert.deepEqual(
      orderListoneRows(rows, true, sortBySeasonAverageDesc).map((row) => row.athleteId),
      ["in-corso-701", "in-corso-645", "scorsa-720", "scorsa-612", "senza-media", "assente"],
    );
  });

  it("non cambia l'elenco di partenza", () => {
    orderListoneRows(rows, true, sortBySeasonAverageDesc);
    assert.equal(rows[0]?.athleteId, "senza-media");
  });

  it("«Azzera filtri» spegne «Ordina per media» e lascia «Solo disponibili» com'è", () => {
    assert.deepEqual(resetListoneViewToggles({ onlyFree: true, sortByAverage: true }), {
      onlyFree: true,
      sortByAverage: false,
    });
    assert.deepEqual(resetListoneViewToggles({ onlyFree: false, sortByAverage: true }), {
      onlyFree: false,
      sortByAverage: false,
    });
    assert.deepEqual(DEFAULT_LISTONE_VIEW_TOGGLES, { onlyFree: false, sortByAverage: false });
  });
});
