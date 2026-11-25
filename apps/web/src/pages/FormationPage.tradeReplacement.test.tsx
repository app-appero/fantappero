import {
  approvedModuleCatalog,
  type FantasyTurnSummary,
  type LineupContext,
  type LineupRole,
  type LineupRosterPlayer,
  type ReplacementBanner,
  type SessionUser,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFantasyTurnsMock = vi.fn();
const fetchMyLineupMock = vi.fn();
const openReplacementMock = vi.fn();
let replacementBannerValue: ReplacementBanner | null = null;

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
vi.mock("../market/TradeReplacementContext", () => ({
  useTradeReplacement: () => ({
    status: null,
    banner: replacementBannerValue,
    open: openReplacementMock,
    refresh: vi.fn(),
  }),
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
// 34/35 dopo uno scambio 2 per 1: manca un difensore.
const ROSTER: LineupRosterPlayer[] = [...ids("P", 3), ...ids("D", 10), ...ids("C", 11), ...ids("A", 10)].map(
  (athleteId, slotIndex) => ({
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotIndex,
    locked: false,
  }),
);

const BLOCK =
  "Rosa incompleta: 34 giocatori su 35. Dopo lo scambio ti manca 1 Difensore: scegli il sostituto per schierare la formazione.";

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
    lineup: null,
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues: [{ code: "roster_not_validated", message: BLOCK }],
  };
}

describe("FormationPage — sostituto dopo lo scambio sbilanciato (1.5)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = (id: string) => container.querySelector(`[data-testid="${id}"]`);

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
    for (let index = 0; index < 6; index += 1) {
      // eslint-disable-next-line no-await-in-loop
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchMyLineupMock.mockReset();
    openReplacementMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
    replacementBannerValue = null;
  });

  it("riquadro arancione, pulsante che riapre la scelta e «Salva formazione» spento con la nota", async () => {
    replacementBannerValue = {
      title: "Rosa incompleta: 34/35",
      body: "Ti manca un Difensore dopo lo scambio. Sceglilo per poter schierare la formazione.",
      action: "Scegli il sostituto (Difensore)",
      blockedMessage: null,
    };
    await render();
    const banner = byTestId("formation-replacement-banner");
    expect(banner?.textContent).toContain("Rosa incompleta: 34/35");
    expect(banner?.textContent).toContain("Ti manca un Difensore dopo lo scambio. Sceglilo per poter schierare la formazione.");
    // Il riquadro del sostituto prende il posto di quello generico della rosa bloccata.
    expect(byTestId("formation-roster-blocked")).toBeNull();
    expect((byTestId("formation-save") as HTMLButtonElement | null)?.disabled).toBe(true);
    expect(byTestId("formation-replacement-note")?.textContent).toBe(
      "Se non scegli entro il blocco, gioca la formazione automatica.",
    );
    const choose = byTestId("formation-replacement-banner-choose") as HTMLButtonElement | null;
    expect(choose?.textContent).toBe("Scegli il sostituto (Difensore)");
    await act(async () => {
      choose?.click();
    });
    expect(openReplacementMock).toHaveBeenCalledTimes(1);
  });

  it("senza sostituto da scegliere resta l'avviso della rosa bloccata di prima", async () => {
    await render();
    expect(byTestId("formation-replacement-banner")).toBeNull();
    expect(byTestId("formation-replacement-note")).toBeNull();
    expect(byTestId("formation-roster-blocked")?.textContent).toContain(BLOCK);
  });
});
