/**
 * Presentazione del risultato dello scontro diretto (EP13-P02).
 *
 * Il backend (EP07-05) persiste due grandezze distinte sullo slot di
 * calendario e la UI deve nominarle entrambe invece di mostrare numeri
 * anonimi tra parentesi:
 *
 * - **Punti** — `homeScore`/`awayScore`: la somma dei fantavoti degli undici
 *   effettivi, con decimali.
 * - **Gol fantasy** — `homeFantasyGoals`/`awayFantasyGoals`: i Punti
 *   convertiti in gol secondo le soglie di `docs/api/league_scoring.md`, cioè
 *   il risultato dello scontro diretto.
 *
 * Questo modulo formatta soltanto: la conversione Punti → Gol fantasy resta
 * del backend e non va mai ricalcolata nel client.
 */

import type { H2HMatchupScore } from "./leagues.js";

export const H2H_POINTS_LABEL = "Punti";
export const H2H_GOALS_LABEL = "Gol fantasy";

/** Placeholder per un valore non ancora calcolato: mai sostituito da zero. */
export const H2H_VALUE_UNAVAILABLE = "—";

/** Trattino semilungo spaziato, come negli esempi di prodotto: `72,5 – 68,0`. */
const SEPARATOR = " – ";

const pointsFormatter = new Intl.NumberFormat("it-IT", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const goalsFormatter = new Intl.NumberFormat("it-IT", {
  maximumFractionDigits: 0,
});

function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value);
}

/** Punti con una cifra decimale in formato italiano (`72,5`). */
export function formatFantasyPoints(value: number | null | undefined): string {
  return isMissing(value) ? H2H_VALUE_UNAVAILABLE : pointsFormatter.format(value);
}

/** Gol fantasy come intero (`2`). */
export function formatFantasyGoals(value: number | null | undefined): string {
  return isMissing(value) ? H2H_VALUE_UNAVAILABLE : goalsFormatter.format(value);
}

/** Voto provvisorio mostrato mentre il provider non ha ancora un voto per chi sta giocando. */
export const PROVISIONAL_LIVE_SCORE = 6;

export type PlayerVoteKind = "voted" | "live" | "provisional" | "sv" | "pending";

export interface PlayerVoteState {
  kind: PlayerVoteKind;
  /** Testo del bollino: `7,5`, `6,5 LIVE`, `6 LIVE`, `S.V.` oppure `null` se non ancora giocato. */
  label: string | null;
  /** Partita in corso: alone blu lampeggiante. */
  live: boolean;
}

/**
 * Stato del voto di un giocatore nello scontro:
 * - voto presente → `voted` (o `live` se la sua partita è in corso);
 * - partita in corso senza voto del provider → `provisional` (6 LIVE);
 * - partita terminata senza voto (minutaggio insufficiente) → `sv`;
 * - altrimenti `pending`.
 */
export function playerVoteState(player: {
  fantasyScore?: number | null;
  fixtureStatusLabel?: string | null;
  scoreFinal?: boolean;
}): PlayerVoteState {
  const isLive = player.fixtureStatusLabel === "LIVE";
  if (player.fantasyScore != null) {
    const base = formatFantasyPoints(player.fantasyScore);
    return { kind: isLive ? "live" : "voted", label: isLive ? `${base} LIVE` : base, live: isLive };
  }
  if (isLive) {
    return {
      kind: "provisional",
      label: `${formatFantasyPoints(PROVISIONAL_LIVE_SCORE)} LIVE`.replace(",0", ""),
      live: true,
    };
  }
  if (player.fixtureStatusLabel === "Terminata" || player.scoreFinal === true) {
    return { kind: "sv", label: "S.V.", live: false };
  }
  return { kind: "pending", label: null, live: false };
}

export type H2HResultStatus = "pending" | "provisional" | "final";

export interface H2HResultDisplay {
  status: H2HResultStatus;
  statusLabel: string;
  /** True solo se entrambi i lati hanno i Punti calcolati. */
  pointsAvailable: boolean;
  pointsLine: string;
  /** True solo se entrambi i lati hanno i Gol fantasy calcolati. */
  goalsAvailable: boolean;
  goalsLine: string;
  /** Spiegazione da mostrare quando una grandezza non è disponibile. */
  unavailableHint: string | null;
}

const STATUS_LABELS: Record<H2HResultStatus, string> = {
  pending: "In attesa",
  provisional: "Provvisorio",
  final: "Finale",
};

/**
 * Deriva la resa delle due grandezze senza inventare valori: un lato non
 * calcolato resta `—` e non diventa `0`.
 */
export function describeH2HResult(
  result: H2HMatchupScore | null | undefined,
): H2HResultDisplay {
  const homePoints = result?.homeScore ?? null;
  const awayPoints = result?.awayScore ?? null;
  const homeGoals = result?.homeFantasyGoals ?? null;
  const awayGoals = result?.awayFantasyGoals ?? null;

  const pointsAvailable = !isMissing(homePoints) && !isMissing(awayPoints);
  const goalsAvailable = !isMissing(homeGoals) && !isMissing(awayGoals);

  const status: H2HResultStatus = !result
    ? "pending"
    : result.resultFinal
      ? "final"
      : "provisional";

  let unavailableHint: string | null = null;
  if (status === "pending") {
    unavailableHint = "Risultato non ancora calcolato.";
  } else if (!pointsAvailable || !goalsAvailable) {
    unavailableHint = "Alcuni valori non sono ancora disponibili per questo scontro.";
  }

  return {
    status,
    statusLabel: STATUS_LABELS[status],
    pointsAvailable,
    pointsLine: `${formatFantasyPoints(homePoints)}${SEPARATOR}${formatFantasyPoints(awayPoints)}`,
    goalsAvailable,
    goalsLine: `${formatFantasyGoals(homeGoals)}${SEPARATOR}${formatFantasyGoals(awayGoals)}`,
    unavailableHint,
  };
}

/**
 * Riga leggibile da screen reader per l'insieme del risultato, così il
 * significato non dipende dal solo accostamento visivo dei numeri.
 */
export function h2hResultAriaLabel(
  display: H2HResultDisplay,
  homeName: string,
  awayName: string,
): string {
  return [
    `${homeName} contro ${awayName}`,
    `${H2H_GOALS_LABEL} ${display.goalsLine}`,
    `${H2H_POINTS_LABEL} ${display.pointsLine}`,
    display.statusLabel,
  ].join(". ");
}
