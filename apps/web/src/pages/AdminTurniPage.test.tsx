import type { AdminLeagueTurnStatus, TurniBatch } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAdminLeagueTurnStatusMock = vi.fn();
const calculateCurrentRoundsAllLeaguesMock = vi.fn();
const repairHistoricalRoundsMock = vi.fn();
const refreshPredictedLineupsMock = vi.fn();
const runTurniBatchMock = vi.fn();
vi.mock("../api/admin", () => ({
  runTurniBatch: (...args: unknown[]) => runTurniBatchMock(...args),
  fetchAdminLeagueTurnStatus: (...args: unknown[]) => fetchAdminLeagueTurnStatusMock(...args),
  generateAllAiLineups: vi.fn(),
  syncAllLeagueTurns: vi.fn(),
  syncCalendarForAllLeagues: vi.fn(),
  refreshPredictedLineups: (...args: unknown[]) => refreshPredictedLineupsMock(...args),
  calculateCurrentRoundsAllLeagues: (...args: unknown[]) =>
    calculateCurrentRoundsAllLeaguesMock(...args),
  repairHistoricalRounds: (...args: unknown[]) => repairHistoricalRoundsMock(...args),
}));

const calculateCurrentRoundMock = vi.fn();
vi.mock("../api/leagues", () => ({
  openFantasyTurn: vi.fn(),
  recalculateFantasyTurnCutoff: vi.fn(),
  runAiLineups: vi.fn(),
  calculateCurrentRound: (...args: unknown[]) => calculateCurrentRoundMock(...args),
}));

import { ApiError } from "../api/client";
import { saveStoredSession, clearStoredSession } from "../auth/sessionStorage";
import { AdminTurniPage } from "./AdminTurniPage";

const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype,
  "value",
)!.set!;

/** React tracks the native value setter to detect real input changes — setting
 * `.value` directly and dispatching a plain Event is invisible to it. */
