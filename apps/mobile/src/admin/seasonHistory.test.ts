import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type {
  AdminMarketValuesRefreshResult,
  AdminSeasonHistoryEstimate,
  AdminSeasonHistoryImportResponse,
  AdminSeasonHistoryProgress,
  AdminSeasonHistoryResult,
} from "@fantappero/contracts";
import {
  currentSeasonYear,
  estimateHeadline,
  estimateSeasonLines,
  failedJobText,
  isSeasonHistoryJobActive,
  marketValuesText,
  parseSeasonYearInput,
  pollSeasonHistoryJob,
  progressFromStart,
  progressText,
  resultLines,
  startImportConfirmMessage,
  stopReasonText,
  type SeasonHistoryApi,
} from "./seasonHistory.ts";

const estimate: AdminSeasonHistoryEstimate = {
  seasonYear: 2026,
  seasons: [
    {
      seasonYear: 2025,
      seasonLabel: "25/26",
      leaguePagesDone: 0,
      leaguePagesRemaining: 200,
      leaguePagesExact: false,
      listoneAthletes: 2500,
      athletesWithRows: 0,
      athletesChecked: 0,
      athletesToFill: 625,
      athletesToFillExact: false,
      rowsStored: 0,
      estimatedCalls: 825,
    },
    {
      seasonYear: 2024,
      seasonLabel: "24/25",
      leaguePagesDone: 40,
      leaguePagesRemaining: 1,
      leaguePagesExact: true,
      listoneAthletes: 2500,
      athletesWithRows: 1900,
      athletesChecked: 0,
      athletesToFill: 1,
      athletesToFillExact: true,
      rowsStored: 2100,
      estimatedCalls: 825,
    },
  ],
  estimatedCalls: 1650,
  estimatedMinutes: 6,
  requestsPerMinute: 300,
};

const values: AdminMarketValuesRefreshResult = {
  seasonYear: 2026,
  skipped: false,
  currentSeasonRows: 900,
  athletesValued: 2500,
  athletesWithHistory: 2100,
  athletesWithCurrentAverage: 800,
  athletesWithPreviousAverage: 1300,
  computedAt: "2026-11-22T21:00:00Z",
};

const result: AdminSeasonHistoryResult = {
  seasonYear: 2026,
  seasons: [2025, 2024],
  calls: 1650,
  leaguePages: 400,
  athletesChecked: 1250,
  athletesFound: 1100,
  rowsCreated: 5200,
  rowsUpdated: 0,
  snapshotsCreated: 1650,
  errors: 0,
  stoppedReason: null,
  message: "Fatto",
  marketValues: values,
  remaining: null,
};

function progress(overrides: Partial<AdminSeasonHistoryProgress>): AdminSeasonHistoryProgress {
  return {
    jobId: "job-1",
    status: "running",
    percent: 0,
    stage: "league_pages",
    message: "Pagine di campionato 25/26",
    errorCode: null,
    result: null,
    ...overrides,
  };
}

/** API finta: registra le chiamate e restituisce gli avanzamenti in fila. */
function fakeApi(progresses: AdminSeasonHistoryProgress[]) {
  const calls: string[] = [];
  const queue = [...progresses];
  const api: SeasonHistoryApi = {
    estimate: async (seasonYear) => {
      calls.push(`estimate:${seasonYear}`);
      return { dryRun: true, estimate, job: null } satisfies AdminSeasonHistoryImportResponse;
    },
    start: async (seasonYear) => {
      calls.push(`start:${seasonYear}`);
      return { dryRun: false, estimate, job: { jobId: "job-1", status: "queued", message: "In coda" } };
    },
    fetchActive: async () => {
      calls.push("active");
      return queue[0] ?? null;
    },
    fetchProgress: async (jobId) => {
      calls.push(`progress:${jobId}`);
      const next = queue.shift();
      if (!next) {
        throw new Error("nessun avanzamento");
      }
      return next;
    },
    refreshValues: async (seasonYear) => {
      calls.push(`values:${seasonYear}`);
      return values;
    },
  };
  return { api, calls };
}

