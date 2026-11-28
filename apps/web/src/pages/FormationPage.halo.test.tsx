import {
  approvedModuleCatalog,
  type FantasyTurnSummary,
  type LineupContext,
  type LineupRole,
  type LineupRosterPlayer,
  type SessionUser,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFantasyTurnsMock = vi.fn();
const fetchMyLineupMock = vi.fn();

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  apiRequest: vi.fn(),
}));
vi.mock("../api/leagues", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/leagues")>()),
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchMyLineup: (...args: unknown[]) => fetchMyLineupMock(...args),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
  copyPreviousLineupToDraft: vi.fn(),
  discardLineupDraft: vi.fn(),
  saveLineupDraft: vi.fn(),
  saveMyLineup: vi.fn(),
}));
vi.mock("../auth/AuthContext", () => ({
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

const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
const ROSTER_IDS = [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 6)];

// Indizi come li manda il server: P1 titolare probabile, D1 possibile panchina, D2 indisponibile,
// D3 senza dato (come Cissè, De Winter, Norton-Cuffy, Gabriel nella segnalazione del 27/11).
const HINTS: Record<string, Partial<LineupRosterPlayer>> = {
  P1: { probableHint: "starter", probableNote: "Titolare probabile" },
  D1: { probableHint: "bench", probableNote: "Possibile panchina" },
  D2: { probableHint: "unavailable", probableNote: "Infortunato", probableAbsence: "injured" },
};

const ROSTER: LineupRosterPlayer[] = ROSTER_IDS.map((athleteId, slotIndex) => ({
  athleteId,
  athleteName: `Giocatore ${athleteId}`,
  role: athleteId[0] as LineupRole,
  slotIndex,
  locked: false,
  ...HINTS[athleteId],
}));
const STARTERS_433 = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
const BENCH_433 = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8"];

const CONTEXT: LineupContext = {
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
  roster: ROSTER,
  lineup: null,
  previousLineup: null,
  draft: {
    module: "4-3-3",
    starterAthleteIds: STARTERS_433,
    benchAthleteIds: BENCH_433,
    savedAt: "2026-11-19T10:00:00.000Z",
  },
  copyAvailable: false,
  copyIssues: [],
  issues: [],
};

describe("FormationPage — alone in campo anche senza dato (Rosario, 27/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const pitchPlayer = (index: number) =>
    container.querySelector<HTMLElement>(`[data-testid="pitch-player-starter-${index}"]`);

  async function render() {
    fetchFantasyTurnsMock.mockResolvedValue([TURN]);
    fetchMyLineupMock.mockResolvedValue(CONTEXT);
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

  it("chi non ha il dato ha l'alone neutro, gli altri il loro colore", async () => {
    await render();

    expect(pitchPlayer(0)?.className).toContain("fa-pitch-player--probable");
    expect(pitchPlayer(0)?.className).not.toContain("fa-pitch-player--no-info");
    expect(pitchPlayer(1)?.className).toContain("fa-pitch-player--bench");
    expect(pitchPlayer(2)?.className).toContain("fa-pitch-player--unavailable");
    expect(pitchPlayer(3)?.className).toContain("fa-pitch-player--no-info");
    for (const index of [0, 1, 2]) {
      expect(pitchPlayer(index)?.className).not.toContain("fa-pitch-player--no-info");
    }
  });

  it("la legenda ha la voce «Nessuna informazione»", async () => {
    await render();

    const legend = container.querySelector('[data-testid="formation-legend"]');
    expect(legend?.textContent).toContain("Titolare probabile");
    expect(legend?.textContent).toContain("Indisponibile");
    const none = container.querySelector('[data-testid="formation-legend-none"]');
    expect(none?.textContent).toBe("Nessuna informazione");
    expect(none?.querySelector(".fa-formation-legend__dot--none")).not.toBeNull();
  });
});
