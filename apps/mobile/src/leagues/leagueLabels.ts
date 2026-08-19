import type { LeagueState } from "@fantappero/contracts";

export const LEAGUE_STATE_LABELS: Record<LeagueState, string> = {
  draft: "Bozza",
  configuring: "Configurazione",
  auction: "Asta",
  active: "Attiva",
  concluded: "Conclusa",
  archived: "Archiviata",
};

export function leagueStateLabel(state: LeagueState | undefined): string {
  return state ? LEAGUE_STATE_LABELS[state] : "—";
}
