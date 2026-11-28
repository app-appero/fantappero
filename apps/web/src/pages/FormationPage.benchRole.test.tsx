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
// 4-4-2: 11 titolari, 12 in panchina (i primi 10 attivi) e il resto in tribuna.
const STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "C4", "A1", "A2"];
const BENCH = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "P3", "D8", "C8", "A5"];
// Due indisponibili: uno in panchina (D6) e uno in tribuna (D8).
const UNAVAILABLE = new Set(["D6", "D8"]);

function rosterRow(athleteId: string, slotIndex: number): LineupRosterPlayer {
  return {
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotIndex,
    locked: false,
    ...(UNAVAILABLE.has(athleteId)
      ? { selectionBlocked: true, probableHint: "unavailable" as const, probableAbsence: "injured" as const }
      : {}),
  };
}

function player(athleteId: string, slotKind: "starter" | "bench", sortOrder: number): LineupPlayer {
  return { athleteId, athleteName: `Giocatore ${athleteId}`, role: athleteId[0] as LineupRole, slotKind, sortOrder };
}

const CONTEXT: LineupContext = {
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
  roster: [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 5)].map(rosterRow),
  lineup: {
    id: "lineup-1",
    module: "4-4-2",
    revision: 1,
    submittedAt: "2026-11-19T09:00:00.000Z",
    systemGeneratedAi: false,
    aiAlgorithmVersion: null,
    aiDecidedAt: null,
    starters: STARTERS.map((athleteId, index) => player(athleteId, "starter", index)),
    bench: BENCH.map((athleteId, index) => player(athleteId, "bench", index)),
  },
  previousLineup: null,
  draft: null,
  copyAvailable: false,
  copyIssues: [],
  issues: [],
};

describe("Formazione sul sito: il ruolo (P, D, C, A) si vede in panchina e in tribuna (Rosario 27/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset().mockResolvedValue([TURN]);
    fetchMyLineupMock.mockReset().mockResolvedValue(CONTEXT);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/formazione"],
          children: createElement(ToastProvider, { children: createElement(FormationPage) }),
        }),
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  const rowsOf = (listTestId: string) =>
    [...container.querySelectorAll<HTMLElement>(`[data-testid="${listTestId}"] .fa-bench-order__row`)];

  /** Sigla e colore del ruolo prima del nome, come in Rosa (P verde, D ambra, C azzurro, A rosso). */
  const roleBadge = (row: HTMLElement) => row.querySelector<HTMLElement>(".fa-starter-row .fa-badge");

  it("ogni riga della panchina ha la sigla del ruolo prima del nome", () => {
    const rows = rowsOf("formation-bench-panchina");
    expect(rows).toHaveLength(10);
    const expected = BENCH.slice(0, 10).map((id) => id[0]);
    expect(rows.map((row) => roleBadge(row)?.textContent)).toEqual(expected);
    for (const row of rows) {
      const badge = roleBadge(row)!;
      const name = row.querySelector(".fa-starter-row__name")!;
      // La sigla viene prima del nome, nella stessa riga.
      expect(badge.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it("anche la tribuna ha la sigla, compreso chi è indisponibile", () => {
    const rows = rowsOf("formation-bench-tribuna");
    expect(rows).toHaveLength(3);
    expect(rows.map((row) => roleBadge(row)?.textContent)).toEqual(BENCH.slice(10).map((id) => id[0]));
    expect(rows.map((row) => row.querySelector(".fa-starter-row__name")?.textContent)).toContain("Giocatore D8");
    // Il difensore indisponibile (D8) in tribuna ha comunque il suo cerchio ambra.
    const unavailable = rows.find((row) => row.textContent?.includes("Giocatore D8"))!;
    expect(roleBadge(unavailable)?.textContent).toBe("D");
    expect(roleBadge(unavailable)?.classList.contains("fa-badge--warning")).toBe(true);
  });

  it("i colori sono quelli del ruolo: portiere verde, difensore ambra, centrocampista azzurro, attaccante rosso", () => {
    const all = [...rowsOf("formation-bench-panchina"), ...rowsOf("formation-bench-tribuna")];
    const variantByRole: Record<string, string> = {
      P: "fa-badge--success",
      D: "fa-badge--warning",
      C: "fa-badge--accent",
      A: "fa-badge--danger",
    };
    for (const row of all) {
      const badge = roleBadge(row)!;
      expect(badge.classList.contains(variantByRole[badge.textContent ?? ""] ?? "mai")).toBe(true);
    }
  });
});
