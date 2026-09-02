import type { AdminLeagueTurnStatus } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAdminLeagueTurnStatusMock = vi.fn();
const calculateCurrentRoundsAllLeaguesMock = vi.fn();
const repairHistoricalRoundsMock = vi.fn();
vi.mock("../api/admin", () => ({
  fetchAdminLeagueTurnStatus: (...args: unknown[]) => fetchAdminLeagueTurnStatusMock(...args),
  generateAllAiLineups: vi.fn(),
  syncAllLeagueTurns: vi.fn(),
  syncCalendarForAllLeagues: vi.fn(),
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
});
