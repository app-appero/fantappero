import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  OFFER_MINIMUM_CREDITS,
  liveRaiseOptions,
  manualAddMinimum,
  offerPrefillHint,
  priceCaption,
  pricePrefill,
  suggestedDraft,
  syncPriceDraft,
  valueOverCreditsNote,
} from "./pricePrefill.ts";

describe("prezzo che parte dal Valore", () => {
  it("Valore entro i crediti: parte dal Valore, senza riga", () => {
    assert.deepEqual(pricePrefill({ marketValue: 24, remainingCredits: 40, minimum: 1 }), {
      price: 24,
      capped: false,
      note: null,
    });
    assert.equal(pricePrefill({ marketValue: 40, remainingCredits: 40, minimum: 1 })?.capped, false);
  });

  it("Valore oltre i crediti: parte dai crediti rimasti con «Valore N: hai solo X crediti»", () => {
    assert.deepEqual(pricePrefill({ marketValue: 58, remainingCredits: 40, minimum: 1 }), {
      price: 40,
      capped: true,
      note: "Valore 58: hai solo 40 crediti",
    });
    assert.equal(valueOverCreditsNote(58, 1), "Valore 58: hai solo 1 credito");
  });

  it("senza Valore il campo fa come oggi", () => {
    assert.equal(pricePrefill({ marketValue: null, remainingCredits: 40, minimum: 1 }), null);
    assert.equal(pricePrefill({ marketValue: undefined, remainingCredits: 40, minimum: 1 }), null);
    // Aggiunta manuale: da 1; offerte: campo vuoto.
    assert.equal(suggestedDraft(null, "1"), "1");
    assert.equal(suggestedDraft(null, ""), "");
    assert.equal(offerPrefillHint(null), null);
  });

  it("crediti non ancora noti: parte dal Valore", () => {
    assert.deepEqual(pricePrefill({ marketValue: 58, remainingCredits: null, minimum: 1 }), {
      price: 58,
      capped: false,
      note: null,
    });
  });

  it("restano i minimi di oggi: partecipante almeno 1, amministratore anche 0", () => {
    assert.equal(manualAddMinimum(false), 1);
    assert.equal(manualAddMinimum(true), 0);
    assert.equal(OFFER_MINIMUM_CREDITS, 1);
    // Nessun credito rimasto: il partecipante parte da 1, l'amministratore da 0.
    assert.deepEqual(pricePrefill({ marketValue: 12, remainingCredits: 0, minimum: manualAddMinimum(false) }), {
      price: 1,
      capped: true,
      note: "Valore 12: hai solo 0 crediti",
    });
    assert.deepEqual(pricePrefill({ marketValue: 12, remainingCredits: 0, minimum: manualAddMinimum(true) }), {
      price: 0,
      capped: true,
      note: "Valore 12: hai solo 0 crediti",
    });
    // Valore 0 (mai sotto il minimo del partecipante).
    assert.equal(pricePrefill({ marketValue: 0, remainingCredits: 40, minimum: 1 })?.price, 1);
    assert.equal(pricePrefill({ marketValue: 0, remainingCredits: 40, minimum: 0 })?.price, 0);
  });

  it("didascalia e riga dell'offerta come nel canvas", () => {
    const capped = pricePrefill({ marketValue: 58, remainingCredits: 40, minimum: 1 });
    const free = pricePrefill({ marketValue: 24, remainingCredits: 40, minimum: 1 });
    assert.equal(priceCaption("40", capped), "massimo");
    assert.equal(priceCaption("24", free), "consigliato");
    assert.equal(priceCaption("30", free), "crediti");
    assert.equal(priceCaption("1", null), "crediti");
    assert.equal(offerPrefillHint(capped), "Valore 58: hai solo 40 crediti");
    assert.equal(offerPrefillHint(free), "Proposta in base al Valore: puoi offrire di più o di meno.");
  });
});

describe("il campo segue il prezzo proposto finché non lo cambi", () => {
  it("campo ancora al prezzo proposto: prende quello nuovo", () => {
    assert.equal(syncPriceDraft({ draft: "1", previousSuggestion: "1", suggestion: "24" }), "24");
    assert.equal(syncPriceDraft({ draft: "", previousSuggestion: "", suggestion: "58" }), "58");
    // Altro calciatore senza Valore: torna come oggi.
    assert.equal(syncPriceDraft({ draft: "58", previousSuggestion: "58", suggestion: "" }), "");
  });

  it("cifra scritta dall'utente: resta la sua", () => {
    assert.equal(syncPriceDraft({ draft: "30", previousSuggestion: "24", suggestion: "40" }), "30");
    assert.equal(syncPriceDraft({ draft: "45", previousSuggestion: "", suggestion: "58" }), "45");
  });
});

describe("asta live: il Valore è solo mostrato", () => {
  it("i rilanci partono dal prezzo del lotto, mai dal Valore", () => {
    const withValue = liveRaiseOptions({ currentAmountCredits: 10, marketValue: 58 }, 11);
    const withoutValue = liveRaiseOptions({ currentAmountCredits: 10 }, 11);
    assert.deepEqual(withValue, withoutValue);
    assert.deepEqual(withValue, {
      minimum: 11,
      quick: [
        { step: 1, amount: 11 },
        { step: 5, amount: 15 },
        { step: 10, amount: 20 },
      ],
    });
    assert.ok(withValue.quick.every((raise) => raise.amount !== 58));
  });

  it("primo rilancio sotto il minimo: vale il minimo", () => {
    assert.deepEqual(
      liveRaiseOptions({ currentAmountCredits: 1, marketValue: 3 }, 5).quick.map((raise) => raise.amount),
      [5, 6, 11],
    );
  });
});
