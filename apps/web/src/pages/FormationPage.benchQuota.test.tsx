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

// Turno non ancora aperto (come la «lega demo» di Rosario, 20/11): nessun blocco.
const TURN: FantasyTurnSummary = {
  id: "turn-3",
  leagueId: "league-1",
  number: 3,
  kind: "weekend",
  windowStartAt: "2026-11-27T22:00:00.000Z",
  windowEndAt: "2026-12-01T22:00:00.000Z",
  opensAt: null,
  closesAt: null,
  cutoffAt: "2026-11-29T14:00:00.000Z",
  status: "scheduled",
  effectiveStatus: "scheduled",
  skipReason: null,
  fixtureCount: 10,
  generatedAt: "2026-11-18T08:00:00.000Z",
  modificationAllowed: true,
  matchStatus: "scheduled",
};

const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
// 4-4-2. L'attaccante che era 8° in panchina è stato ceduto: la panchina salvata si è
// ricompattata e il primo della tribuna (il terzo portiere, P3) è salito al 10° posto.
// Al suo posto in rosa è arrivato A5, che oggi non prende il voto (infortunato): non è
// nella formazione salvata.
const NEWCOMER = "A5";
const STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "C4", "A1", "A2"];
const SAVED_BENCH = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "P3", "D8", "C8"];

function rosterRow(athleteId: string, slotIndex: number, extra: Partial<LineupRosterPlayer> = {}): LineupRosterPlayer {
  return {
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotIndex,
    locked: false,
    ...extra,
  };
}

function roster(newcomer: Partial<LineupRosterPlayer>): LineupRosterPlayer[] {
  return [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 5)].map((athleteId, slotIndex) =>
    rosterRow(athleteId, slotIndex, athleteId === NEWCOMER ? newcomer : {}),
  );
}

function player(athleteId: string, slotKind: "starter" | "bench", sortOrder: number): LineupPlayer {
  return { athleteId, athleteName: `Giocatore ${athleteId}`, role: athleteId[0] as LineupRole, slotKind, sortOrder };
}

function lineupContext(rows: LineupRosterPlayer[], bench: string[] = SAVED_BENCH): LineupContext {
  return {
    leagueId: "league-1",
    roundId: "turn-3",
    roundNumber: 3,
    kind: "weekend",
    cutoffAt: "2026-11-29T14:00:00.000Z",
    status: "scheduled",
    effectiveStatus: "scheduled",
    modificationAllowed: true,
    lineupLockMarginMinutes: 0,
    modules: approvedModuleCatalog(),
    roster: rows,
    lineup: {
      id: "lineup-1",
      module: "4-4-2",
      revision: 1,
      submittedAt: "2026-11-19T09:00:00.000Z",
      systemGeneratedAi: false,
      aiAlgorithmVersion: null,
      aiDecidedAt: null,
      starters: STARTERS.map((athleteId, index) => player(athleteId, "starter", index)),
      bench: bench.map((athleteId, index) => player(athleteId, "bench", index)),
    },
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues: [],
  };
}

