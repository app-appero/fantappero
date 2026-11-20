import type { LeagueDetail, LeagueMember, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchLeagueMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchLeague: (...args: unknown[]) => fetchLeagueMock(...args),
  fetchLeagueMembersPublic: vi.fn().mockResolvedValue([
    {
      userId: "user-1",
      displayName: "Marco Rossi",
      userType: "human",
      role: "league_admin",
      joinedAt: "2026-07-01T10:00:00Z",
    },
    {
      userId: "user-2",
      displayName: "Giulia Bianchi",
      userType: "human",
      role: "member",
      joinedAt: "2026-07-02T10:00:00Z",
    },
    {
      userId: "user-3",
      displayName: "Luca Verdi",
      userType: "human",
      role: "member",
      joinedAt: "2026-07-03T10:00:00Z",
    },
  ] satisfies LeagueMember[]),
  fetchLeagueCalendar: vi.fn().mockResolvedValue(null),
}));
// Valori stabili tra un render e l'altro: la home ricarica quando cambia la lega attiva.
const AUTH = {
  isDemoMode: false,
  activeLeagueId: "league-1",
  activeLeague: { id: "league-1", name: "Lega Test", role: "member" },
  can: () => false,
};
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => AUTH,
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { LeagueHomePage } from "./LeagueHomePage";

const USER: SessionUser = { id: "user-2", displayName: "Giulia Bianchi", globalRole: "member" };

function league(pendingInviteCount?: number): LeagueDetail {
  return {
    id: "league-1",
    name: "Lega Test",
    seasonYear: 2026,
    state: "configuring",
    viewerRole: "member",
    marketOpen: false,
    memberCount: 3,
    participantCount: 4,
    leagueFull: false,
    marketBlockedReason: "league_not_full",
    pendingInviteCount,
    competitions: [],
    rules: {
      presetName: "standard",
      participantCount: 4,
      participantMin: 4,
      participantMax: 10,
      roster: { rosterSize: 35, goalkeepers: 3, defenders: 11, midfielders: 11, forwards: 10 },
      totalCredits: 1000,
      minFixturesPerRound: 25,
      turnCoverageThreshold: 0.75,
      lineupLockMarginMinutes: 15,
      minutesThreshold: 15,
      voluntaryReleaseRefundPercent: 50,
      leagueExitRefundPercent: 100,
      maxActiveTradeProposalsPerTeam: 10,
      options: { allowTrades: true, allowManualInvites: true, requireTradeApproval: false },
    },
  };
}

describe("Home lega — inviti nominativi in attesa accanto ai partecipanti (Rosario, 20/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function render(detail: LeagueDetail) {
    fetchLeagueMock.mockResolvedValue(detail);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/home"],
          children: createElement(LeagueHomePage),
        }),
      );
    });
    for (let i = 0; i < 4; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }

  beforeEach(() => {
    clearStoredSession();
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("sotto il conto 3/4 mostra «1 invito in attesa»", async () => {
    await render(league(1));
    const stat = container.querySelector('[data-testid="league-home-pending-invites"]');
    expect(stat?.textContent).toBe("1 invito in attesa");
    expect(stat?.parentElement?.querySelector("strong")?.textContent).toBe("3/4");
  });

  it("al plurale «2 inviti in attesa»; senza inviti la riga non c'è", async () => {
    await render(league(2));
    expect(
      container.querySelector('[data-testid="league-home-pending-invites"]')?.textContent,
    ).toBe("2 inviti in attesa");
    for (const count of [0, undefined]) {
      // Una home nuova per ogni lega (la pagina ricarica quando cambia la lega attiva).
      act(() => root.unmount());
      root = createRoot(container);
      // eslint-disable-next-line no-await-in-loop
      await render(league(count));
      expect(container.querySelector(".fa-lhome__stat strong")?.textContent).toBe("3/4");
      expect(container.querySelector('[data-testid="league-home-pending-invites"]')).toBeNull();
    }
  });
});
