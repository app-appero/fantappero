import type { LeagueListoneEntry, LeagueSummary, MarketSession, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchLeagueListoneMock = vi.fn();
const fetchMyCreditsMock = vi.fn();
const fetchMyFantasyTeamMock = vi.fn();
const fetchWaiverSessionsMock = vi.fn();
const fetchMyWaiverBidsMock = vi.fn();

vi.mock("../api/auth", () => ({
  fetchMe: (...args: unknown[]) => fetchMeMock(...args),
  refresh: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../api/leagues", () => ({
  fetchCompetitions: vi.fn(),
  fetchMyLeagues: (...args: unknown[]) => fetchMyLeaguesMock(...args),
  createLeague: vi.fn(),
  fetchLeagueListone: (...args: unknown[]) => fetchLeagueListoneMock(...args),
  refreshLeagueListone: vi.fn(),
  fetchMyCredits: (...args: unknown[]) => fetchMyCreditsMock(...args),
  fetchMyFantasyTeam: (...args: unknown[]) => fetchMyFantasyTeamMock(...args),
}));

vi.mock("../api/market", () => ({
  createAuctionSession: vi.fn(),
  closeAuctionSession: vi.fn(),
  resolveAuctionSession: vi.fn(),
  fetchAuctionSessions: vi.fn(),
  fetchAuctionSession: vi.fn(),
  submitAuctionBid: vi.fn(),
  withdrawAuctionBid: vi.fn(),
  fetchMyAuctionBids: vi.fn(),
  createWaiverSession: vi.fn(),
  closeWaiverSession: vi.fn(),
  resolveWaiverSession: vi.fn(),
  fetchWaiverSessions: (...args: unknown[]) => fetchWaiverSessionsMock(...args),
  fetchWaiverSession: vi.fn(),
  submitWaiverBid: vi.fn(),
  withdrawWaiverBid: vi.fn(),
  fetchMyWaiverBids: (...args: unknown[]) => fetchMyWaiverBidsMock(...args),
  previewVoluntaryRelease: vi.fn(),
  applyVoluntaryRelease: vi.fn(),
  createTradeProposal: vi.fn(),
  fetchTradeProposals: vi.fn(),
  fetchTradeProposal: vi.fn(),
  cancelTradeProposal: vi.fn(),
  acceptTradeProposal: vi.fn(),
  rejectTradeProposal: vi.fn(),
  counterTradeProposal: vi.fn(),
  approveTradeProposal: vi.fn(),
  rejectTradeProposalAsAdmin: vi.fn(),
  fetchMarketHistory: vi.fn(),
}));

vi.mock("../api/notifications", () => ({
  fetchNotifications: vi.fn().mockResolvedValue({
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
    unreadCount: 0,
  }),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  fetchNotificationPreferences: vi.fn(),
  updateNotificationPreference: vi.fn(),
}));

import { AuthProvider } from "../auth/AuthContext";
import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { AppRoutes } from "../routes";

const LEAGUE: LeagueSummary = { id: "league-1", name: "Lega Test", role: "member" };
const LEAGUE_ADMIN: LeagueSummary = { id: "league-1", name: "Lega Test", role: "league_admin" };

const MEMBER_USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };
const ADMIN_USER: SessionUser = { id: "admin-1", displayName: "Admin Test", globalRole: "member" };

const LISTONE: LeagueListoneEntry[] = [
  {
    athleteId: "athlete-1",
    canonicalName: "Svincolato Uno",
    seasonYear: 2026,
    officialRole: "C",
    effectiveRole: "C",
    providerPositionRaw: "Midfielder",
    mappingVersion: "v1.0.0",
    clubId: "club-1",
    clubName: "Torino",
    override: null,
  },
];

const OPEN_SESSION: MarketSession = {
  id: "waiver-session-1",
  leagueId: "league-1",
  kind: "waiver",
  status: "open",
  opensAt: "2026-08-19T10:00:00Z",
  closesAt: "2026-08-20T10:00:00Z",
  bidCount: null,
  parentSessionId: null,
  targetAthleteId: null,
};

