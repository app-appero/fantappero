/**
 * Invio di una nuova proposta di scambio: `true` solo se il server l'ha accettata. Con un
 * errore (es. 400 `market_round_in_progress`) il messaggio passa a `onError` e si risponde
 * `false`: il chiamante lascia aperto il form «Nuova proposta», con quanto compilato e il
 * messaggio del server, invece di chiuderlo come se l'invio fosse andato (QA 20-21/11).
 */
export async function submitTrade(
  send: () => Promise<unknown>,
  onError: (error: unknown) => void,
): Promise<boolean> {
  try {
    await send();
    return true;
  } catch (error) {
    onError(error);
    return false;
  }
}
