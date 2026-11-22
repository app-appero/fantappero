import type { AthleteSeasonAverage } from "@fantappero/contracts";
import { describe, expect, it } from "vitest";
import {
  EMPTY_BID_DRAFT,
  OFFER_PRICE_MINIMUM,
  bidDraftForSelection,
  formatSeasonAverage,
  fullSeasonLabel,
  hasMarketData,
  manualPriceMinimum,
  marketValueLabel,
  marketValuePrefill,
  offerPrefillHint,
  valueOverCreditsLine,
} from "./athleteValue";

const CURRENT: AthleteSeasonAverage = { value: 6.45, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true };
const PREVIOUS: AthleteSeasonAverage = { value: 6.12, seasonYear: 2025, seasonLabel: "25/26", isCurrent: false };

describe("media stagionale nelle righe del mercato (1.3)", () => {
  it("verde con solo il numero se è della stagione in corso", () => {
    expect(formatSeasonAverage(CURRENT)).toEqual({
      text: "6,45",
      tone: "current",
      title: "Media voto della stagione in corso (26/27)",
    });
  });

  it("rossa con la stagione se è quella della stagione scorsa", () => {
    const display = formatSeasonAverage(PREVIOUS);
    expect(display?.text).toBe("6,12 · 25/26");
    expect(display?.tone).toBe("previous");
  });

  it("due decimali con la virgola", () => {
    expect(formatSeasonAverage({ ...CURRENT, value: 6 })?.text).toBe("6,00");
    expect(formatSeasonAverage({ ...CURRENT, value: 6.456 })?.text).toBe("6,46");
  });

  it("niente media: null (backend vecchio, campo assente o valore non numerico)", () => {
    expect(formatSeasonAverage(null)).toBeNull();
    expect(formatSeasonAverage(undefined)).toBeNull();
    expect(formatSeasonAverage({ ...CURRENT, value: Number.NaN })).toBeNull();
  });

  it("«Valore N» solo se il Valore c'è", () => {
    expect(marketValueLabel(58)).toBe("Valore 58");
    expect(marketValueLabel(null)).toBeNull();
    expect(marketValueLabel(undefined)).toBeNull();
  });

  it("riconosce un listone senza dati 1.3 (backend più vecchio)", () => {
    expect(hasMarketData([{}, { marketValue: null, seasonAverage: null }])).toBe(false);
    expect(hasMarketData([{}, { marketValue: 3 }])).toBe(true);
    expect(hasMarketData([{ seasonAverage: PREVIOUS }])).toBe(true);
  });

  it("stagione lunga per carriera e pannello operatore", () => {
    expect(fullSeasonLabel(2026)).toBe("2026/27");
    expect(fullSeasonLabel(2099)).toBe("2099/00");
  });
});

describe("prezzo che parte dal Valore (decisione del 21/11)", () => {
  it("Valore sotto i crediti: parte dal Valore, nessuna riga", () => {
    expect(marketValuePrefill({ marketValue: 24, remainingCredits: 40, minimum: 1 })).toEqual({
      price: 24,
      capped: false,
      notice: null,
    });
  });

  it("Valore uguale ai crediti: parte dal Valore", () => {
    expect(marketValuePrefill({ marketValue: 40, remainingCredits: 40, minimum: 1 })?.price).toBe(40);
  });

  it("Valore sopra i crediti: parte dai crediti rimasti con «Valore N: hai solo X crediti»", () => {
    expect(marketValuePrefill({ marketValue: 58, remainingCredits: 40, minimum: 1 })).toEqual({
      price: 40,
      capped: true,
      notice: "Valore 58: hai solo 40 crediti",
    });
    expect(valueOverCreditsLine(5, 1)).toBe("Valore 5: hai solo 1 credito");
  });

  it("senza Valore resta il comportamento di oggi (nessuna proposta)", () => {
    expect(marketValuePrefill({ marketValue: null, remainingCredits: 40, minimum: 1 })).toBeNull();
    expect(marketValuePrefill({ marketValue: undefined, remainingCredits: 40, minimum: 1 })).toBeNull();
  });

  it("crediti non noti: parte dal Valore", () => {
    expect(marketValuePrefill({ marketValue: 12, remainingCredits: null, minimum: 1 })?.price).toBe(12);
  });

  it("restano i minimi di oggi: admin anche 0, partecipante almeno 1", () => {
    expect(manualPriceMinimum(true)).toBe(0);
    expect(manualPriceMinimum(false)).toBe(1);
    expect(marketValuePrefill({ marketValue: 8, remainingCredits: 0, minimum: manualPriceMinimum(true) })).toEqual({
      price: 0,
      capped: true,
      notice: "Valore 8: hai solo 0 crediti",
    });
    expect(
      marketValuePrefill({ marketValue: 8, remainingCredits: 0, minimum: manualPriceMinimum(false) })?.price,
    ).toBe(1);
    expect(OFFER_PRICE_MINIMUM).toBe(1);
  });
});

describe("campo offerta di buste e svincolati", () => {
  const prefill = marketValuePrefill({ marketValue: 58, remainingCredits: 40, minimum: 1 });

  it("scegliendo un calciatore con Valore l'offerta parte da lì", () => {
    expect(bidDraftForSelection(EMPTY_BID_DRAFT, prefill)).toEqual({ amount: "40", fromValue: true });
    expect(bidDraftForSelection({ amount: "12", fromValue: false }, prefill)).toEqual({
      amount: "40",
      fromValue: true,
    });
  });

  it("senza Valore resta quello che hai scritto, ma non il numero del calciatore di prima", () => {
    expect(bidDraftForSelection({ amount: "12", fromValue: false }, null)).toEqual({
      amount: "12",
      fromValue: false,
    });
    expect(bidDraftForSelection({ amount: "40", fromValue: true }, null)).toEqual(EMPTY_BID_DRAFT);
  });

  it("la riga sotto il campo spiega da dove parte l'offerta", () => {
    expect(offerPrefillHint(prefill)).toBe("Valore 58: hai solo 40 crediti, l'offerta parte da 40.");
    expect(offerPrefillHint(marketValuePrefill({ marketValue: 24, remainingCredits: 40, minimum: 1 }))).toBe(
      "Proposta in base al Valore. Puoi offrire di più o di meno.",
    );
    expect(offerPrefillHint(null)).toBeNull();
  });
});
