import type { LeagueState } from "@fantappero/contracts";

const STATE_LABELS: Record<LeagueState, string> = {
  draft: "Bozza",
  configuring: "Configurazione",
  auction: "Asta",
  active: "Attiva",
  concluded: "Conclusa",
  archived: "Archiviata",
};

export function leagueStateLabel(state: LeagueState | null | undefined): string {
  return state ? STATE_LABELS[state] : "—";
}
