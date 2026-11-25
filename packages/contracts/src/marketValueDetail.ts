/**
 * «Dettaglio del Valore» (release 1.4, solo operatore): come si arriva al Valore di mercato di
 * un calciatore, stagione per stagione. `GET /admin/listone/valori/{athleteId}?seasonYear=…
 * &leagueId=…` (`global:operate`); guida in `docs/operations/valore_di_mercato_e_storico.md`.
 *
 * Tipi della risposta e frasi in italiano condivise da web e app, così le due schede dicono la
 * stessa cosa con gli stessi numeri. Nessun calcolo nuovo: i numeri vengono dal backend
 * (`components_json` dell'ultimo ricalcolo); qui solo la formattazione e i crediti a un budget
 * a scelta, con la stessa regola del backend (`credits_for_budget`).
 */
import type { FantasyRole } from "./leagues.js";

export type MarketValueSeasonSlot = "current" | "previous" | "twoSeasonsAgo";

/**
 * `league` conta; `cup`, `youth` (giovanili, riserve, femminili: 25/11), `unknown` (non
 * campionato) e `no_rating` (senza media) no.
 */
export type MarketValueRowKind = "league" | "cup" | "youth" | "unknown" | "no_rating";

export interface AdminMarketValueSeasonRow {
  competition: string;
  club: string | null;
  /** Peso nella media: presenze (fornitore) o partite con voto (FantApperò). */
  appearances: number;
  average: number | null;
  kind: MarketValueRowKind;
}

export interface AdminMarketValueSeasonDetail {
  slot: MarketValueSeasonSlot;
  seasonYear: number;
  /** «25/26». */
  seasonLabel: string;
  isCurrent: boolean;
  /** `provider` (fornitore) o `fantappero`; `null` se la stagione non ha righe. */
  source: "provider" | "fantappero" | null;
  /** Competizioni contate, dalla più giocata. */
  competitions: string[];
  rows: AdminMarketValueSeasonRow[];
  /** Righe che non contano (coppe, tipo sconosciuto, senza media). */
  excluded: AdminMarketValueSeasonRow[];
  /** `false`: stagione senza dati, vale `missingSeasonIndex` (la stagione in corso pesa 0). */
  hasData: boolean;
  /** Presenze con voto (n). */
  appearances: number;
  average: number | null;
  roleAverage: number | null;
  shrunkAverage: number | null;
  /** 0..1. */
  percentile: number | null;
  /** 1 = media ristretta più alta del ruolo. */
  rank: number | null;
  /** Calciatori del ruolo con dati nella stagione. */
  poolSize: number | null;
  /** 0..1. */
  weight: number;
  /** Indice che entra nella somma (percentile o valore della stagione senza dati). */
  indexUsed: number;
  /** `weight × indexUsed`. */
  contribution: number;
}

export interface AdminMarketValueLeagueCredits {
  leagueId: string;
  leagueName: string;
  budget: number;
  credits: number;
}

/**
 * - `computed`: dettaglio completo;
 * - `outdated`: riga scritta prima della 1.4, solo percentili e pesi (rifare «Ricalcola
 *   valori»);
 * - `not_computed`: nessuna riga (entrato nel listone dopo l'ultimo ricalcolo): valore base.
 */
export type AdminMarketValueStatus = "computed" | "outdated" | "not_computed";

export interface AdminMarketValueDetail {
  athleteId: string;
  canonicalName: string;
  clubName: string | null;
  role: FantasyRole;
  seasonYear: number;
  seasonLabel: string;
  status: AdminMarketValueStatus;
  version: string | null;
  computedAt: string | null;
  /** Indice combinato p (0..1). */
  valueIndex: number;
  /** Crediti al budget di riferimento, non arrotondati. */
  referenceValue: number;
  /** Crediti al budget di riferimento, arrotondati. */
  referenceCredits: number;
  referenceBudget: number;
  roleTop: number;
  floor: number;
  curveExponent: number;
  missingSeasonIndex: number;
  shrinkAppearances: number;
  currentFullWeightAppearances: number;
  /** Valore di riferimento di chi non ha storico, nello stesso ruolo. */
  baseReferenceValue: number;
  /** Stagione in corso, scorsa, due fa. */
  seasons: AdminMarketValueSeasonDetail[];
  league: AdminMarketValueLeagueCredits | null;
}

// --- formattazione ---------------------------------------------------------------------------

