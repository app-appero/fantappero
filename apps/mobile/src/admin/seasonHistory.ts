/**
 * Pannello operatore → Listone → «Storico stagioni» (1.3): import una tantum delle due stagioni
 * passate dal fornitore e ricalcolo di medie e Valore
 * (`docs/operations/valore_di_mercato_e_storico.md`).
 *
 * 1. «Calcola chiamate»: `POST /admin/listone/storico` in modalità conta (`dryRun`), nessuna
 *    chiamata al fornitore.
 * 2. «Avvia import» (dopo la conferma): stessa chiamata con `dryRun: false`; se un import è già
 *    in corso il backend restituisce quello.
 * 3. Avanzamento: `GET /admin/listone/storico/{jobId}` finché il job è in coda o in corso; si
 *    smette quando la schermata perde il focus e si riprende (`GET /admin/listone/storico`)
 *    quando torna.
 * 4. «Ricalcola valori»: `POST /admin/listone/valori/ricalcola`.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` con un'API finta.
 */
import type {
  AdminMarketValuesRefreshResult,
  AdminSeasonHistoryEstimate,
  AdminSeasonHistoryImportResponse,
  AdminSeasonHistoryProgress,
  AdminSeasonHistoryResult,
  AdminSeasonHistoryStopReason,
} from "@fantappero/contracts";

/** Le chiamate che servono al pannello (in app: `api/admin.ts`; nei test: finte). */
export type SeasonHistoryApi = {
  estimate: (seasonYear: number) => Promise<AdminSeasonHistoryImportResponse>;
  start: (seasonYear: number) => Promise<AdminSeasonHistoryImportResponse>;
  fetchActive: () => Promise<AdminSeasonHistoryProgress | null>;
  fetchProgress: (jobId: string) => Promise<AdminSeasonHistoryProgress>;
  refreshValues: (seasonYear: number) => Promise<AdminMarketValuesRefreshResult>;
};

export const SEASON_HISTORY_POLL_INTERVAL_MS = 2000;

function formatInteger(value: number): string {
  const rounded = Math.round(value);
  const sign = rounded < 0 ? "-" : "";
  return sign + String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function plural(count: number, one: string, many: string): string {
  return `${formatInteger(count)} ${count === 1 ? one : many}`;
}

/** Anno d'inizio della stagione in corso: da luglio quella nuova (novembre 2026 → 2026). */
export function currentSeasonYear(now: Date = new Date()): number {
  return now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
}

/** Anno della stagione scritto dall'operatore, o `null` se non valido (2000-2100 come il backend). */
export function parseSeasonYearInput(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d{4}$/.test(trimmed)) {
    return null;
  }
  const year = Number(trimmed);
  return year >= 2000 && year <= 2100 ? year : null;
}

export const INVALID_SEASON_YEAR_MESSAGE = "Inserisci un anno stagione valido (es. 2026).";

/** Il job è ancora da seguire. */
export function isSeasonHistoryJobActive(status: string | null | undefined): boolean {
  return status === "queued" || status === "running";
}

/** «Circa 1.650 chiamate al fornitore, circa 6 minuti (300 al minuto).» */
export function estimateHeadline(estimate: AdminSeasonHistoryEstimate): string {
  if (estimate.estimatedCalls <= 0) {
    return "Storico già completo: rilanciare l'import non costa chiamate.";
  }
  const minutes = Math.max(1, estimate.estimatedMinutes);
  return `Circa ${plural(estimate.estimatedCalls, "chiamata", "chiamate")} al fornitore, circa ${plural(minutes, "minuto", "minuti")} (${formatInteger(estimate.requestsPerMinute)} al minuto).`;
}

/** Una riga per stagione: «25/26: 38 pagine di campionato (stima), 600 calciatori da cercare (stima) · 812 chiamate». */
export function estimateSeasonLines(estimate: AdminSeasonHistoryEstimate): string[] {
  return estimate.seasons.map((season) => {
    const pages = `${plural(season.leaguePagesRemaining, "pagina", "pagine")} di campionato${season.leaguePagesExact ? "" : " (stima)"}`;
    const athletes = `${plural(season.athletesToFill, "calciatore", "calciatori")} da cercare${season.athletesToFillExact ? "" : " (stima)"}`;
    return `${season.seasonLabel}: ${pages}, ${athletes} · ${plural(season.estimatedCalls, "chiamata", "chiamate")}`;
  });
}

export const START_IMPORT_CONFIRM_TITLE = "Avviare l'import dello storico?";
export const START_IMPORT_CONFIRM_LABEL = "Avvia import";
export const START_IMPORT_CANCEL_LABEL = "Annulla";

/** Testo della conferma prima di «Avvia import». */
export function startImportConfirmMessage(seasonYear: number, estimate: AdminSeasonHistoryEstimate | null): string {
  const seasons = estimate?.seasons.map((season) => season.seasonLabel).join(" e ");
  const head = seasons
    ? `Si scaricano dal fornitore le stagioni ${seasons} (stagione in corso ${seasonYear}).`
    : `Si scaricano dal fornitore le due stagioni prima della ${seasonYear}.`;
  const cost = estimate ? ` ${estimateHeadline(estimate)}` : "";
  return `${head}${cost} L'import si ferma da solo prima di togliere quota ai giri live e si può riprendere rilanciandolo.`;
}

