/**
 * Storico del calciatore, media stagionale e Valore di mercato (release 1.3).
 *
 * Tutto additivo: i campi nuovi sulle risposte esistenti sono opzionali (`?`), così web e
 * mobile compilano anche contro un backend più vecchio. Le regole di prezzo («il prezzo parte
 * dal Valore») restano alla UI; il backend non cambia la validazione delle offerte
 * (partecipante almeno 1 credito, admin anche 0).
 */

/**
 * Media stagionale mostrata in ogni riga del mercato.
 *
 * - `isCurrent: true`: media dei voti FantApperò della stagione in corso (almeno un voto) →
 *   verde;
 * - `isCurrent: false`: media della stagione scorsa (per la 2026/27 quella del fornitore della
 *   2025/26), con l'etichetta `seasonLabel` («25/26») → rossa;
 * - nessuna delle due: il campo è `null`.
 */
export interface AthleteSeasonAverage {
  value: number;
  /** Anno d'inizio della stagione (2025 per la 2025/26). */
  seasonYear: number;
  /** «25/26». */
  seasonLabel: string;
  isCurrent: boolean;
}

/**
 * Campi aggiunti alle righe di calciatore del mercato: listone della Rosa (e quindi
 * Svincolati), offerte di asta a buste e svincoli, lotto dell'asta live, calciatori delle
 * proposte di scambio, scheda calciatore.
 */
export interface AthleteMarketFields {
  /**
   * Valore di mercato in crediti di questa lega (proporzionale al suo budget, almeno 1).
   * Prezzo consigliato, non un minimo. `null` se il calciatore non è nel listone della stagione;
   * assente da un backend più vecchio.
   */
  marketValue?: number | null;
  seasonAverage?: AthleteSeasonAverage | null;
}

/** `provider`: statistiche di stagione del fornitore; `fantappero`: i dati di FantApperò. */
export type AthleteCareerSource = "provider" | "fantappero";

/** Una riga dello storico della scheda calciatore: stagione + club + competizione. */
export interface AthleteCareerRow {
  seasonYear: number;
  seasonLabel: string;
  isCurrent: boolean;
  source: AthleteCareerSource;
  /** Id FantApperò del club, se il club è nel nostro catalogo; altrimenti solo il nome. */
  clubId: string | null;
  clubName: string | null;
  competitionId: string | null;
  competitionName: string | null;
  appearances: number | null;
  minutes: number | null;
  /** Media voto: del fornitore per le stagioni passate, dei voti FantApperò per quella in corso. */
  averageRating: number | null;
  /** Partite con voto FantApperò (`null` per le righe del fornitore). */
  votes: number | null;
  fantasyAverage: number | null;
  goals: number | null;
  assists: number | null;
  goalsConceded: number | null;
  saves: number | null;
  penaltiesSaved: number | null;
  yellowCards: number | null;
  redCards: number | null;
  /** Porte inviolate: solo portieri e solo dalla stagione in corso; `null` dove non note. */
  cleanSheets: number | null;
}

/** «25/26» dall'anno d'inizio della stagione (2025). */
export function seasonLabel(seasonYear: number): string {
  const start = ((seasonYear % 100) + 100) % 100;
  const end = (start + 1) % 100;
  return `${String(start).padStart(2, "0")}/${String(end).padStart(2, "0")}`;
}

/** 0: media della stagione in corso, 1: solo quella della scorsa, 2: nessuna media. */
function seasonAverageTier(average: AthleteSeasonAverage | null | undefined): 0 | 1 | 2 {
  if (!average || typeof average.value !== "number" || Number.isNaN(average.value)) return 2;
  return average.isCurrent ? 0 : 1;
}

/**
 * Ordine «Ordina per media» (Rosario 23/11): prima tutti quelli con la media della stagione in
 * corso (`isCurrent: true`, verde), dalla più alta alla più bassa; poi quelli con la sola media
 * della stagione scorsa (`isCurrent: false`, rossa), dalla più alta alla più bassa; in fondo chi
 * non ha media. Prima del 23/11 le due medie erano mescolate: un 6,30 della stagione scorsa
 * passava davanti a un 5,90 di quest'anno.
 * Il listone si ordina in app (il backend lo restituisce intero); a parità resta l'ordine dato.
 */
export function compareBySeasonAverageDesc(
  left: AthleteMarketFields,
  right: AthleteMarketFields,
): number {
  const leftTier = seasonAverageTier(left.seasonAverage);
  const rightTier = seasonAverageTier(right.seasonAverage);
  if (leftTier !== rightTier) return leftTier - rightTier;
  if (leftTier === 2) return 0;
  // Stesso gruppo e media presente in entrambi (tier 0 o 1).
  return (right.seasonAverage?.value ?? 0) - (left.seasonAverage?.value ?? 0);
}

/** Copia ordinata con `compareBySeasonAverageDesc` (stabile: a parità resta l'ordine dato). */
export function sortBySeasonAverageDesc<T extends AthleteMarketFields>(items: readonly T[]): T[] {
  return [...items].sort(compareBySeasonAverageDesc);
}