describe("FormationPage — panchina con un portiere al posto di un attaccante (Rosario, 20/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = <T extends Element = HTMLElement>(testId: string) =>
    container.querySelector<T>(`[data-testid="${testId}"]`);

  /** La panchina come la mostra la pagina: un id per posto, in ordine. */
  const shownBench = () => {
    const out: string[] = [];
    for (let index = 0; ; index += 1) {
      const row = byTestId(`formation-bench-change-${index}`);
      if (!row) {
        return out;
      }
      const match = /Giocatore (\w+)/.exec(row.textContent ?? "");
      out.push(match?.[1] ?? "?");
    }
  };

  async function render(context: LineupContext) {
    fetchFantasyTurnsMock.mockResolvedValue([TURN]);
    fetchMyLineupMock.mockResolvedValue(context);
    saveMyLineupMock.mockResolvedValue(context);
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
    saveMyLineupMock.mockReset();
    saveLineupDraftMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  const INJURED: Partial<LineupRosterPlayer> = {
    selectionBlocked: true,
    probableHint: "unavailable",
    probableAbsence: "injured",
  };

  it("l'attaccante appena arrivato che non prende il voto non alza la quota: si salva così", async () => {
    // Prima: errore «mancano: 1 attaccante», e «Sistema la panchina» non cambiava niente perché
    // lui tornava sempre in coda. Ora, come sul server, chi non prende il voto non conta.
    await render(lineupContext(roster(INJURED)));

    expect(shownBench()).toEqual([...SAVED_BENCH, NEWCOMER]);
    expect(byTestId("formation-issues")).toBeNull();
    await click("formation-save");
    expect(saveMyLineupMock.mock.calls[0]?.[3]).toEqual({
      module: "4-4-2",
      starterAthleteIds: STARTERS,
      benchAthleteIds: [...SAVED_BENCH, NEWCOMER],
    });
  });

  it("il posto scelto per chi è arrivato dopo e non prende il voto resta (bozza, formazione migliore)", async () => {
    const placed = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", NEWCOMER, "P3", "D8", "C8"];
    const context = lineupContext(roster(INJURED));
    await render({
      ...context,
      draft: {
        module: "4-4-2",
        starterAthleteIds: STARTERS,
        benchAthleteIds: placed,
        savedAt: "2026-11-20T15:00:00.000Z",
        copySourceRoundId: null,
      },
    });

    // Prima tornava in coda alla tribuna e al 10° posto risaliva il portiere.
    expect(shownBench()).toEqual(placed);
  });

  it("«Sistema la panchina» fa salire l'attaccante della tribuna al posto del portiere", async () => {
    await render(lineupContext(roster({})));

    expect(shownBench()).toEqual([...SAVED_BENCH, NEWCOMER]);
    expect(byTestId("formation-issues")?.textContent).toContain("mancano: 1 attaccante");

    await click("formation-fix-bench");

    // L'attaccante prende il 10° posto, il portiere torna primo della tribuna; gli altri restano.
    const fixed = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", NEWCOMER, "P3", "D8", "C8"];
    expect(shownBench()).toEqual(fixed);
    expect(byTestId("formation-issues")).toBeNull();

    await click("formation-save");
    expect(saveMyLineupMock).toHaveBeenCalledTimes(1);
    expect(saveMyLineupMock.mock.calls[0]?.[3]).toEqual({
      module: "4-4-2",
      starterAthleteIds: STARTERS,
      benchAthleteIds: fixed,
    });
  });

  it("«Cambia» sul portiere al 10° posto propone anche l'attaccante della tribuna", async () => {
    // Formazione sporca con l'attaccante già in tribuna (salvata prima della correzione).
    await render(lineupContext(roster({}), [...SAVED_BENCH, NEWCOMER]));

    await click("formation-bench-change-9");
    const option = byTestId<HTMLButtonElement>(`formation-bench-pick-9-${NEWCOMER}`);
    expect(option).not.toBeNull();
    expect(option?.textContent).toContain("Tribuna");
    await act(async () => {
      option!.click();
    });

    expect(shownBench().slice(0, 10)).toEqual(["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", NEWCOMER]);
    expect(shownBench()).toContain("P3");
    expect(byTestId("formation-issues")).toBeNull();
  });

  it("chi è in esubero di ruolo non conta: nessun errore e il portiere può restare al 10° posto", async () => {
    // L'unico altro attaccante è in esubero: in panchina non può andare, quindi la regola chiede
    // solo i 2 attaccanti schierabili (come il server).
    await render(lineupContext(roster({ exceedsRoleQuota: true })));

    expect(shownBench()).toEqual([...SAVED_BENCH, NEWCOMER]);
    expect(byTestId("formation-issues")).toBeNull();
    expect(byTestId("formation-fix-bench")).toBeNull();
  });
});
