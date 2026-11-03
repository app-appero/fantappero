/** Vetrina della schermata di accesso: top player dei cinque campionati (solo nomi, nessuna foto). */
export type ShowcaseRole = "P" | "D" | "C" | "A";

export interface ShowcaseLeague {
  flag: string;
  name: string;
  players: ReadonlyArray<{ name: string; role: ShowcaseRole }>;
}

export const LOGIN_SHOWCASE_LEAGUES: readonly ShowcaseLeague[] = [
  { flag: "🇮🇹", name: "Serie A", players: [{ name: "Lautaro", role: "A" }, { name: "Leão", role: "A" }, { name: "Barella", role: "C" }] },
  { flag: "🏴", name: "Premier", players: [{ name: "Haaland", role: "A" }, { name: "Salah", role: "A" }, { name: "Saka", role: "A" }] },
  { flag: "🇪🇸", name: "LaLiga", players: [{ name: "Mbappé", role: "A" }, { name: "Vinícius", role: "A" }, { name: "Yamal", role: "A" }] },
  { flag: "🇩🇪", name: "Bundesliga", players: [{ name: "Kane", role: "A" }, { name: "Musiala", role: "C" }, { name: "Wirtz", role: "C" }] },
  { flag: "🇫🇷", name: "Ligue 1", players: [{ name: "Dembélé", role: "A" }, { name: "Barcola", role: "A" }, { name: "Doué", role: "C" }] },
];

export interface ShowcasePlayer {
  name: string;
  role: ShowcaseRole;
  flag: string;
  /** Posizione sul campo in miniatura, in percentuale. */
  x: number;
  y: number;
  state?: "final" | "live";
}

/** Formazione di esempio con giocatori di campionati diversi: in una lega si mescolano. */
export const LOGIN_SHOWCASE_PITCH: readonly ShowcasePlayer[] = [
  { name: "Haaland", role: "A", flag: "🏴", x: 22, y: 14, state: "final" },
  { name: "Mbappé", role: "A", flag: "🇪🇸", x: 50, y: 14, state: "live" },
  { name: "Kane", role: "A", flag: "🇩🇪", x: 78, y: 14 },
  { name: "Barella", role: "C", flag: "🇮🇹", x: 26, y: 40, state: "final" },
  { name: "Musiala", role: "C", flag: "🇩🇪", x: 50, y: 40 },
  { name: "Yamal", role: "C", flag: "🇪🇸", x: 74, y: 40 },
  { name: "Saka", role: "D", flag: "🏴", x: 16, y: 66 },
  { name: "Bastoni", role: "D", flag: "🇮🇹", x: 39, y: 66, state: "final" },
  { name: "Barcola", role: "D", flag: "🇫🇷", x: 61, y: 66 },
  { name: "Dumfries", role: "D", flag: "🇮🇹", x: 84, y: 66 },
  { name: "Maignan", role: "P", flag: "🇮🇹", x: 50, y: 86 },
];

export const LOGIN_SHOWCASE_FEATURES = [
  { glyph: "🔨", title: "Asta live e scambi", text: "Costruisci la rosa con gli amici" },
  { glyph: "🔒", title: "Formazione a step", text: "Ogni giocatore si blocca al suo fischio" },
  { glyph: "🏆", title: "Più campionati", text: "Una lega con i campionati che scegli" },
] as const;
