import type {
  AdminMarketValuesRefreshResult,
  AdminSeasonHistoryEstimate,
  AdminSeasonHistoryImportResponse,
  AdminSeasonHistoryProgress,
} from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * «Storico stagioni» nel Listone del pannello operatore (1.3): conto delle chiamate (dryRun),
 * avvio con conferma, avanzamento ogni pochi secondi e «Ricalcola valori». Il fetch è finto:
 * si controllano URL e corpo delle richieste, nessuna chiamata vera.
 */

const ESTIMATE: AdminSeasonHistoryEstimate = {
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
  ],
  estimatedCalls: 1650,
  estimatedMinutes: 6,
  requestsPerMinute: 300,
};

const DRY_RUN: AdminSeasonHistoryImportResponse = { dryRun: true, estimate: ESTIMATE, job: null };
const STARTED: AdminSeasonHistoryImportResponse = {
  dryRun: false,
  estimate: ESTIMATE,
  job: { jobId: "job-42", status: "queued", message: "Import dello storico in coda." },
};

const RUNNING: AdminSeasonHistoryProgress = {
  jobId: "job-42",
  status: "running",
  percent: 35,
  stage: "league_pages",
  message: "Pagine di campionato: 140 di 400",
  errorCode: null,
  result: null,
};

const DONE: AdminSeasonHistoryProgress = {
  jobId: "job-42",
  status: "completed",
  percent: 100,
  stage: "done",
  message: "Fatto",
  errorCode: null,
  result: {
    seasonYear: 2026,
    seasons: [2025, 2024],
    calls: 1648,
    leaguePages: 398,
    athletesChecked: 1250,
    athletesFound: 1100,
    rowsCreated: 5200,
    rowsUpdated: 0,
    snapshotsCreated: 1648,
    errors: 2,
    stoppedReason: null,
    message: "Storico importato.",
    marketValues: {
      seasonYear: 2026,
      skipped: false,
      currentSeasonRows: 800,
      athletesValued: 2480,
      athletesWithHistory: 2100,
      athletesWithCurrentAverage: 600,
      athletesWithPreviousAverage: 1500,
      computedAt: "2026-11-22T20:00:00Z",
    },
    remaining: null,
  },
};

const VALUES: AdminMarketValuesRefreshResult = {
  seasonYear: 2026,
  skipped: false,
  currentSeasonRows: 800,
  athletesValued: 2480,
  athletesWithHistory: 2100,
  athletesWithCurrentAverage: 600,
  athletesWithPreviousAverage: 1500,
  computedAt: "2026-11-22T20:00:00Z",
};

vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token-op" }),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

import { SEASON_HISTORY_POLL_MS, SeasonHistoryPanel } from "./SeasonHistoryPanel";

type Call = { url: string; method: string; body: unknown };

