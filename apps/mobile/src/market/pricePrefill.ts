/**
 * Prezzo che parte dal Valore (decisione di Rosario del 21/11, canvas «Proposte 1.3»).
 *
 * - Aggiunta manuale dal listone della Rosa e offerte (asta a buste, svincoli): il prezzo parte
 *   dal Valore invece che da 1 ed è modificabile.
 * - Valore oltre i crediti rimasti: parte dai crediti rimasti, con la riga
 *   «Valore N: hai solo X crediti».
 * - Restano i minimi di oggi: il partecipante almeno 1 credito, l'amministratore anche 0
 *   (aggiunta manuale). Le offerte restano da almeno 1.
 * - Senza Valore il campo fa come oggi.
 * - Asta live: il Valore è solo mostrato, i rilanci partono dal prezzo del lotto
 *   (`liveRaiseOptions`).
 *
 * Solo logica pura e import di tipo (nessun import a runtime, nemmeno locale): gira nei test
 * `node:test`.
 */
import type { AthleteMarketFields, LiveLot } from "@fantappero/contracts";

/** Valore usabile (intero non negativo) o `null`; come `usableMarketValue` di `athleteValue.ts`. */
function usableValue(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return Math.round(value);
}

/** Minimo dell'aggiunta manuale: partecipante 1, amministratore 0 (come il backend). */
export function manualAddMinimum(isAdmin: boolean): number {
  return isAdmin ? 0 : 1;
}

/** Minimo di un'offerta di asta a buste o svincoli (il backend vuole almeno 1). */
export const OFFER_MINIMUM_CREDITS = 1;

export type PricePrefillInput = {
  marketValue?: number | null;
  /** Crediti rimasti della squadra che paga; `null` se non ancora noti. */
  remainingCredits?: number | null;
  minimum: number;
};

export type PricePrefill = {
  /** Prezzo proposto nel campo. */
  price: number;
  /** Il Valore supera i crediti rimasti: il prezzo parte dai crediti. */
  capped: boolean;
  /** «Valore 58: hai solo 40 crediti» quando `capped`, altrimenti `null`. */
  note: string | null;
};

function creditsWord(amount: number): string {
  return amount === 1 ? "credito" : "crediti";
}

/** «Valore 58: hai solo 40 crediti». */
export function valueOverCreditsNote(marketValue: number, remainingCredits: number): string {
  return `Valore ${marketValue}: hai solo ${remainingCredits} ${creditsWord(remainingCredits)}`;
}

/** Prezzo proposto dal Valore; `null` senza Valore (il campo resta come oggi). */
export function pricePrefill({ marketValue, remainingCredits, minimum }: PricePrefillInput): PricePrefill | null {
  const value = usableValue(marketValue);
  if (value === null) {
    return null;
  }
  const credits =
    typeof remainingCredits === "number" && Number.isFinite(remainingCredits) ? Math.floor(remainingCredits) : null;
  if (credits !== null && value > credits) {
    return {
      price: Math.max(minimum, credits),
      capped: true,
      note: valueOverCreditsNote(value, credits),
    };
  }
  return { price: Math.max(minimum, value), capped: false, note: null };
}

/** Testo del campo prezzo per un prezzo proposto: il prezzo, o `fallback` (oggi: «1» o vuoto). */
export function suggestedDraft(prefill: PricePrefill | null, fallback: string): string {
  return prefill ? String(prefill.price) : fallback;
}

/**
 * Il prezzo proposto è cambiato (altro calciatore, Valore ricalcolato, crediti arrivati o
 * scesi): se il campo ha ancora il prezzo proposto di prima lo aggiorna, se l'utente l'ha
 * cambiato resta il suo.
 */
export function syncPriceDraft({
  draft,
  previousSuggestion,
  suggestion,
}: {
  draft: string;
  previousSuggestion: string;
  suggestion: string;
}): string {
  return draft.trim() === previousSuggestion.trim() ? suggestion : draft;
}

/** Didascalia sotto il campo prezzo della riga del listone (canvas: «consigliato» / «massimo»). */
export function priceCaption(draft: string, prefill: PricePrefill | null): string {
  if (prefill && draft.trim() === String(prefill.price)) {
    return prefill.capped ? "massimo" : "consigliato";
  }
  return "crediti";
}

/** Riga sotto il campo dell'offerta: il motivo del prezzo proposto (canvas). */
export function offerPrefillHint(prefill: PricePrefill | null): string | null {
  if (!prefill) {
    return null;
  }
  return prefill.capped ? prefill.note : "Proposta in base al Valore: puoi offrire di più o di meno.";
}

// --- Asta live: il Valore è solo mostrato -----------------------------------------------------

export type LiveRaiseOptions = {
  /** «Rilancia a N». */
  minimum: number;
  /** Bottoni +1, +5, +10. */
  quick: Array<{ step: number; amount: number }>;
};

export const LIVE_QUICK_STEPS = [1, 5, 10] as const;

/**
 * Rilanci dell'asta live dal prezzo attuale del lotto e dal rilancio minimo
 * (`computeMinimumNextBid` dei contratti): il Valore del lotto non entra mai nei rilanci.
 */
export function liveRaiseOptions(
  lot: Pick<LiveLot, "currentAmountCredits"> & AthleteMarketFields,
  minimumNextBid: number,
): LiveRaiseOptions {
  return {
    minimum: minimumNextBid,
    quick: LIVE_QUICK_STEPS.map((step) => ({
      step,
      amount: Math.max(minimumNextBid, lot.currentAmountCredits + step),
    })),
  };
}