const ROLE_PLURAL: Record<FantasyRole, string> = {
  P: "portieri",
  D: "difensori",
  C: "centrocampisti",
  A: "attaccanti",
};

const ROW_KIND_LABEL: Record<MarketValueRowKind, string> = {
  league: "campionato",
  cup: "coppa",
  youth: "giovanili o riserve",
  unknown: "competizione di tipo sconosciuto",
  no_rating: "senza media",
};

export function marketValueRolePlural(role: FantasyRole): string {
  return ROLE_PLURAL[role];
}

export function marketValueRowKindLabel(kind: MarketValueRowKind): string {
  return ROW_KIND_LABEL[kind] ?? kind;
}

/** Numero con la virgola: 7.034 → «7,03» (2 decimali di default). */
export function formatValueNumber(value: number, digits = 2): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const fixed = value.toFixed(digits);
  return (fixed === `-${(0).toFixed(digits)}` ? (0).toFixed(digits) : fixed).replace(".", ",");
}

/** Peso in percentuale: 0.3 → «30%», 0.2333 → «23,3%». */
export function formatWeightPercent(weight: number): string {
  const tenths = Math.round(weight * 1000) / 10;
  return `${Number.isInteger(tenths) ? String(tenths) : formatValueNumber(tenths, 1)}%`;
}

/** Percentile come posizione: 0.62 → «62°». */
export function formatPercentileOrdinal(percentile: number): string {
  return `${Math.min(100, Math.max(0, Math.round(percentile * 100)))}°`;
}

/** «2025/26» dall'anno d'inizio. */
export function marketValueSeasonName(seasonYear: number): string {
  return `${seasonYear}/${String((((seasonYear + 1) % 100) + 100) % 100).padStart(2, "0")}`;
}

export function marketValueSourceLabel(source: AdminMarketValueSeasonDetail["source"]): string {
  if (source === "provider") {
    return "fornitore";
  }
  if (source === "fantappero") {
    return "FantApperò";
  }
  return "nessuna fonte";
}

/** Crediti per un budget: come il backend, proporzionali, arrotondati, almeno 1. */
export function marketValueCreditsForBudget(
  referenceValue: number,
  budget: number,
  referenceBudget = 1000,
): number {
  const scaled = (referenceValue * Math.max(0, budget)) / referenceBudget;
  return Math.max(1, Math.floor(scaled + 0.5));
}

function appearancesLabel(season: AdminMarketValueSeasonDetail): string {
  const n = season.appearances;
  if (season.source === "fantappero") {
    return n === 1 ? "1 partita con voto" : `${n} partite con voto`;
  }
  return n === 1 ? "1 presenza" : `${n} presenze`;
}

function seasonHeading(season: AdminMarketValueSeasonDetail): string {
  const name = `Stagione ${marketValueSeasonName(season.seasonYear)}`;
  if (!season.source) {
    return name;
  }
  const parts = [marketValueSourceLabel(season.source), ...season.competitions];
  return `${name} (${parts.join(", ")})`;
}

/**
 * Una stagione in una frase, es. «Stagione 2025/26 (fornitore, Premier League): 34 presenze,
 * media 7,03 → media ristretta 6,98 → 62° percentile fra 180 portieri → peso 30%».
 */
export function marketValueSeasonSentence(
  season: AdminMarketValueSeasonDetail,
  role: FantasyRole,
  missingSeasonIndex = 0.33,
): string {
  const heading = seasonHeading(season);
  const weight = `peso ${formatWeightPercent(season.weight)}`;
  if (!season.hasData) {
    if (season.isCurrent) {
      return `${heading}: nessun voto FantApperò quest'anno → ${weight}`;
    }
    const why =
      season.excluded.length > 0 ? "nessuna riga di campionato con media" : "nessun dato";
    return `${heading}: ${why} → vale ${formatValueNumber(missingSeasonIndex)} come una stagione senza dati (sotto la mediana) → ${weight}`;
  }
  const parts = [`${heading}: ${appearancesLabel(season)}`];
  if (season.average !== null) {
    parts[0] += `, media ${formatValueNumber(season.average)}`;
  }
  if (season.shrunkAverage !== null) {
    const roleAverage =
      season.roleAverage !== null
        ? ` (media dei ${ROLE_PLURAL[role]} ${formatValueNumber(season.roleAverage)})`
        : "";
    parts.push(`media ristretta ${formatValueNumber(season.shrunkAverage)}${roleAverage}`);
  }
  if (season.percentile !== null) {
    const pool = season.poolSize !== null ? ` fra ${season.poolSize} ${ROLE_PLURAL[role]}` : "";
    const rank = season.rank !== null ? `, ${season.rank}° posto` : "";
    parts.push(`${formatPercentileOrdinal(season.percentile)} percentile${pool}${rank}`);
  }
  parts.push(weight);
  return parts.join(" → ");
}

