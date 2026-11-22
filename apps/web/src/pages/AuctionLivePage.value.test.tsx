import type { FantasyTeamSummary, LiveAuctionSession, LiveLot, LiveLotState } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Asta live (1.3): il Valore del lotto è solo mostrato, mai messo nel rilancio. */

// Dati usati dentro `vi.mock`, che sale in cima al file: vanno preparati con `vi.hoisted`.
const { SESSION, TEAMS, STATE } = vi.hoisted(() => {
  const session: LiveAuctionSession = {
    id: "session-1",
    leagueId: "league-1",
    status: "open",
    opensAt: "2026-11-22T10:00:00.000Z",
    closesAt: "2026-11-22T12:00:00.000Z",
    nominationMode: "manual",
    minIncrementCredits: 1,
    softCloseSeconds: 15,
    lotDurationSeconds: 30,
    operatorUserId: "someone-else",
    queueRemaining: 0,
    pendingSwapCount: 0,
    turnOrder: [],
  };
  const lot: LiveLot = {
    id: "lot-1",
    sessionId: "session-1",
    athleteId: "ferraro",
    athleteName: "M. Ferraro",
    photoUrl: null,
    sequenceNumber: 1,
    status: "open",
    openedAt: "2026-11-22T10:05:00.000Z",
    closesAt: "2026-11-22T10:05:30.000Z",
    minIncrementCredits: 1,
    currentLeaderTeamId: "team-2",
    currentLeaderTeamName: "Bomber FC",
    currentAmountCredits: 12,
    minimumNextAmountCredits: 13,
    closedAt: null,
    marketValue: 58,
    seasonAverage: { value: 6.85, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true },
  };
  const team = (id: string, userId: string, name: string): FantasyTeamSummary => ({
    id,
    leagueId: "league-1",
    membershipId: `m-${id}`,
    userId,
    userType: "human",
    name,
    rosterSize: 25,
    filledSlots: 3,
    compositionStatus: "incomplete",
  });
  const state: LiveLotState = {
    session,
    currentLot: lot,
    recentRaises: [],
    secondsRemaining: 20,
    pendingSwap: null,
    currentTurnTeamId: null,
    currentTurnTeamName: null,
  };
  return {
    SESSION: session,
    TEAMS: [team("team-1", "user-1", "Io"), team("team-2", "user-2", "Bomber FC")],
    STATE: state,
  };
});

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    isDemoMode: false,
    activeLeagueId: "league-1",
    can: () => false,
    user: { id: "user-1", displayName: "Io", globalRole: "member" },
  }),
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token" }),
}));
vi.mock("../api/leagues", () => ({
  fetchFantasyTeams: vi.fn().mockResolvedValue(TEAMS),
  fetchLeagueListone: vi.fn().mockResolvedValue([]),
  fetchLeagueMembersPublic: vi.fn().mockResolvedValue([]),
  fetchMyCredits: vi.fn().mockResolvedValue({ balance: 40 }),
  fetchRosterOccupancy: vi.fn().mockResolvedValue([]),
}));
vi.mock("../api/marketLive", () => ({
  cancelLiveAuctionLot: vi.fn(),
  createLiveAuctionSession: vi.fn(),
  declineLiveAuctionSwap: vi.fn(),
  endLiveAuctionSession: vi.fn(),
  fetchLiveAuctionLots: vi.fn().mockResolvedValue({ sessionId: "session-1", lots: [] }),
  fetchLiveAuctionSessions: vi.fn().mockResolvedValue([SESSION]),
  forceSellLiveAuctionLot: vi.fn(),
  nominateLiveAuctionLot: vi.fn(),
  passLiveAuctionLot: vi.fn(),
  placeLiveAuctionRaise: vi.fn(),
  resolveLiveAuctionSwap: vi.fn(),
  startLiveAuctionSession: vi.fn(),
}));
// Il polling restituisce subito lo stato con il lotto in corso.
vi.mock("../market/useLiveAuctionPolling", async () => {
  const React = await import("react");
  return {
    useLiveAuctionPolling: (
      _leagueId: string | null,
      sessionId: string | null,
      onUpdate: (next: LiveLotState) => void,
      enabled: boolean,
    ) => {
      React.useEffect(() => {
        if (enabled && sessionId) {
          onUpdate(STATE);
        }
      }, [enabled, sessionId]);
      return { degraded: false };
    },
  };
});

import { AuctionLivePage } from "./AuctionLivePage";

describe("asta live con Valore e media (1.3)", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = null;
    container = null;
  });

  it("mostra Valore e media del lotto, ma il rilancio non parte dal Valore", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(AuctionLivePage));
    });
    await act(async () => {
      await Promise.resolve();
    });

    const lot = container.querySelector('[data-testid="auction-live-current-lot"]');
    expect(lot).not.toBeNull();
    const tags = container.querySelector('[data-testid="auction-live-lot-value"]');
    expect(tags?.textContent).toContain("Valore 58");
    expect(tags?.querySelector(".fa-season-avg--current")?.textContent).toContain("6,85");
    expect(container.querySelector('[data-testid="auction-live-table-value"]')?.textContent).toContain(
      "Valore 58",
    );

    // Il campo del rilancio resta vuoto e il bottone propone il minimo, non il Valore.
    const custom = container.querySelector('input[name="custom-bid"]') as HTMLInputElement;
    expect(custom.value).toBe("");
    expect(custom.placeholder).not.toContain("58");
    const raise = container.querySelector('[data-testid="auction-live-raise-min"]');
    expect(raise?.textContent).toBe("Rilancia a 13");
    expect(container.querySelector('[data-testid="auction-live-current-lot"] .fa-market-hint')).toBeNull();
  });
});