describe("Storico stagioni (pannello operatore)", () => {
  let container: HTMLDivElement;
  let root: Root;
  let calls: Call[];
  let routes: Array<(call: Call) => unknown | undefined>;

  function respond(body: unknown, status = 200): Response {
    return new Response(body === null ? "null" : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  }

  beforeEach(() => {
    calls = [];
    routes = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        const call: Call = {
          url: url.replace("http://localhost:59999", ""),
          method: init?.method ?? "GET",
          body: init?.body ? JSON.parse(String(init.body)) : undefined,
        };
        calls.push(call);
        for (const route of routes) {
          const body = route(call);
          if (body !== undefined) {
            return respond(body);
          }
        }
        return respond({ message: "non previsto" }, 500);
      }),
    );
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function flush() {
    for (let index = 0; index < 5; index += 1) {
      await act(async () => {
        await Promise.resolve();
      });
    }
  }

  async function mount() {
    await act(async () => {
      root.render(createElement(SeasonHistoryPanel, { defaultSeasonYear: 2026 }));
    });
    await flush();
  }

  async function click(id: string) {
    await act(async () => {
      byTestId(id)?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await flush();
  }

  it("«Calcola chiamate» chiede solo il conto (dryRun) e lo mostra", async () => {
    routes.push((call) => (call.method === "GET" && call.url === "/admin/listone/storico" ? null : undefined));
    routes.push((call) => (call.method === "POST" && call.url === "/admin/listone/storico" ? DRY_RUN : undefined));
    await mount();
    expect((container.querySelector('input[name="admin-season-history-year"]') as HTMLInputElement).value).toBe(
      "2026",
    );
    expect(byTestId("admin-season-history-start")).toBeNull();

    await click("admin-season-history-estimate-button");
    const post = calls.find((call) => call.method === "POST");
    expect(post).toEqual({ url: "/admin/listone/storico", method: "POST", body: { seasonYear: 2026, dryRun: true } });
    expect(byTestId("admin-season-history-summary")?.textContent).toContain("2025/26 e 2024/25");
    expect(byTestId("admin-season-history-summary")?.textContent).toContain("1.650 chiamate");
    expect(byTestId("admin-season-history-summary")?.textContent).toContain("circa 6 minuti");
    expect(byTestId("admin-season-history-season-2025")?.textContent).toContain("(stima)");
    expect(byTestId("admin-season-history-start")?.textContent).toBe("Avvia import");
  });

  it("«Avvia import» chiede conferma, avvia (dryRun false) e segue l'avanzamento ogni pochi secondi", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    let progressCalls = 0;
    routes.push((call) => (call.method === "GET" && call.url === "/admin/listone/storico" ? null : undefined));
    routes.push((call) => {
      if (call.method !== "POST" || call.url !== "/admin/listone/storico") return undefined;
      return (call.body as { dryRun?: boolean }).dryRun === false ? STARTED : DRY_RUN;
    });
    routes.push((call) => {
      if (call.url !== "/admin/listone/storico/job-42") return undefined;
      progressCalls += 1;
      return progressCalls === 1 ? RUNNING : DONE;
    });
    await mount();
    await click("admin-season-history-estimate-button");

    await click("admin-season-history-start");
    expect(byTestId("admin-season-history-confirm")?.textContent).toContain("1.650 chiamate");
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);
    await click("admin-season-history-confirm-no");
    expect(byTestId("admin-season-history-confirm")).toBeNull();

    await click("admin-season-history-start");
    await click("admin-season-history-confirm-yes");
    const start = calls.filter((call) => call.method === "POST")[1];
    expect(start).toEqual({ url: "/admin/listone/storico", method: "POST", body: { seasonYear: 2026, dryRun: false } });
    expect(byTestId("admin-season-history-progress")?.textContent).toContain("Import in corso");
    expect(byTestId("admin-season-history-estimate-button")?.hasAttribute("disabled")).toBe(true);
    expect(progressCalls).toBe(0);

    await act(async () => {
      vi.advanceTimersByTime(SEASON_HISTORY_POLL_MS);
    });
    await flush();
    expect(progressCalls).toBe(1);
    expect(byTestId("admin-season-history-progress")?.textContent).toContain("Pagine di campionato: 140 di 400");
    expect(byTestId("admin-season-history-progress")?.textContent).toContain("35%");

    await act(async () => {
      vi.advanceTimersByTime(SEASON_HISTORY_POLL_MS);
    });
    await flush();
    expect(progressCalls).toBe(2);
    expect(byTestId("admin-season-history-progress")).toBeNull();
    expect(byTestId("admin-season-history-done")?.textContent).toContain("Storico importato.");
    expect(byTestId("admin-season-history-done")?.textContent).toContain("Valori ricalcolati: 2.480 calciatori.");

    // Finito: niente più richieste.
    await act(async () => {
      vi.advanceTimersByTime(SEASON_HISTORY_POLL_MS * 3);
    });
    await flush();
    expect(progressCalls).toBe(2);
  });

  it("un import già in corso (anche di un altro operatore) si vede subito e si segue", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    routes.push((call) => (call.method === "GET" && call.url === "/admin/listone/storico" ? RUNNING : undefined));
    routes.push((call) =>
      call.url === "/admin/listone/storico/job-42"
        ? { ...DONE, result: { ...DONE.result!, stoppedReason: "quota_reserve", remaining: { ...ESTIMATE, estimatedCalls: 400 } } }
        : undefined,
    );
    await mount();
    expect(byTestId("admin-season-history-progress")?.textContent).toContain("35%");
    await act(async () => {
      vi.advanceTimersByTime(SEASON_HISTORY_POLL_MS);
    });
    await flush();
    const done = byTestId("admin-season-history-done")?.textContent ?? "";
    expect(done).toContain("Import fermato prima della fine");
    expect(done).toContain("sotto il 15%");
    expect(done).toContain("restano 400 chiamate");
  });

  it("«Ricalcola valori» rifà medie e Valore della stagione scelta", async () => {
    routes.push((call) => (call.method === "GET" && call.url === "/admin/listone/storico" ? null : undefined));
    routes.push((call) => (call.url === "/admin/listone/valori/ricalcola" ? VALUES : undefined));
    await mount();
    await click("admin-season-history-values");
    expect(calls.find((call) => call.url === "/admin/listone/valori/ricalcola")).toEqual({
      url: "/admin/listone/valori/ricalcola",
      method: "POST",
      body: { seasonYear: 2026 },
    });
    expect(byTestId("admin-season-history-values-done")?.textContent).toContain(
      "Valore calcolato per 2.480 calciatori",
    );
  });

  it("import fallito senza chiave del fornitore: lo dice chiaro", async () => {
    routes.push((call) =>
      call.method === "GET" && call.url === "/admin/listone/storico"
        ? { ...RUNNING, status: "failed", errorCode: "provider_key_missing", message: "x" }
        : undefined,
    );
    await mount();
    expect(byTestId("admin-season-history-failed")?.textContent).toContain("Manca la chiave del fornitore");
  });
});
