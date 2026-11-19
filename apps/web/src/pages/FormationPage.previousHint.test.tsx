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

const USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

const TURN: FantasyTurnSummary = {
  id: "turn-2",
  leagueId: "league-1",
  number: 2,
  kind: "weekend",
  windowStartAt: "2026-11-20T22:00:00.000Z",
  windowEndAt: "2026-11-24T22:00:00.000Z",
  opensAt: null,
  closesAt: null,
  cutoffAt: "2026-11-22T14:00:00.000Z",
  status: "open",
  effectiveStatus: "open",
  skipReason: null,
  fixtureCount: 10,
  generatedAt: "2026-11-18T08:00:00.000Z",
  modificationAllowed: true,
  matchStatus: "scheduled",
};

function lineupContext(overrides: Partial<LineupContext>): LineupContext {
  return {
    leagueId: "league-1",
    roundId: "turn-2",
    roundNumber: 2,
    kind: "weekend",
    cutoffAt: "2026-11-22T14:00:00.000Z",
    status: "open",
    effectiveStatus: "open",
    modificationAllowed: true,
    lineupLockMarginMinutes: 0,
    modules: approvedModuleCatalog(),
    roster: [],
    lineup: null,
    previousLineup: {
      roundId: "turn-1",
      roundNumber: 1,
      module: "4-3-3",
      starters: [],
      bench: [],
    },
    draft: null,
    copyAvailable: true,
    copyIssues: [],
    issues: [],
    ...overrides,
  };
}

describe("FormationPage — avviso «Formazione precedente disponibile»", () => {
  let container: HTMLDivElement;
  let root: Root;

  const hint = () => container.querySelector('[data-testid="formation-previous-hint"]');
  const copyButton = () => container.querySelector('[data-testid="formation-copy"]');

  async function render(context: LineupContext) {
    fetchFantasyTurnsMock.mockResolvedValue([TURN]);
    fetchMyLineupMock.mockResolvedValue(context);
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

  it("non lo mostra se la formazione precedente c'è ma non si può copiare", async () => {
    await render(lineupContext({ copyAvailable: false }));
    expect(container.querySelector('[data-testid="formation-cutoff"]')).not.toBeNull();
    expect(copyButton()).toBeNull();
    expect(hint()).toBeNull();
  });

  it("lo mostra insieme al tasto «Copia formazione precedente» quando la copia è possibile", async () => {
    await render(lineupContext({ copyAvailable: true }));
    expect(copyButton()).not.toBeNull();
    expect(hint()?.textContent).toContain("Formazione precedente disponibile: turno 1");
  });

  it("non lo mostra senza formazione precedente", async () => {
    await render(lineupContext({ copyAvailable: true, previousLineup: null }));
    expect(hint()).toBeNull();
  });
});
