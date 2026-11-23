/**
 * Valore di mercato e media stagionale nelle righe del mercato (release 1.3, decisioni di
 * Rosario del 21–22/11, canvas «Proposte 1.3»). Solo logica pura: i componenti sono in
 * `AthleteValueTags.tsx`.
 *
 * - Media verde se è della stagione in corso («6,45»), rossa con la stagione se è quella della
 *   stagione scorsa («6,12 · 25/26»), niente (o «—») se manca.
 * - «Valore N» solo se il backend lo manda.
 * - Il prezzo dell'aggiunta manuale e delle offerte (buste, svincolati) parte dal Valore; se il
 *   Valore supera i crediti rimasti parte dai crediti rimasti, con la riga «Valore N: hai solo X
 *   crediti». Restano i minimi di oggi (partecipante almeno 1, admin anche 0). Asta live: il
 *   Valore è solo mostrato, mai precompilato.
 */
import type { AthleteMarketFields, AthleteSeasonAverage } from "@fantappero/contracts";

const AVERAGE_FORMAT = new Intl.NumberFormat("it-IT", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Minimo del prezzo d'acquisto nell'aggiunta manuale: partecipante 1, admin anche 0. */
export const MANUAL_PRICE_MINIMUM = { participant: 1, admin: 0 } as const;

/** Minimo di un'offerta (asta a buste e svincolati): 1 credito per tutti, come il backend. */
export const OFFER_PRICE_MINIMUM = 1;

export function manualPriceMinimum(isAdmin: boolean): number {
  return isAdmin ? MANUAL_PRICE_MINIMUM.admin : MANUAL_PRICE_MINIMUM.participant;
}

export type SeasonAverageTone = "current" | "previous";

export type SeasonAverageDisplay = {
  /** «6,45» (stagione in corso) oppure «6,12 · 25/26» (stagione scorsa). */
  text: string;
  tone: SeasonAverageTone;
  /** Spiegazione per il tooltip e lo screen reader. */
  title: string;
};

/** «2026/27» dall'anno d'inizio (le righe del mercato usano la forma corta «25/26»). */
export function fullSeasonLabel(seasonYear: number): string {
  return `${seasonYear}/${String((seasonYear + 1) % 100).padStart(2, "0")}`;
}

/** Media con la virgola e due decimali: 6.45 → «6,45». */
export function formatAverageValue(value: number): string {
  return AVERAGE_FORMAT.format(value);
}

export function formatSeasonAverage(
  average: AthleteSeasonAverage | null | undefined,
): SeasonAverageDisplay | null {
  if (!average || typeof average.value !== "number" || !Number.isFinite(average.value)) {
    return null;
  }
  const number = formatAverageValue(average.value);
  if (average.isCurrent) {
    return {
      text: number,
      tone: "current",
      title: `Media voto della stagione in corso (${average.seasonLabel})`,
    };
  }
  return {
    text: `${number} · ${average.seasonLabel}`,
    tone: "previous",
    title: `Media voto della stagione ${average.seasonLabel}: quest'anno non ha ancora voti`,
  };
}

export function hasMarketValue(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** «Valore 58», `null` se il calciatore non ha Valore (o il backend è più vecchio). */
export function marketValueLabel(value: number | null | undefined): string | null {
  return hasMarketValue(value) ? `Valore ${value}` : null;
}

/** C'è almeno un Valore o una media: altrimenti (backend più vecchio) non si aggiunge nulla. */
export function hasMarketData(entries: readonly AthleteMarketFields[]): boolean {
  return entries.some(
    (entry) => hasMarketValue(entry.marketValue) || formatSeasonAverage(entry.seasonAverage) !== null,
  );
}

export function creditsLabel(credits: number): string {
  return credits === 1 ? "1 credito" : `${credits} crediti`;
}

/** La riga decisa il 21/11: «Valore 58: hai solo 40 crediti». */
export function valueOverCreditsLine(value: number, credits: number): string {
  return `Valore ${value}: hai solo ${creditsLabel(credits)}`;
}

export type PricePrefill = {
  /** Prezzo da cui parte il campo (modificabile). */
  price: number;
  /** Il Valore supera i crediti rimasti: il prezzo parte dai crediti. */
  capped: boolean;
  /** «Valore 58: hai solo 40 crediti» quando `capped`, altrimenti `null`. */
  notice: string | null;
};

/**
 * Prezzo di partenza dal Valore. `null` se il calciatore non ha Valore: si tiene il
 * comportamento di oggi (1 nell'aggiunta manuale, campo vuoto nelle offerte). Con crediti
 * sconosciuti (`null`) parte dal Valore.
 */
export function marketValuePrefill({
  marketValue,
  remainingCredits,
  minimum,
}: {
  marketValue: number | null | undefined;
  remainingCredits: number | null | undefined;
  minimum: number;
}): PricePrefill | null {
  if (!hasMarketValue(marketValue)) {
    return null;
  }
  const credits =
    typeof remainingCredits === "number" && Number.isFinite(remainingCredits)
      ? Math.max(0, Math.floor(remainingCredits))
      : null;
  if (credits !== null && marketValue > credits) {
    return {
      price: Math.max(minimum, credits),
      capped: true,
      notice: valueOverCreditsLine(marketValue, credits),
    };
  }
  return { price: Math.max(minimum, marketValue), capped: false, notice: null };
}

/** Campo offerta: il testo e se viene ancora dal Valore (non toccato da chi offre). */
export type BidDraft = { amount: string; fromValue: boolean };

export const EMPTY_BID_DRAFT: BidDraft = { amount: "", fromValue: false };

/**
 * Offerta dopo la scelta di un calciatore (buste e svincolati): parte dal Valore. Senza Valore
 * resta quello che c'era, come oggi, tranne un numero messo dal Valore del calciatore di prima
 * e mai toccato, che torna vuoto.
 */
export function bidDraftForSelection(current: BidDraft, prefill: PricePrefill | null): BidDraft {
  if (prefill) {
    return { amount: String(prefill.price), fromValue: true };
  }
  return current.fromValue ? EMPTY_BID_DRAFT : current;
}

/** Riga sotto il campo offerta: perché parte da lì. `null` se il calciatore non ha Valore. */
export function offerPrefillHint(prefill: PricePrefill | null): string | null {
  if (!prefill) {
    return null;
  }
  if (prefill.capped && prefill.notice) {
    return `${prefill.notice}, l'offerta parte da ${prefill.price}.`;
  }
  return "Proposta in base al Valore. Puoi offrire di più o di meno.";
}
