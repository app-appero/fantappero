import type { TradeAthlete, TradeProposal } from "@fantappero/contracts";

// Conferma prima di accettare una proposta di scambio (QA 19/11: un tocco
// accidentale su «Accetta» ha eseguito uno scambio). L'accettazione sposta
// subito calciatori e crediti e non si può annullare, quindi si chiede conferma.
// Stessi testi del web (apps/web/src/market/tradeAcceptConfirm.ts).

/** Titolo della conferma. */
export const TRADE_ACCEPT_CONFIRM_TITLE = "Accettare lo scambio?";

/** Pulsante che accetta davvero la proposta. */
export const TRADE_ACCEPT_CONFIRM_LABEL = "Accetta scambio";

/** Pulsante che chiude la conferma senza fare nulla. */
export const TRADE_ACCEPT_CANCEL_LABEL = "Indietro";

const TRADE_ACCEPT_WARNING = "Una volta accettato non potrai annullarlo.";

type TradeAcceptProposal = Pick<
  TradeProposal,
  | "proposerTeamId"
  | "recipientTeamId"
  | "offeredAthletes"
  | "requestedAthletes"
  | "offeredCredits"
  | "requestedCredits"
>;

function creditsLabel(credits: number): string {
  return credits === 1 ? "1 credito" : `${credits} crediti`;
}

/**
 * Una parte dello scambio come nella scheda della proposta: i nomi separati da
 * virgola, poi «+ N crediti» se si muovono crediti. Stringa vuota se la parte è vuota.
 */
function tradeSideSummary(athletes: TradeAthlete[], credits: number): string {
  const names = athletes.map((athlete) => athlete.name?.trim() || "Giocatore").join(", ");
  const amount = credits > 0 ? creditsLabel(credits) : "";
  if (names && amount) {
    return `${names} + ${amount}`;
  }
  return names || amount;
}

/**
 * Testo della conferma: «Riceverai X e cederai Y. Una volta accettato non
 * potrai annullarlo.». Con l'approvazione dell'admin attiva lo scambio
 * avviene solo dopo la sua decisione. Chi accetta è il destinatario, che riceve ciò che il
 * proponente offre e cede ciò che chiede; se `myTeamId` è il proponente i due
 * lati si invertono.
 */
export function tradeAcceptConfirmMessage(
  proposal: TradeAcceptProposal,
  myTeamId: string | null | undefined,
): string {
  const iAmProposer =
    myTeamId != null && myTeamId === proposal.proposerTeamId && myTeamId !== proposal.recipientTeamId;
  const offered = tradeSideSummary(proposal.offeredAthletes, proposal.offeredCredits);
  const requested = tradeSideSummary(proposal.requestedAthletes, proposal.requestedCredits);
  const receive = iAmProposer ? requested : offered;
  const give = iAmProposer ? offered : requested;

  let summary = "";
  if (receive && give) {
    summary = `Riceverai ${receive} e cederai ${give}.`;
  } else if (receive) {
    summary = `Riceverai ${receive} senza cedere nulla.`;
  } else if (give) {
    summary = `Cederai ${give} senza ricevere nulla.`;
  }
  return summary ? `${summary} ${TRADE_ACCEPT_WARNING}` : TRADE_ACCEPT_WARNING;
}