const STOP_REASON_TEXT: Record<AdminSeasonHistoryStopReason, string> = {
  max_calls: "Fermato al tetto di chiamate di questa esecuzione: rilancia l'import per continuare.",
  quota_reserve: "Fermato per lasciare quota ai giri live (sotto il 15% della quota giornaliera): rilancialo domani.",
  too_many_errors: "Fermato dopo troppi errori di fila del fornitore: riprova più tardi.",
};

export function stopReasonText(reason: AdminSeasonHistoryStopReason | string | null | undefined): string | null {
  if (!reason) {
    return null;
  }
  return STOP_REASON_TEXT[reason as AdminSeasonHistoryStopReason] ?? `Fermato prima della fine (${reason}): rilancia l'import per continuare.`;
}

/** «Import in corso: 42% · Pagine di campionato 25/26». */
export function progressText(progress: AdminSeasonHistoryProgress): string {
  const message = progress.message?.trim();
  return message ? `${message} (${progress.percent}%)` : `Import in corso (${progress.percent}%)`;
}

/** Riepilogo del risultato a fine import. */
export function resultLines(result: AdminSeasonHistoryResult): string[] {
  const lines = [
    `${plural(result.calls, "chiamata", "chiamate")} al fornitore: ${plural(result.rowsCreated, "riga creata", "righe create")}, ${plural(result.rowsUpdated, "aggiornata", "aggiornate")}, ${plural(result.athletesFound, "calciatore trovato", "calciatori trovati")} su ${formatInteger(result.athletesChecked)} cercati.`,
  ];
  if (result.errors > 0) {
    lines.push(`${plural(result.errors, "errore", "errori")} del fornitore.`);
  }
  const stopped = stopReasonText(result.stoppedReason);
  if (stopped) {
    lines.push(stopped);
  }
  if (result.remaining && result.remaining.estimatedCalls > 0) {
    lines.push(`Resta da scaricare: ${estimateHeadline(result.remaining)}`);
  }
  if (result.marketValues) {
    lines.push(marketValuesText(result.marketValues));
  }
  return lines;
}

/** Esito di «Ricalcola valori» (o del ricalcolo a fine import). */
export function marketValuesText(result: AdminMarketValuesRefreshResult): string {
  if (result.skipped) {
    return "Medie e Valore già aggiornati: voti, statistiche e storico non sono cambiati.";
  }
  return `Valore ricalcolato per ${plural(result.athletesValued, "calciatore", "calciatori")}: ${formatInteger(result.athletesWithCurrentAverage)} con la media della stagione in corso, ${formatInteger(result.athletesWithPreviousAverage)} con quella della stagione scorsa.`;
}

/**
 * Segue il job finché non finisce: chiede l'avanzamento, lo passa a `onUpdate`, aspetta e
 * ripete. Restituisce l'ultimo avanzamento (completato o fallito), o `null` se `shouldStop`
 * diventa vero (la schermata ha perso il focus): nessuna altra chiamata dopo.
 */
export async function pollSeasonHistoryJob({
  jobId,
  fetchProgress,
  onUpdate,
  shouldStop,
  wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  intervalMs = SEASON_HISTORY_POLL_INTERVAL_MS,
}: {
  jobId: string;
  fetchProgress: SeasonHistoryApi["fetchProgress"];
  onUpdate: (progress: AdminSeasonHistoryProgress) => void;
  shouldStop: () => boolean;
  wait?: (ms: number) => Promise<unknown>;
  intervalMs?: number;
}): Promise<AdminSeasonHistoryProgress | null> {
  for (;;) {
    if (shouldStop()) {
      return null;
    }
    const progress = await fetchProgress(jobId);
    if (shouldStop()) {
      return null;
    }
    onUpdate(progress);
    if (!isSeasonHistoryJobActive(progress.status)) {
      return progress;
    }
    await wait(intervalMs);
  }
}

/** Avanzamento di partenza dalla risposta di «Avvia import» (prima del primo giro). */
export function progressFromStart(response: AdminSeasonHistoryImportResponse): AdminSeasonHistoryProgress | null {
  if (!response.job) {
    return null;
  }
  return {
    jobId: response.job.jobId,
    status: isSeasonHistoryJobActive(response.job.status) ? (response.job.status as "queued" | "running") : "queued",
    percent: 0,
    stage: "queued",
    message: response.job.message,
    errorCode: null,
    result: null,
  };
}

/** Messaggio di un job fallito. */
export function failedJobText(progress: AdminSeasonHistoryProgress): string {
  if (progress.errorCode === "provider_key_missing") {
    return "Manca la chiave del fornitore: l'import non può partire.";
  }
  return progress.message?.trim() || "Import dello storico non riuscito.";
}
