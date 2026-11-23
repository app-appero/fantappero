/**
 * Fantallenatori: i conteggi accanto alla directory (posti, iscritti, inviti in attesa) si
 * chiedono solo quando la schermata li mostra, cioè all'amministratore della lega, con sessione e
 * lega attive. Un semplice partecipante vede «Permessi insufficienti»: prima la schermata chiedeva
 * comunque amministrazione e partecipanti, che rispondevano 403 (QA 22→23/11).
 */
export function directoryCountsRequest(input: {
  isAdmin: boolean;
  accessToken: string | null | undefined;
  leagueId: string | null | undefined;
}): { accessToken: string; leagueId: string } | null {
  if (!input.isAdmin || !input.accessToken || !input.leagueId) {
    return null;
  }
  return { accessToken: input.accessToken, leagueId: input.leagueId };
}