function typeInto(input: HTMLInputElement, value: string): void {
  nativeInputValueSetter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function league(overrides: Partial<AdminLeagueTurnStatus> = {}): AdminLeagueTurnStatus {
  return {
    leagueId: "league-1",
    leagueName: "Lega Uno",
    currentRoundId: "round-1",
    currentRoundNumber: 3,
    currentRoundStatus: "open",
    homologationStatus: "provisional",
    calendarUpdatedAt: null,
    ...overrides,
  };
}

describe("AdminTurniPage (EP-turni-calcolo)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchAdminLeagueTurnStatusMock.mockReset();
    calculateCurrentRoundsAllLeaguesMock.mockReset();
    repairHistoricalRoundsMock.mockReset();
    refreshPredictedLineupsMock.mockReset();
    runTurniBatchMock.mockReset();
    calculateCurrentRoundMock.mockReset();
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
  });

  it("renders the legend and the leagues table once loaded", async () => {
    fetchAdminLeagueTurnStatusMock.mockResolvedValue([
      league(),
      league({ leagueId: "league-2", leagueName: "Lega Due" }),
    ]);

    await act(async () => {
      root.render(createElement(AdminTurniPage));
    });

    expect(container.querySelector('[data-testid="admin-turni-legend"]')).not.toBeNull();
    expect(container.textContent).toContain("Calcola giornata corrente");
    expect(container.textContent).toContain("Aggiorna probabili");
    expect(container.querySelector('[data-testid="admin-turni-refresh-predicted"]')).not.toBeNull();
    expect(container.textContent).toContain("Lega Uno");
    expect(container.textContent).toContain("Lega Due");
  });

  it("filters the leagues table by search query", async () => {
    fetchAdminLeagueTurnStatusMock.mockResolvedValue([
      league({ leagueId: "league-1", leagueName: "Lega Alfa" }),
      league({ leagueId: "league-2", leagueName: "Lega Beta" }),
    ]);

    await act(async () => {
      root.render(createElement(AdminTurniPage));
    });

    const input = container.querySelector<HTMLInputElement>(
      '[data-testid="admin-turni-search"]',
    );
    expect(input).not.toBeNull();

    await act(async () => {
      typeInto(input!, "beta");
    });

    expect(container.textContent).not.toContain("Lega Alfa");
    expect(container.textContent).toContain("Lega Beta");
  });

  it("calculates the current round for all leagues from the global button", async () => {
    fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
    calculateCurrentRoundsAllLeaguesMock.mockResolvedValue({
      roundsConsidered: 2,
      roundsProcessed: 2,
      roundsFinalized: 1,
      fixturesScored: 10,
      errors: [],
    });

    await act(async () => {
      root.render(createElement(AdminTurniPage));
    });

    const button = container.querySelector<HTMLButtonElement>(
      '[data-testid="admin-turni-calculate-all"]',
    );
    expect(button).not.toBeNull();

    await act(async () => {
      button!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(calculateCurrentRoundsAllLeaguesMock).toHaveBeenCalledWith("token-123");
    expect(container.textContent).toContain("omologati: 1");
  });

  it("calculates a single league's current round from the row action", async () => {
    fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
    calculateCurrentRoundMock.mockResolvedValue({
      roundId: "round-1",
      roundNumber: 3,
      fixturesScored: 4,
      fallbackResolvedFromDraft: 0,
      fallbackResolvedFromPreviousRound: 0,
      fallbackResolvedAsZero: 1,
      resultFinal: true,
      homologated: true,
    });

    await act(async () => {
      root.render(createElement(AdminTurniPage));
    });

    const button = container.querySelector<HTMLButtonElement>(
      '[data-testid="admin-turni-calculate-league-1"]',
    );
    expect(button).not.toBeNull();

    await act(async () => {
      button!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(calculateCurrentRoundMock).toHaveBeenCalledWith("token-123", "league-1", "round-1");
    expect(container.textContent).toContain("Turno 3 calcolato e omologato.");
  });

  it("refreshes probable lineups from the operator panel", async () => {
    fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
    refreshPredictedLineupsMock.mockResolvedValue({
      fixturesConsidered: 2,
      matchesLinked: 2,
      snapshotsSaved: 1,
      skippedRecent: 0,
      skippedUnmatched: 1,
      rejected: 0,
      warnings: 0,
      requestsMade: 3,
      message: null,
    });

    await act(async () => {
      root.render(createElement(AdminTurniPage));
    });

    const button = container.querySelector<HTMLButtonElement>(
      '[data-testid="admin-turni-refresh-predicted"]',
    );
    expect(button).not.toBeNull();

    await act(async () => {
      button!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(refreshPredictedLineupsMock).toHaveBeenCalledWith("token-123");
    expect(container.textContent).toContain("1 salvate, 1 senza corrispondenza");
  });

  it("disables the historical repair button until a reason is entered", async () => {
    fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);

    await act(async () => {
      root.render(createElement(AdminTurniPage));
    });

    const button = container.querySelector<HTMLButtonElement>(
      '[data-testid="admin-turni-repair-all"]',
    );
    expect(button).not.toBeNull();
    expect(button!.disabled).toBe(true);

    const reasonInput = container.querySelector<HTMLInputElement>(
      '[name="admin-turni-repair-reason"]',
    );
    expect(reasonInput).not.toBeNull();

    await act(async () => {
      typeInto(reasonInput!, "Recupero storico");
    });

    expect(button!.disabled).toBe(false);
  });

  describe("Esegui tutti", () => {
    function click(testId: string) {
      const element = container.querySelector<HTMLButtonElement>(`[data-testid="${testId}"]`);
      expect(element, testId).not.toBeNull();
      return act(async () => {
        element!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }

    function batchOf(overrides: Partial<TurniBatch> = {}): TurniBatch {
      return {
        batchId: "batch-1",
        status: "completed",
        operations: [
          { key: "importa-stagione", label: "Importa calendario stagione", status: "ok", message: "Stagioni create: 0." },
          { key: "genera-calendario", label: "Genera calendario", status: "failed", message: "Quota del fornitore finita." },
          { key: "sincronizza-turni", label: "Sincronizza turni", status: "ok", message: "Leghe: 2." },
          { key: "formazioni-probabili", label: "Aggiorna probabili", status: "skipped", message: "Saltata: già in esecuzione." },
          { key: "formazioni-ia", label: "Genera formazioni IA", status: "ok", message: "Turni processati: 1." },
        ],
        ok: 3,
        failed: 1,
        skipped: 1,
        startedAt: null,
        finishedAt: null,
        ...overrides,
      };
    }

    it("asks «Sei sicuro?» with the list of operations and the provider quota notice", async () => {
      fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
      await act(async () => {
        root.render(createElement(AdminTurniPage));
      });

      expect(container.querySelector('[data-testid="admin-turni-run-all-confirm-text"]')).toBeNull();
      await click("admin-turni-run-all");

      const text = container.querySelector('[data-testid="admin-turni-run-all-confirm-text"]');
      expect(text).not.toBeNull();
      expect(container.textContent).toContain("Sei sicuro?");
      for (const label of [
        "Importa calendario stagione",
        "Genera calendario",
        "Sincronizza turni",
        "Aggiorna probabili",
        "Genera formazioni IA",
      ]) {
        expect(text!.textContent).toContain(`• ${label}`);
      }
      expect(text!.textContent).toContain("la quota del fornitore sportivo");
      expect(text!.textContent).toContain("Non omologa nessun turno");
      expect(runTurniBatchMock).not.toHaveBeenCalled();
    });

    it("does nothing when the confirmation is cancelled", async () => {
      fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
      await act(async () => {
        root.render(createElement(AdminTurniPage));
      });

      await click("admin-turni-run-all");
      await click("admin-turni-run-all-confirm-cancel");

      expect(runTurniBatchMock).not.toHaveBeenCalled();
      expect(container.querySelector('[data-testid="admin-turni-run-all-confirm-text"]')).toBeNull();
    });

    it("runs the batch and shows the outcome of every operation and the summary", async () => {
      fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
      runTurniBatchMock.mockResolvedValue(batchOf());
      await act(async () => {
        root.render(createElement(AdminTurniPage));
      });

      await click("admin-turni-run-all");
      await click("admin-turni-run-all-confirm-confirm");
      await act(async () => {
        await Promise.resolve();
      });

      expect(runTurniBatchMock).toHaveBeenCalledTimes(1);
      expect(runTurniBatchMock.mock.calls[0]![0]).toBe("token-123");
      const result = container.querySelector('[data-testid="admin-turni-run-all-result"]');
      expect(result).not.toBeNull();
      expect(
        container.querySelector('[data-testid="admin-turni-run-all-result-summary"]')!.textContent,
      ).toBe("Riuscite 3 operazioni su 5 · 1 non riuscita · 1 saltata.");
      expect(
        container.querySelector('[data-testid="admin-turni-run-all-result-genera-calendario"]')!
          .textContent,
      ).toContain("Non riuscita: Quota del fornitore finita.");
      expect(
        container.querySelector('[data-testid="admin-turni-run-all-result-sincronizza-turni"]')!
          .textContent,
      ).toContain("Riuscita: Leghe: 2.");
      expect(
        container.querySelector('[data-testid="admin-turni-run-all-result-formazioni-probabili"]')!
          .textContent,
      ).toContain("Saltata");
      // A fine blocco la tabella delle leghe si rilegge.
      expect(fetchAdminLeagueTurnStatusMock).toHaveBeenCalledTimes(2);
    });

    it("shows the progress while the operations run", async () => {
      fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
      let finish: (batch: TurniBatch) => void = () => undefined;
      runTurniBatchMock.mockImplementation(
        (_token: string, options: { onProgress: (batch: TurniBatch) => void }) =>
          new Promise<TurniBatch>((resolve) => {
            options.onProgress(
              batchOf({
                status: "running",
                operations: [
                  { key: "importa-stagione", label: "Importa calendario stagione", status: "ok", message: "Fatto." },
                  { key: "genera-calendario", label: "Genera calendario", status: "running", message: null },
                  { key: "sincronizza-turni", label: "Sincronizza turni", status: "pending", message: null },
                ],
                ok: 1,
                failed: 0,
                skipped: 0,
              }),
            );
            finish = resolve;
          }),
      );
      await act(async () => {
        root.render(createElement(AdminTurniPage));
      });

      await click("admin-turni-run-all");
      await click("admin-turni-run-all-confirm-confirm");

      expect(
        container.querySelector('[data-testid="admin-turni-run-all-result-summary"]')!.textContent,
      ).toBe("In corso: 1 operazione su 3 finite.");
      expect(
        container.querySelector('[data-testid="admin-turni-run-all-result-genera-calendario"]')!
          .textContent,
      ).toContain("In corso");
      expect(
        container.querySelector<HTMLButtonElement>('[data-testid="admin-turni-run-all"]')!.disabled,
      ).toBe(true);

      await act(async () => {
        finish(batchOf({ failed: 0, skipped: 0, ok: 5 }));
        await Promise.resolve();
      });
      expect(
        container.querySelector<HTMLButtonElement>('[data-testid="admin-turni-run-all"]')!.disabled,
      ).toBe(false);
    });

    it("shows the server message when the batch is refused (already running)", async () => {
      fetchAdminLeagueTurnStatusMock.mockResolvedValue([league()]);
      runTurniBatchMock.mockRejectedValue(
        new ApiError(
          "Le operazioni dei turni sono già in corso: aspetta che finiscano prima di rilanciarle.",
          409,
          "turni_batch_already_running",
        ),
      );
      await act(async () => {
        root.render(createElement(AdminTurniPage));
      });

      await click("admin-turni-run-all");
      await click("admin-turni-run-all-confirm-confirm");
      await act(async () => {
        await Promise.resolve();
      });

      expect(
        container.querySelector('[data-testid="admin-turni-run-all-error"]')!.textContent,
      ).toContain("già in corso");
    });
  });
});
