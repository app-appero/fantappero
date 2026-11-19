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
const saveMyLineupMock = vi.fn();
const saveLineupDraftMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchMyLineup: (...args: unknown[]) => fetchMyLineupMock(...args),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
  applyBestLineup: vi.fn(),
  copyPreviousLineupToDraft: vi.fn(),
  discardLineupDraft: vi.fn(),
  saveLineupDraft: (...args: unknown[]) => saveLineupDraftMock(...args),
  saveMyLineup: (...args: unknown[]) => saveMyLineupMock(...args),
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

const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
// A7 è in esubero di ruolo (come A. Adams di qa-02): in rosa ma non schierabile.
const EXCESS_ID = "A7";
const ROSTER: LineupRosterPlayer[] = [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 7)].map(
  (athleteId, slotIndex) => ({
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotIndex,
    locked: false,
    exceedsRoleQuota: athleteId === EXCESS_ID,
  }),
);
const STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
// Panchina salvata dal server: tutta la rosa tranne i titolari e chi è in esubero.
const SAVED_BENCH = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8"];

function player(athleteId: string, slotKind: "starter" | "bench", sortOrder: number): LineupPlayer {
  return {
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotKind,
    sortOrder,
  };
}

function lineupContext(): LineupContext {
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
      starters: STARTERS.map((athleteId, index) => player(athleteId, "starter", index)),
      bench: SAVED_BENCH.map((athleteId, index) => player(athleteId, "bench", index)),
    },
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues: [],
  };
}

describe("FormationPage — calciatore in esubero di ruolo (QA 19/11, qa-02)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = <T extends Element = HTMLElement>(testId: string) =>
    container.querySelector<T>(`[data-testid="${testId}"]`);

  async function render() {
    fetchFantasyTurnsMock.mockResolvedValue([TURN]);
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

  async function click(testId: string) {
    const button = byTestId<HTMLButtonElement>(testId);
    expect(button).not.toBeNull();
    expect(button?.disabled).toBe(false);
    await act(async () => {
      button!.click();
    });
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchMyLineupMock.mockReset();
    saveMyLineupMock.mockReset().mockResolvedValue(lineupContext());
    saveLineupDraftMock.mockReset().mockResolvedValue(lineupContext());
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("appena aperta la formazione salvata non risulta modificata", async () => {
    await render();

    // Nessuna modifica non salvata: niente «Annulla modifiche», «Ripristina» o avviso sulle mosse.
    expect(byTestId<HTMLButtonElement>("formation-revert")?.disabled).toBe(true);
    expect(byTestId("formation-reset")).toBeNull();
    expect(byTestId("formation-moves-reason")).toBeNull();
    expect(byTestId("formation-issues")).toBeNull();
    // Si vede ancora, in fondo alla tribuna, ma non si sposta.
    const tribuna = byTestId("formation-bench-tribuna")?.textContent ?? "";
    expect(tribuna).toContain(`Giocatore ${EXCESS_ID}`);
    const lastIndex = SAVED_BENCH.length;
    expect(byTestId(`formation-bench-change-${lastIndex}`)?.textContent).toContain(`Giocatore ${EXCESS_ID}`);
    expect(byTestId<HTMLButtonElement>(`formation-bench-change-${lastIndex}`)?.disabled).toBe(true);
  });

  it("formazione e bozza si salvano senza di lui", async () => {
    await render();

    await click("formation-save");
    expect(saveMyLineupMock).toHaveBeenCalledTimes(1);
    expect(saveMyLineupMock.mock.calls[0]?.[3]).toEqual({
      module: "4-3-3",
      starterAthleteIds: STARTERS,
      benchAthleteIds: SAVED_BENCH,
    });

    await click("formation-draft");
    expect(saveLineupDraftMock).toHaveBeenCalledTimes(1);
    expect(saveLineupDraftMock.mock.calls[0]?.[3]).toEqual({
      module: "4-3-3",
      starterAthleteIds: STARTERS,
      benchAthleteIds: SAVED_BENCH,
    });
  });
});
