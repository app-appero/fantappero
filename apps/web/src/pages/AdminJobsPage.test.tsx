import type { SystemJob, SystemJobRunAllResult } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchSystemJobsMock = vi.fn();
const updateSystemJobMock = vi.fn();
const runSystemJobMock = vi.fn();
const runAllSystemJobsMock = vi.fn();
vi.mock("../api/admin", () => ({
  fetchSystemJobs: (...args: unknown[]) => fetchSystemJobsMock(...args),
  updateSystemJob: (...args: unknown[]) => updateSystemJobMock(...args),
  runSystemJob: (...args: unknown[]) => runSystemJobMock(...args),
  runAllSystemJobs: (...args: unknown[]) => runAllSystemJobsMock(...args),
}));

import { ApiError } from "../api/client";
import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { AdminJobsPage } from "./AdminJobsPage";

function job(overrides: Partial<SystemJob> = {}): SystemJob {
  return {
    key: "sports-data-sync-fixtures",
    title: "Calendario partite",
    description: "Scarica le partite.",
    task: "sports_data.sync_mvp_fixtures",
    enabled: true,
    intervalSeconds: 3600,
    minIntervalSeconds: 3600,
    maxIntervalSeconds: 604800,
    lastStartedAt: null,
    nextRunAt: null,
    usesProviderQuota: true,
    sendsNotifications: false,
    running: false,
    lastRun: null,
    ...overrides,
  };
}

const JOBS: SystemJob[] = [
  job(),
  job({
    key: "notifications-broadcast-dispatch",
    title: "Avvisi programmati",
    usesProviderQuota: false,
    sendsNotifications: true,
  }),
  job({ key: "market-trade-expiry", title: "Scadenza proposte di scambio", usesProviderQuota: false, enabled: false }),
];

