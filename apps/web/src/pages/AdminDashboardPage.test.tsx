import type { AdminOverview } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchOverviewMock = vi.fn();

vi.mock("../api/admin", () => ({
  fetchAdminOverview: (...args: unknown[]) => fetchOverviewMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "t", refreshToken: "r", user: { id: "u" } }),
}));

import { MemoryRouter } from "../router/simpleRouter";
import { AdminDashboardPage } from "./AdminDashboardPage";

const HOUR = 3_600_000;

function overview(): AdminOverview {
  const now = Date.now();
  return {
    operatorId: "op-1",
    operatorDisplayName: "Rosario",
    environment: "development",
    usersCount: 23,
    operatorsCount: 2,
    leaguesCount: 4,
    leaguesByState: { active: 2, auction: 1, draft: 1 },
    watch: {
      generatedAt: new Date(now).toISOString(),
      testerRequestsPending: 3,
      oldestTesterRequestAt: new Date(now - 50 * HOUR).toISOString(),
      feedbackNew: 2,
      latestFeedbackAt: new Date(now - 2 * HOUR).toISOString(),
      jobsDisabled: [{ key: "fantasy-lineups-generate-ai", title: "Formazioni IA" }],
      jobFailuresSince: new Date(now - 24 * HOUR).toISOString(),
      jobFailures: [
        {
          jobKey: "sports-poll-late",
          title: "Correzioni tardive",
          failedAt: new Date(now - 6 * HOUR).toISOString(),
          reason: "Fornitore sportivo: troppe richieste, limite raggiunto (ProviderRateLimitError).",
          failures: 1,
          lastOutcome: "failed",
          lastFinishedAt: new Date(now - 6 * HOUR).toISOString(),
        },
      ],
      listoneLastUpdate: {
        updatedAt: new Date(now - 72 * HOUR).toISOString(),
        seasonYear: 2026,
        kind: "refresh",
        source: "operator",
        authorDisplayName: "Rosario",
        leagueName: null,
        added: 3,
        removed: 1,
        changed: 12,
      },
      currentRounds: { activeLeagues: 2, leaguesInProgress: 2, roundNumbers: [12] },
      nextLineupLock: {
        lockAt: new Date(now + 4 * HOUR).toISOString(),
        leagueId: "l1",
        leagueName: "Lega del Lunedì",
        roundNumber: 12,
      },
      androidAppVersion: {
        latestVersionName: "1.3.0",
        latestVersionCode: 4,
        downloadUrl: "https://example.com/app.apk",
        message: null,
      },
    },
  };
}

describe("AdminDashboardPage — Riepilogo 1.4", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchOverviewMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function render() {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/admin"],
          children: createElement(AdminDashboardPage),
        }),
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it("mostra chi sei, i numeri, le leghe per stato e le sei righe di «Da guardare»", async () => {
    fetchOverviewMock.mockResolvedValue(overview());
    await render();

    expect(container.querySelector("h1")?.textContent).toMatch(/Riepilogo/i);
    expect(container.querySelector('[data-testid="admin-overview-name"]')?.textContent).toBe(
      "Rosario",
    );
    expect(container.querySelector('[data-testid="admin-overview-users"]')?.textContent).toBe("23");
    expect(
      container.querySelector('[data-testid="admin-overview-league-states"]')?.textContent,
    ).toBe("Leghe: 2 in corso · 1 all'asta · 1 in preparazione");

    const rows = Array.from(container.querySelectorAll('[data-testid^="admin-watch-"]')).filter(
      (node) => node.tagName === "LI",
    );
    expect(rows.map((row) => row.getAttribute("data-testid"))).toEqual([
      "admin-watch-testers",
      "admin-watch-feedback",
      "admin-watch-jobs",
      "admin-watch-listone",
      "admin-watch-rounds",
      "admin-watch-app-version",
    ]);
    const jobs = container.querySelector('[data-testid="admin-watch-jobs"]');
    expect(jobs?.getAttribute("data-tone")).toBe("bad");
    expect(jobs?.textContent).toContain("1 job spento: Formazioni IA");
    expect(jobs?.textContent).toContain("Errore in «Correzioni tardive»");
    expect(jobs?.textContent).toContain("ProviderRateLimitError");
    expect(jobs?.querySelector("a")?.getAttribute("href")).toBe("/admin/job");

    const listone = container.querySelector('[data-testid="admin-watch-listone"]');
    expect(listone?.textContent).toContain("da Rosario");
    expect(listone?.textContent).toContain("3 nuovi, 1 tolto, 12 cambiati");

    const rounds = container.querySelector('[data-testid="admin-watch-rounds"]');
    expect(rounds?.textContent).toContain("Giornata 12 in corso in 2 leghe su 2");
    expect(rounds?.textContent).toContain("Prossimo blocco formazioni:");
    expect(rounds?.textContent).toContain("Lega del Lunedì, giornata 12");

    const version = container.querySelector('[data-testid="admin-watch-app-version"] a');
    expect(version?.getAttribute("href")).toBe("/admin/versione-app");
    expect(container.querySelector('[data-testid="admin-watch-testers"] a')?.getAttribute("href")).toBe(
      "/admin/utenti",
    );
    // Le schede che ripetevano il menù non ci sono più.
    expect(container.textContent).not.toContain("Promuovi, revoca, impersona");
    expect(container.querySelector('[data-testid="admin-appversion"]')).toBeNull();
  });

  it("con un server che non manda «Da guardare» restano identità e numeri", async () => {
    const { watch: _watch, leaguesByState: _states, ...old } = overview();
    fetchOverviewMock.mockResolvedValue(old);
    await render();

    expect(container.querySelector('[data-testid="admin-dashboard-success"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="admin-watch-unavailable"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="admin-overview-league-states"]')).toBeNull();
  });

  it("senza permessi mostra il pannello non disponibile", async () => {
    const { ApiError } = await import("../api/client");
    fetchOverviewMock.mockRejectedValue(new ApiError("forbidden", 403, "forbidden"));
    await render();
    expect(container.querySelector('[data-testid="admin-dashboard-error"]')?.textContent).toContain(
      "Non hai i permessi",
    );
  });
});
