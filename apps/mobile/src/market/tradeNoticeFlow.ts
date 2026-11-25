import type { TradeAfterNotice, TradePreviewRequest } from "@fantappero/contracts";

/**
 * Avvisi prima di uno scambio nell'app (1.5 e corsa Mercato del 25/11): quando chiedere
 * l'anteprima al server e come confermare. I testi sono in `@fantappero/contracts`
 * (`tradeAfterNotice`), qui solo le scelte dell'app, uguali a quelle del sito.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`.
 */

export type TradeCreditsDirection = "offer" | "request";

/** Crediti offerti o chiesti dal campo «Crediti» del form (un solo verso alla volta). */
export function tradeCreditsSplit(
  direction: TradeCreditsDirection,
  amount: string | number,
): { offeredCredits: number; requestedCredits: number } {
  const credits = Math.max(0, Math.trunc(Number(amount) || 0));
  return direction === "offer"
    ? { offeredCredits: credits, requestedCredits: 0 }
    : { offeredCredits: 0, requestedCredits: credits };
}

/**
 * La bozza da mandare all'anteprima (`POST …/mercato/scambi/anteprima`) prima di proporre o
 * controproporre, con i crediti (servono ai crediti dopo lo scambio); `null` se non si muove
 * nessun calciatore (la rosa resta com'è: niente da avvisare) o manca la squadra destinataria.
 */
export function tradePreviewDraft(input: {
  recipientTeamId: string | null | undefined;
  offeredAthleteIds: readonly string[];
  requestedAthleteIds: readonly string[];
  direction: TradeCreditsDirection;
  amount: string | number;
}): TradePreviewRequest | null {
  if (!input.recipientTeamId) {
    return null;
  }
  if (input.offeredAthleteIds.length === 0 && input.requestedAthleteIds.length === 0) {
    return null;
  }
  return {
    recipientTeamId: input.recipientTeamId,
    offeredAthleteIds: [...input.offeredAthleteIds],
    requestedAthleteIds: [...input.requestedAthleteIds],
    ...tradeCreditsSplit(input.direction, input.amount),
  };
}

/**
 * Come si conferma «Accetta»: `alert` (finestra di sistema di sempre) senza avvisi; `short` con
 * il foglio dal basso e «Accetta e scegli» se mancano giocatori; `info` con il foglio dal basso e
 * il pulsante di sempre se c'è solo la riga dei ruoli sotto quota.
 */
export type TradeAcceptConfirmMode = "alert" | "short" | "info";

export function tradeAcceptConfirmMode(
  notice: Pick<TradeAfterNotice, "tone"> | null | undefined,
): TradeAcceptConfirmMode {
  if (!notice) {
    return "alert";
  }
  return notice.tone === "warning" ? "short" : "info";
}