describe("AdminJobsPage — Esegui e Esegui tutti (1.5)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchSystemJobsMock.mockReset();
    updateSystemJobMock.mockReset();
    runSystemJobMock.mockReset();
    runAllSystemJobsMock.mockReset();
    saveStoredSession({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { id: "user-1", displayName: "Operatore Test", globalRole: "global_operator" },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
    vi.useRealTimers();
  });

  function byTestId(testId: string): HTMLElement | null {
    return container.querySelector<HTMLElement>(`[data-testid="${testId}"]`);
  }

  function click(testId: string) {
    const element = byTestId(testId);
    expect(element, testId).not.toBeNull();
    return act(async () => {
      element!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  }

  async function renderPage(jobs: SystemJob[] = JOBS) {
    fetchSystemJobsMock.mockResolvedValue(jobs);
    await act(async () => {
      root.render(createElement(AdminJobsPage));
    });
  }

  it("shows «Esegui» on every job and «Esegui tutti» above them", async () => {
    await renderPage();

    for (const item of JOBS) {
      expect(byTestId(`admin-job-run-${item.key}`)?.textContent).toBe("Esegui");
    }
    expect(byTestId("admin-jobs-run-all")?.textContent).toBe("Esegui tutti");
  });

  it("asks «Sei sicuro?» with the provider quota notice for a job that uses it", async () => {
    await renderPage();

    await click("admin-job-run-sports-data-sync-fixtures");

    const text = byTestId("admin-jobs-confirm-text")!.textContent!;
    expect(container.textContent).toContain("Sei sicuro?");
    expect(text).toBe("Lancio «Calendario partite» adesso, una volta sola. Usa la quota del fornitore sportivo.");
    expect(runSystemJobMock).not.toHaveBeenCalled();
  });

  it("does not warn about the quota for a job that does not use it", async () => {
    await renderPage();

    await click("admin-job-run-notifications-broadcast-dispatch");

    const text = byTestId("admin-jobs-confirm-text")!.textContent!;
    expect(text).not.toContain("quota");
    expect(text).toContain("Può mandare avvisi ai fantallenatori.");
  });

  it("warns that a switched-off job runs once and stays off", async () => {
    await renderPage();

    await click("admin-job-run-market-trade-expiry");

    expect(byTestId("admin-jobs-confirm-text")!.textContent).toContain(
      "Il job è spento: parte lo stesso questa volta, poi resta spento.",
    );
  });

  it("runs one job after the confirmation and shows the started outcome with the off-job warning", async () => {
    await renderPage();
    runSystemJobMock.mockResolvedValue({
      key: "market-trade-expiry",
      title: "Scadenza proposte di scambio",
      status: "started",
      message: "«Scadenza proposte di scambio» lanciato: il giro è in coda e parte tra poco.",
      warning: "«Scadenza proposte di scambio» è spento: l'ho lanciato a mano una volta sola, non riparte da solo.",
      code: null,
      taskId: "t1",
    });

    await click("admin-job-run-market-trade-expiry");
    await click("admin-jobs-confirm-confirm");

    expect(runSystemJobMock).toHaveBeenCalledWith("token-123", "market-trade-expiry");
    const line = byTestId("admin-jobs-run-result-market-trade-expiry")!.textContent!;
    expect(line).toContain("lanciato: il giro è in coda");
    expect(line).toContain("è spento: l'ho lanciato a mano una volta sola");
    // Dopo il lancio l'elenco si rilegge (per «In esecuzione» e l'esito).
    expect(fetchSystemJobsMock).toHaveBeenCalledTimes(2);
  });

  it("does not run anything when the confirmation is cancelled", async () => {
    await renderPage();

    await click("admin-job-run-sports-data-sync-fixtures");
    await click("admin-jobs-confirm-cancel");

    expect(runSystemJobMock).not.toHaveBeenCalled();
    expect(byTestId("admin-jobs-confirm-text")).toBeNull();
  });

  it("says clearly that a job already running is not launched again", async () => {
    await renderPage();
    runSystemJobMock.mockRejectedValue(
      new ApiError(
        "«Calendario partite» è già in esecuzione: non lo rilancio.",
        409,
        "system_job_already_running",
      ),
    );

    await click("admin-job-run-sports-data-sync-fixtures");
    await click("admin-jobs-confirm-confirm");

    const line = byTestId("admin-jobs-run-result-sports-data-sync-fixtures")!;
    expect(line.textContent).toContain("già in esecuzione: non lo rilancio");
    expect(line.className).toContain("fa-run-result__line--warning");
  });

  it("disables «Esegui» and shows «In esecuzione» for a job that is running", async () => {
    await renderPage([job({ running: true }), job({ key: "x", title: "Altro" })]);

    expect(
      (byTestId("admin-job-run-sports-data-sync-fixtures") as HTMLButtonElement).disabled,
    ).toBe(true);
    expect((byTestId("admin-job-run-x") as HTMLButtonElement).disabled).toBe(false);
    expect(byTestId("admin-job-last-run-sports-data-sync-fixtures")!.textContent).toBe("In esecuzione");
  });

  it("shows the last outcome of a job, with the reason when it failed", async () => {
    await renderPage([
      job({
        lastRun: { outcome: "failed", finishedAt: "2026-11-28T10:00:00Z", reason: "Quota giornaliera finita." },
      }),
    ]);

    expect(byTestId("admin-job-last-run-sports-data-sync-fixtures")!.textContent).toContain(
      "Ultimo giro non riuscito: Quota giornaliera finita.",
    );
  });

  it("«Esegui tutti» lists only the active jobs, warns about the quota and leaves the off ones out", async () => {
    await renderPage();

    await click("admin-jobs-run-all");

    const text = byTestId("admin-jobs-confirm-text")!.textContent!;
    expect(text).toContain("Lancio ora tutti i 2 job attivi, una volta sola:");
    expect(text).toContain("• Calendario partite");
    expect(text).toContain("• Avvisi programmati");
    expect(text).not.toContain("• Scadenza proposte di scambio");
    expect(text).toContain("Questo usa la quota del fornitore sportivo: Calendario partite.");
    expect(text).toContain("Un job già in esecuzione non si rilancia. I job spenti restano fuori.");
  });

  it("«Esegui tutti» shows the outcome of every job and the summary", async () => {
    await renderPage();
    const result: SystemJobRunAllResult = {
      results: [
        {
          key: "sports-data-sync-fixtures",
          title: "Calendario partite",
          status: "started",
          message: "«Calendario partite» lanciato: il giro è in coda e parte tra poco.",
          warning: null,
          code: null,
          taskId: "a",
        },
        {
          key: "notifications-broadcast-dispatch",
          title: "Avvisi programmati",
          status: "already_running",
          message: "«Avvisi programmati» è già in esecuzione: non lo rilancio.",
          warning: null,
          code: "system_job_already_running",
          taskId: null,
        },
      ],
      started: 1,
      alreadyRunning: 1,
      failed: 0,
    };
    runAllSystemJobsMock.mockResolvedValue(result);

    await click("admin-jobs-run-all");
    await click("admin-jobs-confirm-confirm");

    expect(runAllSystemJobsMock).toHaveBeenCalledWith("token-123");
    expect(byTestId("admin-jobs-run-result-summary")!.textContent).toBe(
      "Avviato 1 job su 2 · 1 già in esecuzione, non rilanciato.",
    );
    expect(byTestId("admin-jobs-run-result-sports-data-sync-fixtures")!.textContent).toContain(
      "lanciato",
    );
    expect(byTestId("admin-jobs-run-result-notifications-broadcast-dispatch")!.textContent).toContain(
      "già in esecuzione",
    );
  });

  it("«Esegui tutti» is disabled when no job is active", async () => {
    await renderPage([job({ enabled: false })]);

    expect((byTestId("admin-jobs-run-all") as HTMLButtonElement).disabled).toBe(true);
  });

  it("rereads the list while a job is running and stops when it has finished", async () => {
    vi.useFakeTimers();
    fetchSystemJobsMock.mockResolvedValueOnce([job({ running: true })]);
    await act(async () => {
      root.render(createElement(AdminJobsPage));
    });
    expect(fetchSystemJobsMock).toHaveBeenCalledTimes(1);

    fetchSystemJobsMock.mockResolvedValue([
      job({ lastRun: { outcome: "ok", finishedAt: "2026-11-28T10:00:00Z", reason: null } }),
    ]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100);
    });

    expect(fetchSystemJobsMock).toHaveBeenCalledTimes(2);
    expect(byTestId("admin-job-last-run-sports-data-sync-fixtures")!.textContent).toContain(
      "Ultimo giro riuscito",
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(fetchSystemJobsMock).toHaveBeenCalledTimes(2);
  });
});
