import type { LeagueState } from "@fantappero/contracts";

export const LEAGUE_STATE_LABELS: Record<LeagueState, string> = {
  draft: "Bozza",
  configuring: "Configurazione",
  auction: "Asta",
  active: "Attiva",
  concluded: "Conclusa",
  archived: "Archiviata",
};

function isLeagueState(state: string): state is LeagueState {
  return Object.prototype.hasOwnProperty.call(LEAGUE_STATE_LABELS, state);
}

/**
 * Etichetta dello stato di una lega ("Attiva", …), come `leagueStateLabel` del web.
 * Accetta anche una stringa libera (il pannello operatore riceve `AdminLeague.state`
 * come `string`): uno stato che l'app non conosce ancora resta visibile col suo codice.
 */
export function leagueStateLabel(state: LeagueState | string | null | undefined): string {
  if (!state) {
    return "—";
  }
  return isLeagueState(state) ? LEAGUE_STATE_LABELS[state] : state;
}
