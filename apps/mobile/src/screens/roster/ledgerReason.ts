/** Etichetta italiana di una causale del registro crediti (codice backend `CreditLedgerReason`). */
export function reasonLabel(reason: string): string {
  if (reason === "initial_allocation") {
    return "Allocazione iniziale";
  }
  if (reason === "admin_adjustment") {
    return "Aggiustamento admin";
  }
  if (reason === "roster_purchase") {
    return "Acquisto rosa";
  }
  if (reason === "roster_release_refund") {
    return "Rimborso rosa";
  }
  if (reason === "market_auction_win") {
    return "Asta vinta";
  }
  if (reason === "market_waiver_acquisition") {
    return "Acquisto da svincolati";
  }
  if (reason === "market_release_refund") {
    return "Rimborso svincolo";
  }
  if (reason === "market_trade_credits_sent") {
    return "Crediti inviati per scambio";
  }
  if (reason === "market_trade_credits_received") {
    return "Crediti ricevuti da scambio";
  }
  return reason;
}
