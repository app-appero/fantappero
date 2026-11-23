import type { LeagueState } from "@fantappero/contracts";

/** Hard-delete allowed only before auction/season start (EP03-05-EXT). */
export const DELETABLE_LEAGUE_STATES = new Set<LeagueState>(["draft", "configuring"]);

export function isLeagueDeletable(state: LeagueState | undefined): boolean {
  return state !== undefined && DELETABLE_LEAGUE_STATES.has(state);
}

/**
 * Pila di navigazione dopo «Elimina lega»: le schede dell'app e sopra la Home lega (della lega
 * rimasta attiva, o «Nessuna lega selezionata»). Con `navigate("LeagueHome")` la Home si
 * aggiungeva sopra Amministrazione della lega eliminata e «indietro» tornava lì, su «Lega non
 * trovata» (QA 23/11). Nessuna schermata della lega eliminata resta nella pila.
 */
export function stackAfterLeagueDeleted() {
  return {
    index: 1,
    routes: [{ name: "MainTabs" as const }, { name: "LeagueHome" as const }],
  };
}
