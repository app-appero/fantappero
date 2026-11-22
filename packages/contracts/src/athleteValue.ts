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

/**
 * Ordine «Ordina per media»: dalla media più alta alla più bassa, chi non ha media in fondo.
 * Il listone si ordina in app (il backend lo restituisce intero); a parità resta l'ordine dato.
 */
export function compareBySeasonAverageDesc(
  left: AthleteMarketFields,
  right: AthleteMarketFields,
): number {
  const a = left.seasonAverage?.value;
  const b = right.seasonAverage?.value;
  const aMissing = a === undefined || a === null;
  const bMissing = b === undefined || b === null;
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  return b - a;
}

/** Copia ordinata con `compareBySeasonAverageDesc` (stabile: a parità resta l'ordine dato). */
export function sortBySeasonAverageDesc<T extends AthleteMarketFields>(items: readonly T[]): T[] {
  return [...items].sort(compareBySeasonAverageDesc);
}