async function flushAsync(rounds = 6): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

async function renderAppAt(
  path: string,
  user: SessionUser,
  leagues: LeagueSummary[],
): Promise<{ html: string; unmount: () => void }> {
  fetchMeMock.mockResolvedValue(user);
  fetchMyLeaguesMock.mockResolvedValue(leagues);
  saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user });

  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  await act(async () => {
    root.render(
      createElement(MemoryRouter, {
        initialEntries: [path],
        children: createElement(AuthProvider, { children: createElement(AppRoutes) }),
      }),
    );
  });
  await flushAsync();

  return {
    html: container.innerHTML,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    },
  };
}

describe("Svincolati — flusso reale collegato alle API (EP08-03)", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchLeagueListoneMock.mockReset().mockResolvedValue(LISTONE);
    fetchMyCreditsMock.mockReset().mockResolvedValue({
      fantasyTeamId: "team-1",
      balance: 380,
      version: 1,
      reconstructedBalance: 380,
    });
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue({
      id: "team-1",
      leagueId: "league-1",
      membershipId: "membership-1",
      userId: "user-1",
      userType: "human",
      name: "Squadra Test",
      rosterSize: 25,
      filledSlots: 1,
      compositionStatus: "incomplete",
      slots: [
        {
          id: "slot-1",
          slotIndex: 0,
          athleteId: "owned-athlete-1",
          athleteName: "Giocatore Posseduto",
          clubName: "Roma",
          role: "D",
          purchaseCredits: 10,
        },
      ],
    });
    fetchWaiverSessionsMock.mockReset();
    fetchMyWaiverBidsMock.mockReset().mockResolvedValue({
      sessionId: "waiver-session-1",
      fantasyTeamId: "team-1",
      bids: [],
    });
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("membro senza market:manage non vede il pannello admin ma vede l'offerta", async () => {
    fetchWaiverSessionsMock.mockResolvedValue([]);
    const { html, unmount } = await renderAppAt("/svincoli", MEMBER_USER, [LEAGUE]);
    expect(html).not.toContain('data-testid="wireframe-region-waiver-admin"');
    expect(html).toContain('data-testid="wireframe-region-waiver-bid"');
    unmount();
  });

  it("admin: nessuna sessione mostra lo stato vuoto e il form di creazione", async () => {
    fetchWaiverSessionsMock.mockResolvedValue([]);
    const { html, unmount } = await renderAppAt("/svincoli", ADMIN_USER, [LEAGUE_ADMIN]);
    expect(html).toContain('data-testid="wireframe-region-waiver-admin"');
    expect(html).toContain('data-testid="waiver-admin-empty"');
    expect(html).toContain('data-testid="waiver-create-session-form"');
    unmount();
  });

  it("admin: sessione aperta mostra il badge e abilita Chiudi svincolati", async () => {
    fetchWaiverSessionsMock.mockResolvedValue([OPEN_SESSION]);
    const { html, unmount } = await renderAppAt("/svincoli", ADMIN_USER, [LEAGUE_ADMIN]);
    expect(html).toContain('data-testid="waiver-admin-current-session"');
    expect(html).toContain("Aperta");
    unmount();
  });

  it("errore nel caricamento delle sessioni mostra lo stato di errore", async () => {
    fetchWaiverSessionsMock.mockRejectedValue(
      new ApiError("Errore dal server.", 500, "internal_error"),
    );
    const { html, unmount } = await renderAppAt("/svincoli", ADMIN_USER, [LEAGUE_ADMIN]);
    expect(html).toContain('data-testid="waiver-admin-error"');
    expect(html).toContain("Errore dal server.");
    unmount();
  });

  it("membro: il form offerta espone il selettore del giocatore da svincolare dalla rosa", async () => {
    fetchWaiverSessionsMock.mockResolvedValue([OPEN_SESSION]);
    const { html, unmount } = await renderAppAt("/svincoli", MEMBER_USER, [LEAGUE]);
    expect(html).toContain("Giocatore Posseduto");
    unmount();
  });
});
