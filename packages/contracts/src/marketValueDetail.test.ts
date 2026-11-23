import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  type AdminMarketValueDetail,
  type AdminMarketValueSeasonDetail,
  formatPercentileOrdinal,
  formatValueNumber,
  formatWeightPercent,
  marketValueBaseSentence,
  marketValueBudgetSentence,
  marketValueCreditsForBudget,
  marketValueCurveSentence,
  marketValueExcludedText,
  marketValueIndexSentence,
  marketValueSeasonName,
  marketValueSeasonSentence,
  marketValueStatusText,
} from "./marketValueDetail.ts";

function season(overrides: Partial<AdminMarketValueSeasonDetail>): AdminMarketValueSeasonDetail {
  return {
    slot: "previous",
    seasonYear: 2025,
    seasonLabel: "25/26",
    isCurrent: false,
    source: "provider",
    competitions: ["Premier League"],
    rows: [],
    excluded: [],
    hasData: true,
    appearances: 34,
    average: 7.03,
    roleAverage: 6.88,
    shrunkAverage: 6.9814,
    percentile: 0.62,
    rank: 69,
    poolSize: 180,
    weight: 0.3,
    indexUsed: 0.62,
    contribution: 0.186,
    ...overrides,
  };
}

const DETAIL: AdminMarketValueDetail = {
  athleteId: "a1",
  canonicalName: "G. Donnarumma",
  clubName: "Manchester City",
  role: "P",
  seasonYear: 2026,
  seasonLabel: "26/27",
  status: "computed",
  version: "1.4.0",
  computedAt: "2026-11-23T10:00:00Z",
  valueIndex: 0.4912,
  referenceValue: 6.1234,
  referenceCredits: 6,
  referenceBudget: 1000,
  roleTop: 30,
  floor: 1,
  curveExponent: 2.4,
  missingSeasonIndex: 0.33,
  shrinkAppearances: 8,
  currentFullWeightAppearances: 15,
  baseReferenceValue: 3.02,
  seasons: [
    season({
      slot: "current",
      seasonYear: 2026,
      seasonLabel: "26/27",
      isCurrent: true,
      source: "fantappero",
      competitions: ["Premier League"],
      appearances: 15,
      average: 6.68,
      weight: 0.5,
      indexUsed: 0.4,
      percentile: 0.4,
    }),
    season({ weight: 0.3, indexUsed: 0.62 }),
    season({
      slot: "twoSeasonsAgo",
      seasonYear: 2024,
      seasonLabel: "24/25",
      competitions: ["Ligue 1"],
      weight: 0.2,
      indexUsed: 0.55,
      percentile: 0.55,
    }),
  ],
  league: null,
};

describe("formattazione", () => {
  it("usa la virgola e i decimali chiesti", () => {
    assert.equal(formatValueNumber(7.034), "7,03");
    assert.equal(formatValueNumber(0.4912), "0,49");
    assert.equal(formatValueNumber(6.1234, 1), "6,1");
    assert.equal(formatValueNumber(-0.001), "0,00");
    assert.equal(formatValueNumber(Number.NaN), "—");
  });

  it("pesi in percentuale e percentili come posizione", () => {
    assert.equal(formatWeightPercent(0.3), "30%");
    assert.equal(formatWeightPercent(0.5 * (7 / 15)), "23,3%");
    assert.equal(formatWeightPercent(0), "0%");
    assert.equal(formatPercentileOrdinal(0.62), "62°");
    assert.equal(formatPercentileOrdinal(0.9984), "100°");
    assert.equal(marketValueSeasonName(2025), "2025/26");
    assert.equal(marketValueSeasonName(2099), "2099/00");
  });

  it("crediti per un budget come il backend (arrotondati, almeno 1)", () => {
    assert.equal(marketValueCreditsForBudget(6.1234, 1000), 6);
    assert.equal(marketValueCreditsForBudget(6.1234, 500), 3);
    assert.equal(marketValueCreditsForBudget(5, 500), 3); // 2,5 → 3
    assert.equal(marketValueCreditsForBudget(1.2, 100), 1);
  });
});

describe("frasi del dettaglio", () => {
  it("una stagione del fornitore in una frase", () => {
    assert.equal(
      marketValueSeasonSentence(season({}), "P"),
      "Stagione 2025/26 (fornitore, Premier League): 34 presenze, media 7,03 → media ristretta 6,98 (media dei portieri 6,88) → 62° percentile fra 180 portieri, 69° posto → peso 30%",
    );
  });

  it("la stagione in corso conta le partite con voto", () => {
    const current = DETAIL.seasons[0]!;
    assert.match(
      marketValueSeasonSentence(current, "P"),
      /^Stagione 2026\/27 \(FantApperò, Premier League\): 15 partite con voto, media 6,68 → .* → peso 50%$/,
    );
    assert.equal(
      marketValueSeasonSentence(
        season({ isCurrent: true, seasonYear: 2026, source: null, competitions: [], hasData: false, weight: 0 }),
        "P",
      ),
      "Stagione 2026/27: nessun voto FantApperò quest'anno → peso 0%",
    );
  });

  it("una stagione senza dati vale 0,33 e dice perché", () => {
    const onlyCups = season({
      hasData: false,
      competitions: [],
      average: null,
      percentile: null,
      shrunkAverage: null,
      appearances: 0,
      weight: 0.4,
      indexUsed: 0.33,
      excluded: [
        { competition: "UEFA Champions League", club: "PSG", appearances: 10, average: 7.4, kind: "cup" },
      ],
    });
    assert.equal(
      marketValueSeasonSentence(onlyCups, "P"),
      "Stagione 2025/26 (fornitore): nessuna riga di campionato con media → vale 0,33 come una stagione senza dati (sotto la mediana) → peso 40%",
    );
    assert.equal(
      marketValueExcludedText(onlyCups),
      "Non contano: UEFA Champions League (coppa, 10 presenze, media 7,40)",
    );
    assert.equal(marketValueExcludedText(season({})), null);
  });

  it("p, curva, budget e valore base", () => {
    assert.equal(
      marketValueIndexSentence(DETAIL),
      "Indice combinato p = 50% × 0,40 + 30% × 0,62 + 20% × 0,55 = 0,49",
    );
    assert.equal(
      marketValueCurveSentence(DETAIL),
      "Curva dei portieri: 1 + (30 − 1) × 0,49^2,4 = 6,1 crediti a budget 1000 → 6 crediti",
    );
    assert.equal(
      marketValueBudgetSentence(DETAIL, 500),
      "Lega da 500 crediti: 6,1 × 500 / 1000 = 3,06 → 3 crediti",
    );
    assert.equal(
      marketValueBudgetSentence(DETAIL, 500, "Lega Amici"),
      "«Lega Amici» (budget 500): 6,1 × 500 / 1000 = 3,06 → 3 crediti",
    );
    assert.equal(marketValueBaseSentence(DETAIL), "Valore base dei portieri (nessuno storico, p = 0,33): 3 crediti");
  });

  it("avvisa per righe vecchie o mancanti", () => {
    assert.equal(marketValueStatusText(DETAIL), null);
    assert.match(marketValueStatusText({ ...DETAIL, status: "outdated" }) ?? "", /Ricalcola valori/);
    assert.match(marketValueStatusText({ ...DETAIL, status: "not_computed" }) ?? "", /valore base/);
  });
});
