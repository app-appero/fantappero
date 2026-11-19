import {
  approvedModuleCatalog,
  type FantasyTurnSummary,
  type LineupContext,
  type LineupPlayer,
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

const NOTICE =
  "N. Zortea non è più nella tua rosa: è stato tolto dalla formazione, scegli chi mettere al suo posto.";

const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
// D2 è stato ceduto: al suo posto in rosa c'è D9, arrivato con lo scambio.
const ROSTER_IDS = [...ids("P", 3), ...ids("D", 9).filter((id) => id !== "D2"), ...ids("C", 8), ...ids("A", 6)];
const ROSTER: LineupRosterPlayer[] = ROSTER_IDS.map((athleteId, slotIndex) => ({
  athleteId,
  athleteName: `Giocatore ${athleteId}`,
  role: athleteId[0] as LineupRole,
  slotIndex,
  locked: false,
}));
const BENCH_IDS = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8", "D9"];

function player(athleteId: string, slotKind: "starter" | "bench", sortOrder: number): LineupPlayer {
  return {
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotKind,
    sortOrder,
  };
}

function lineupContext(issues: LineupContext["issues"]): LineupContext {
  // Formazione 4-3-3 salvata con D2 terzo titolare: il server l'ha tolto, il suo posto è vuoto.
  const starters = ["P1", "D1", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"].map((athleteId, index) =>
    player(athleteId, "starter", index < 2 ? index : index + 1),
  );
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
    roster: ROSTER,
    lineup: {
      id: "lineup-1",
      module: "4-3-3",
      revision: 1,
      submittedAt: "2026-11-19T09:00:00.000Z",
      systemGeneratedAi: false,
      aiAlgorithmVersion: null,
      aiDecidedAt: null,
      starters,
      bench: BENCH_IDS.slice(0, -1).map((athleteId, index) => player(athleteId, "bench", index)),
    },
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues,
  };
}

describe("FormationPage — calciatore non più in rosa (QA 19/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const notices = () => container.querySelector('[data-testid="formation-roster-notices"]');
  const starterName = (index: number) =>
    container.querySelector(`[data-testid="formation-starter-${index}"] .fa-starter-row__name`)?.textContent;

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

  it("dice chi è stato tolto e lascia vuoto il suo posto, senza far scalare gli altri", async () => {
    await render(
      lineupContext([
        { code: "lineup_athlete_left_roster", message: NOTICE },
        { code: "missing_athlete", message: "Ogni slot della formazione deve contenere un calciatore." },
      ]),
    );

    expect(notices()?.textContent).toContain(NOTICE);
    expect(starterName(1)).toBe("Giocatore D1");
    expect(starterName(2)).toBe("Seleziona calciatore");
    expect(starterName(3)).toBe("Giocatore D3");
    expect(starterName(5)).toBe("Giocatore C1");
    expect(starterName(10)).toBe("Giocatore A3");
    // Il posto vuoto passa dal flusso «mancano calciatori» già esistente.
    const issues = container.querySelector('[data-testid="formation-issues"]')?.textContent ?? "";
    expect(issues).toContain("La formazione deve avere esattamente 11 titolari (attuali: 10).");
    expect(container.querySelector<HTMLButtonElement>('[data-testid="formation-save"]')?.disabled).toBe(true);
  });

  it("senza l'avviso del server non mostra nulla", async () => {
    await render(lineupContext([]));
    expect(notices()).toBeNull();
  });
});
