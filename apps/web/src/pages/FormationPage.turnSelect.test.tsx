import {
  approvedModuleCatalog,
  type FantasyTurnSummary,
  type LineupContext,
  type SessionUser,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFantasyTurnsMock = vi.fn();
const fetchMyLineupMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchMyLineup: (...args: unknown[]) => fetchMyLineupMock(...args),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
  applyBestLineup: vi.fn(),
  copyPreviousLineupToDraft: vi.fn(),
  discardLineupDraft: vi.fn(),
  saveLineupDraft: vi.fn(),
  saveMyLineup: vi.fn(),
}));
vi.mock("../auth/AuthContext", () => ({
  // Fantallenatore della lega (non operatore): vede e modifica la propria formazione.
  useAuth: () => ({
    isDemoMode: false,
    activeLeagueId: "league-1",
    can: (permissions: string[]) => !permissions.includes("global:operate"),
  }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { FormationPage } from "./FormationPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

function turn(number: number, overrides: Partial<FantasyTurnSummary> = {}): FantasyTurnSummary {
  return {
    id: `turn-${number}`,
    leagueId: "league-1",
    number,
    kind: "weekend",
    windowStartAt: `2026-11-${String(number).padStart(2, "0")}T22:00:00.000Z`,
    windowEndAt: `2026-11-${String(number + 2).padStart(2, "0")}T22:00:00.000Z`,
    opensAt: null,
    closesAt: null,
    cutoffAt: `2026-11-${String(number + 1).padStart(2, "0")}T14:00:00.000Z`,
    status: "scheduled",
    effectiveStatus: "scheduled",
    skipReason: null,
    fixtureCount: 10,
    generatedAt: "2026-11-01T08:00:00.000Z",
    modificationAllowed: true,
    matchStatus: "scheduled",
    ...overrides,
  };
}

// Come i turni 1-10 della lega di prova (corsa M3, 22/11): nati dopo le loro partite, il ciclo
// di vita resta «scheduled» ma le partite sono tutte finite.
const played = (number: number) => turn(number, { matchStatus: "completed", modificationAllowed: false });
const TURNS: FantasyTurnSummary[] = [
  played(1),
  played(2),
  turn(3, {
    status: "skipped",
    effectiveStatus: "skipped",
    skipReason: "Soglia non raggiunta: 1 squadra sotto il 75% dei titolari.",
    modificationAllowed: false,
  }),
  played(10),
  turn(11),
  turn(12),
];

function lineupContext(): LineupContext {
  return {
    leagueId: "league-1",
    roundId: "turn-11",
    roundNumber: 11,
    kind: "weekend",
    cutoffAt: "2026-11-12T14:00:00.000Z",
    status: "scheduled",
    effectiveStatus: "scheduled",
    modificationAllowed: true,
    lineupLockMarginMinutes: 0,
    modules: approvedModuleCatalog(),
    roster: [],
    lineup: null,
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues: [],
  };
}

describe("Formazione › menù «Turno»: i turni già giocati si leggono «Completato» (come l'app, M3 22/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const select = () => container.querySelector<HTMLSelectElement>('[data-testid="formation-round"]');

  async function render() {
    fetchFantasyTurnsMock.mockResolvedValue(TURNS);
    fetchMyLineupMock.mockResolvedValue(lineupContext());
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/formazione"],
          children: createElement(ToastProvider, { children: createElement(FormationPage) }),
        }),
      );
    });
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchMyLineupMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("le voci usano lo stato mostrato in Turni, non lo stato interno «Programmato»", async () => {
    await render();
    const labels = Array.from(select()?.options ?? [], (option) => option.textContent);
    expect(labels).toEqual([
      "Turno 1 (Completato)",
      "Turno 2 (Completato)",
      "Turno 3 (Turno saltato)",
      "Turno 10 (Completato)",
      "Turno 11 (Prossimo)",
      "Turno 12 (Da disputare)",
    ]);
    expect(labels.some((label) => label?.includes("Programmato"))).toBe(false);
  });
});
