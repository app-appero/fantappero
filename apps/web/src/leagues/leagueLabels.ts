import { LEAGUE_STATE_DOT_EMOJI, type LeagueState } from "@fantappero/contracts";

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

/**
 * Nome lega con un pallino colorato davanti, per il menu a tendina dell'header:
 * sostituisce il badge testuale di stato, che in quello spazio stretto si
 * mangiava la larghezza. Dentro una `<option>` nativa non c'è modo affidabile
 * di colorare un elemento via CSS su ogni browser — l'emoji è testo, quindi
 * identica ovunque.
 */
export function leagueNameWithStateDot(name: string, state: LeagueState | null | undefined): string {
  const dot = state ? LEAGUE_STATE_DOT_EMOJI[state] : null;
  return dot ? `${dot} ${name}` : name;
}
