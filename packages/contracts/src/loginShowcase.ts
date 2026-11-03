/** Vetrina della schermata di accesso: top player dei cinque campionati (solo nomi, nessuna foto). */
export type ShowcaseRole = "P" | "D" | "C" | "A";

export interface ShowcaseLeague {
  flag: string;
  /** Sigla del paese (ITA, ENG…): le bandiere emoji su Windows si vedono come lettere. */
  code: string;
  name: string;
  players: ReadonlyArray<{ name: string; role: ShowcaseRole }>;
}

export const LOGIN_SHOWCASE_LEAGUES: readonly ShowcaseLeague[] = [
  { flag: "🇮🇹", code: "ITA", name: "Serie A", players: [{ name: "Lautaro", role: "A" }, { name: "Leão", role: "A" }, { name: "Barella", role: "C" }] },
  { flag: "🏴", code: "ENG", name: "Premier", players: [{ name: "Haaland", role: "A" }, { name: "Salah", role: "A" }, { name: "Saka", role: "A" }] },
  { flag: "🇪🇸", code: "ESP", name: "LaLiga", players: [{ name: "Mbappé", role: "A" }, { name: "Vinícius", role: "A" }, { name: "Yamal", role: "A" }] },
  { flag: "🇩🇪", code: "GER", name: "Bundesliga", players: [{ name: "Kane", role: "A" }, { name: "Musiala", role: "C" }, { name: "Wirtz", role: "C" }] },
  { flag: "🇫🇷", code: "FRA", name: "Ligue 1", players: [{ name: "Dembélé", role: "A" }, { name: "Barcola", role: "A" }, { name: "Doué", role: "C" }] },
];

export interface ShowcasePlayer {
  name: string;
  role: ShowcaseRole;
  flag: string;
  code: string;
  /** Posizione sul campo in miniatura, in percentuale. */
  x: number;
  y: number;
  state?: "final" | "live";
}

/** Formazione di esempio con giocatori di campionati diversi: in una lega si mescolano. */
export const LOGIN_SHOWCASE_PITCH: readonly ShowcasePlayer[] = [
  { name: "Haaland", role: "A", flag: "🏴", code: "ENG", x: 22, y: 14, state: "final" },
  { name: "Mbappé", role: "A", flag: "🇪🇸", code: "ESP", x: 50, y: 14, state: "live" },
  { name: "Kane", role: "A", flag: "🇩🇪", code: "GER", x: 78, y: 14 },
  { name: "Barella", role: "C", flag: "🇮🇹", code: "ITA", x: 26, y: 40, state: "final" },
  { name: "Musiala", role: "C", flag: "🇩🇪", code: "GER", x: 50, y: 40 },
  { name: "Yamal", role: "C", flag: "🇪🇸", code: "ESP", x: 74, y: 40 },
  { name: "Saka", role: "D", flag: "🏴", code: "ENG", x: 16, y: 63 },
  { name: "Bastoni", role: "D", flag: "🇮🇹", code: "ITA", x: 39, y: 63, state: "final" },
  { name: "Barcola", role: "D", flag: "🇫🇷", code: "FRA", x: 61, y: 63 },
  { name: "Dumfries", role: "D", flag: "🇮🇹", code: "ITA", x: 84, y: 63 },
  { name: "Maignan", role: "P", flag: "🇮🇹", code: "ITA", x: 50, y: 88 },
];

export const LOGIN_SHOWCASE_FEATURES = [
  { glyph: "🔨", title: "Asta live e scambi", text: "Costruisci la rosa con gli amici" },
  { glyph: "🔒", title: "Formazione a step", text: "Ogni giocatore si blocca al suo fischio" },
  { glyph: "🏆", title: "Più campionati", text: "Una lega con i campionati che scegli" },
] as const;