describe("storico stagioni: anno e testi", () => {
  it("stagione in corso di default: da luglio quella nuova", () => {
    assert.equal(currentSeasonYear(new Date(2026, 10, 22)), 2026);
    assert.equal(currentSeasonYear(new Date(2027, 2, 1)), 2026);
    assert.equal(currentSeasonYear(new Date(2027, 6, 1)), 2027);
  });

  it("anno scritto dall'operatore", () => {
    assert.equal(parseSeasonYearInput(" 2026 "), 2026);
    assert.equal(parseSeasonYearInput("26"), null);
    assert.equal(parseSeasonYearInput("1999"), null);
    assert.equal(parseSeasonYearInput("abcd"), null);
  });

  it("conto delle chiamate", () => {
    assert.equal(estimateHeadline(estimate), "Circa 1.650 chiamate al fornitore, circa 6 minuti (300 al minuto).");
    assert.deepEqual(estimateSeasonLines(estimate), [
      "25/26: 200 pagine di campionato (stima), 625 calciatori da cercare (stima) · 825 chiamate",
      "24/25: 1 pagina di campionato, 1 calciatore da cercare · 825 chiamate",
    ]);
    assert.equal(
      estimateHeadline({ ...estimate, estimatedCalls: 0, estimatedMinutes: 0 }),
      "Storico già completo: rilanciare l'import non costa chiamate.",
    );
    assert.match(startImportConfirmMessage(2026, estimate), /stagioni 25\/26 e 24\/25 .*Circa 1\.650 chiamate/);
    assert.match(startImportConfirmMessage(2026, null), /due stagioni prima della 2026/);
  });

  it("motivi di stop, risultato e ricalcolo", () => {
    assert.match(stopReasonText("max_calls") ?? "", /tetto di chiamate/);
    assert.match(stopReasonText("quota_reserve") ?? "", /15%/);
    assert.equal(stopReasonText(null), null);
    assert.deepEqual(resultLines(result), [
      "1.650 chiamate al fornitore: 5.200 righe create, 0 aggiornate, 1.100 calciatori trovati su 1.250 cercati.",
      "Valore ricalcolato per 2.500 calciatori: 800 con la media della stagione in corso, 1.300 con quella della stagione scorsa.",
    ]);
    const stopped = resultLines({ ...result, stoppedReason: "max_calls", remaining: estimate, marketValues: null, errors: 2 });
    assert.equal(stopped.length, 4);
    assert.match(stopped[1] ?? "", /2 errori/);
    assert.match(stopped[3] ?? "", /^Resta da scaricare: Circa 1\.650 chiamate/);
    assert.match(marketValuesText({ ...values, skipped: true }), /già aggiornati/);
    assert.equal(failedJobText(progress({ status: "failed", errorCode: "provider_key_missing" })), "Manca la chiave del fornitore: l'import non può partire.");
    assert.equal(progressText(progress({ percent: 42 })), "Pagine di campionato 25/26 (42%)");
  });
});

describe("storico stagioni: flusso con l'API finta", () => {
  it("conta, avvia e segue il job fino alla fine", async () => {
    const { api, calls } = fakeApi([
      progress({ status: "queued", percent: 0 }),
      progress({ percent: 40 }),
      progress({ status: "completed", percent: 100, result }),
    ]);

    const dry = await api.estimate(2026);
    assert.equal(dry.dryRun, true);
    assert.equal(dry.job, null);

    const started = await api.start(2026);
    const initial = progressFromStart(started);
    assert.equal(initial?.jobId, "job-1");
    assert.equal(isSeasonHistoryJobActive(initial?.status), true);

    const seen: number[] = [];
    const waits: number[] = [];
    const final = await pollSeasonHistoryJob({
      jobId: initial?.jobId ?? "",
      fetchProgress: api.fetchProgress,
      onUpdate: (next) => seen.push(next.percent),
      shouldStop: () => false,
      wait: async (ms) => {
        waits.push(ms);
      },
    });
    assert.equal(final?.status, "completed");
    assert.deepEqual(seen, [0, 40, 100]);
    assert.deepEqual(waits, [2000, 2000]);
    assert.deepEqual(calls, ["estimate:2026", "start:2026", "progress:job-1", "progress:job-1", "progress:job-1"]);
    assert.equal(resultLines(final?.result as AdminSeasonHistoryResult)[0]?.startsWith("1.650 chiamate"), true);
  });

  it("smette di chiedere quando la schermata perde il focus", async () => {
    const { api, calls } = fakeApi([progress({ percent: 10 }), progress({ percent: 20 }), progress({ percent: 30 })]);
    let focused = true;
    const final = await pollSeasonHistoryJob({
      jobId: "job-1",
      fetchProgress: api.fetchProgress,
      onUpdate: () => undefined,
      shouldStop: () => !focused,
      wait: async () => {
        focused = false;
      },
    });
    assert.equal(final, null);
    assert.deepEqual(calls, ["progress:job-1"]);
  });

  it("un job fallito ferma il giro", async () => {
    const { api } = fakeApi([progress({ status: "failed", message: "Errore del fornitore" })]);
    const final = await pollSeasonHistoryJob({
      jobId: "job-1",
      fetchProgress: api.fetchProgress,
      onUpdate: () => undefined,
      shouldStop: () => false,
      wait: async () => undefined,
    });
    assert.equal(final?.status, "failed");
    assert.equal(failedJobText(final as AdminSeasonHistoryProgress), "Errore del fornitore");
  });

  it("import già in corso (altro operatore) e ricalcolo dei valori", async () => {
    const { api, calls } = fakeApi([progress({ percent: 55 })]);
    const active = await api.fetchActive();
    assert.equal(isSeasonHistoryJobActive(active?.status), true);
    assert.equal(marketValuesText(await api.refreshValues(2026)).startsWith("Valore ricalcolato per 2.500"), true);
    assert.deepEqual(calls, ["active", "values:2026"]);
    assert.equal(progressFromStart({ dryRun: true, estimate, job: null }), null);
  });
});