/** Le righe che non contano, es. «Non contano: UEFA Champions League (coppa, 10 presenze)». */
export function marketValueExcludedText(season: AdminMarketValueSeasonDetail): string | null {
  if (season.excluded.length === 0) {
    return null;
  }
  const items = season.excluded.map((row) => {
    const unit = season.source === "fantappero" ? "partite" : "presenze";
    const average = row.average !== null ? `, media ${formatValueNumber(row.average)}` : "";
    return `${row.competition} (${marketValueRowKindLabel(row.kind)}, ${row.appearances} ${unit}${average})`;
  });
  return `Non contano: ${items.join("; ")}`;
}

/** «p = 30% × 0,62 + 20% × 0,55 + 50% × 0,40 = 0,49» (solo le stagioni con peso). */
export function marketValueIndexSentence(detail: AdminMarketValueDetail): string {
  const terms = detail.seasons
    .filter((season) => season.weight > 0)
    .map((season) => `${formatWeightPercent(season.weight)} × ${formatValueNumber(season.indexUsed)}`);
  const sum = terms.length > 0 ? terms.join(" + ") : "0";
  return `Indice combinato p = ${sum} = ${formatValueNumber(detail.valueIndex)}`;
}

/**
 * «Curva dei portieri: 1 + (30 − 1) × 0,49^2,4 = 6,1 crediti a budget 1000 → 6 crediti».
 */
export function marketValueCurveSentence(detail: AdminMarketValueDetail): string {
  const floor = formatValueNumber(detail.floor, 0);
  const top = formatValueNumber(detail.roleTop, 0);
  const exponent = formatValueNumber(detail.curveExponent, 1);
  return (
    `Curva dei ${ROLE_PLURAL[detail.role]}: ${floor} + (${top} − ${floor}) × ` +
    `${formatValueNumber(detail.valueIndex)}^${exponent} = ${formatValueNumber(detail.referenceValue, 1)} ` +
    `crediti a budget ${detail.referenceBudget} → ${detail.referenceCredits} ${detail.referenceCredits === 1 ? "credito" : "crediti"}`
  );
}

/** «Lega da 500 crediti: 6,1 × 500 / 1000 = 3,05 → 3 crediti». */
export function marketValueBudgetSentence(
  detail: AdminMarketValueDetail,
  budget: number,
  leagueName?: string | null,
): string {
  const credits = marketValueCreditsForBudget(detail.referenceValue, budget, detail.referenceBudget);
  const scaled = (detail.referenceValue * Math.max(0, budget)) / detail.referenceBudget;
  const who = leagueName ? `«${leagueName}» (budget ${budget})` : `Lega da ${budget} crediti`;
  return (
    `${who}: ${formatValueNumber(detail.referenceValue, 1)} × ${budget} / ${detail.referenceBudget} = ` +
    `${formatValueNumber(scaled)} → ${credits} ${credits === 1 ? "credito" : "crediti"}`
  );
}

/** Confronto con il valore base del ruolo (chi non ha storico). */
export function marketValueBaseSentence(detail: AdminMarketValueDetail): string {
  const base = marketValueCreditsForBudget(detail.baseReferenceValue, detail.referenceBudget, detail.referenceBudget);
  return (
    `Valore base dei ${ROLE_PLURAL[detail.role]} (nessuno storico, p = ` +
    `${formatValueNumber(detail.missingSeasonIndex)}): ${base} ${base === 1 ? "credito" : "crediti"}`
  );
}

/** Avviso per le righe vecchie o mancanti; `null` se il dettaglio è completo. */
export function marketValueStatusText(detail: AdminMarketValueDetail): string | null {
  if (detail.status === "outdated") {
    return "Calcolato con una versione precedente che non salvava il dettaglio: ci sono solo percentili e pesi. Usa «Ricalcola valori» per vedere ogni passaggio.";
  }
  if (detail.status === "not_computed") {
    return "Nessun calcolo per questo calciatore (entrato nel listone dopo l'ultimo ricalcolo): vale il valore base del ruolo fino al prossimo ricalcolo.";
  }
  return null;
}
