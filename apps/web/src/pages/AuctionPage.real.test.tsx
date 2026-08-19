import type { LeagueListoneEntry, LeagueSummary, MarketSession, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchLeagueListoneMock = vi.fn();
const fetchMyCreditsMock = vi.fn();
const fetchAuctionSessionsMock = vi.fn();
const submitAuctionBidMock = vi.fn();
const withdrawAuctionBidMock = vi.fn();
const fetchMyAuctionBidsMock = vi.fn();

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
}));

vi.mock("../api/market", () => ({
  createAuctionSession: vi.fn(),
  closeAuctionSession: vi.fn(),
  resolveAuctionSession: vi.fn(),
  fetchAuctionSessions: (...args: unknown[]) => fetchAuctionSessionsMock(...args),
  fetchAuctionSession: vi.fn(),
  submitAuctionBid: (...args: unknown[]) => submitAuctionBidMock(...args),
  withdrawAuctionBid: (...args: unknown[]) => withdrawAuctionBidMock(...args),
  fetchMyAuctionBids: (...args: unknown[]) => fetchMyAuctionBidsMock(...args),
  createWaiverSession: vi.fn(),
  closeWaiverSession: vi.fn(),
  resolveWaiverSession: vi.fn(),
  fetchWaiverSessions: vi.fn(),
  fetchWaiverSession: vi.fn(),
  submitWaiverBid: vi.fn(),
  withdrawWaiverBid: vi.fn(),
  fetchMyWaiverBids: vi.fn(),
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
    canonicalName: "M. Thuram",
    seasonYear: 2026,
    officialRole: "A",
    effectiveRole: "A",
    providerPositionRaw: "Attacker",
    mappingVersion: "v1.0.0",
    clubId: "club-1",
    clubName: "Inter",
    override: null,
  },
];

const OPEN_SESSION: MarketSession = {
  id: "session-1",
  leagueId: "league-1",
  kind: "initial_auction",
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

describe("Asta a buste chiuse — flusso reale collegato alle API (EP08-01/02)", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchLeagueListoneMock.mockReset().mockResolvedValue(LISTONE);
    fetchMyCreditsMock.mockReset().mockResolvedValue({
      fantasyTeamId: "team-1",
      balance: 420,
      version: 1,
      reconstructedBalance: 420,
    });
    fetchAuctionSessionsMock.mockReset();
    submitAuctionBidMock.mockReset();
    withdrawAuctionBidMock.mockReset();
    fetchMyAuctionBidsMock.mockReset().mockResolvedValue({
      sessionId: "session-1",
      fantasyTeamId: "team-1",
      bids: [],
    });
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("membro senza market:manage non vede il pannello admin ma vede l'offerta", async () => {
    fetchAuctionSessionsMock.mockResolvedValue([]);
    const { html, unmount } = await renderAppAt("/asta", MEMBER_USER, [LEAGUE]);
    expect(html).not.toContain('data-testid="wireframe-region-auction-admin"');
    expect(html).toContain('data-testid="wireframe-region-auction-bid"');
    unmount();
  });

  it("admin: nessuna sessione mostra lo stato vuoto e il form di creazione", async () => {
    fetchAuctionSessionsMock.mockResolvedValue([]);
    const { html, unmount } = await renderAppAt("/asta", ADMIN_USER, [LEAGUE_ADMIN]);
    expect(html).toContain('data-testid="wireframe-region-auction-admin"');
    expect(html).toContain('data-testid="auction-admin-empty"');
    expect(html).toContain('data-testid="auction-create-session-form"');
    unmount();
  });

  it("admin: sessione aperta mostra il badge e abilita Chiudi asta", async () => {
    fetchAuctionSessionsMock.mockResolvedValue([OPEN_SESSION]);
    const { html, unmount } = await renderAppAt("/asta", ADMIN_USER, [LEAGUE_ADMIN]);
    expect(html).toContain('data-testid="auction-admin-current-session"');
    expect(html).toContain("Aperta");
    expect(html).not.toContain('data-testid="auction-bid-not-open"');
    unmount();
  });

  it("errore nel caricamento delle sessioni mostra lo stato di errore", async () => {
    fetchAuctionSessionsMock.mockRejectedValue(
      new ApiError("Errore dal server.", 500, "internal_error"),
    );
    const { html, unmount } = await renderAppAt("/asta", ADMIN_USER, [LEAGUE_ADMIN]);
    expect(html).toContain('data-testid="auction-admin-error"');
    expect(html).toContain("Errore dal server.");
    unmount();
  });

  it("membro: sessione non aperta impedisce l'invio di offerte", async () => {
    fetchAuctionSessionsMock.mockResolvedValue([]);
    const { html, unmount } = await renderAppAt("/asta", MEMBER_USER, [LEAGUE]);
    expect(html).toContain('data-testid="auction-bid-not-open"');
    unmount();
  });
});
