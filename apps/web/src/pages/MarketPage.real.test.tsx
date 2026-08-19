import type { FantasyTeam, LeagueSummary, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchMyFantasyTeamMock = vi.fn();
const fetchMyCreditsMock = vi.fn();
const fetchFantasyTeamsMock = vi.fn();
const fetchRosterOccupancyMock = vi.fn();
const fetchLeagueListoneMock = vi.fn();
const previewVoluntaryReleaseMock = vi.fn();
const applyVoluntaryReleaseMock = vi.fn();
const fetchTradeProposalsMock = vi.fn();
const createTradeProposalMock = vi.fn();
const acceptTradeProposalMock = vi.fn();
const rejectTradeProposalMock = vi.fn();
const cancelTradeProposalMock = vi.fn();

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
  fetchFantasyTeams: (...args: unknown[]) => fetchFantasyTeamsMock(...args),
  fetchRosterOccupancy: (...args: unknown[]) => fetchRosterOccupancyMock(...args),
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
  fetchWaiverSessions: vi.fn(),
  fetchWaiverSession: vi.fn(),
  submitWaiverBid: vi.fn(),
  withdrawWaiverBid: vi.fn(),
  fetchMyWaiverBids: vi.fn(),
  previewVoluntaryRelease: (...args: unknown[]) => previewVoluntaryReleaseMock(...args),
  applyVoluntaryRelease: (...args: unknown[]) => applyVoluntaryReleaseMock(...args),
  createTradeProposal: (...args: unknown[]) => createTradeProposalMock(...args),
  fetchTradeProposals: (...args: unknown[]) => fetchTradeProposalsMock(...args),
  fetchTradeProposal: vi.fn(),
  cancelTradeProposal: (...args: unknown[]) => cancelTradeProposalMock(...args),
  acceptTradeProposal: (...args: unknown[]) => acceptTradeProposalMock(...args),
  rejectTradeProposal: (...args: unknown[]) => rejectTradeProposalMock(...args),
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
const USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

const TEAM_WITH_PLAYER: FantasyTeam = {
  id: "team-1",
  leagueId: "league-1",
  membershipId: "membership-1",
  userId: "user-1",
  name: "Squadra Test",
  rosterSize: 25,
  filledSlots: 1,
  compositionStatus: "incomplete",
  slots: [
    {
      id: "slot-1",
      slotIndex: 0,
      athleteId: "athlete-1",
      athleteName: "Giocatore Svincolabile",
      clubName: "Lazio",
      role: "A",
      purchaseCredits: 30,
    },
  ],
};

const EMPTY_TEAM: FantasyTeam = { ...TEAM_WITH_PLAYER, slots: [], filledSlots: 0 };

async function flushAsync(rounds = 6): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

async function renderAppAt(path: string): Promise<{ html: string; unmount: () => void }> {
  fetchMeMock.mockResolvedValue(USER);
  fetchMyLeaguesMock.mockResolvedValue([LEAGUE]);
  saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });

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

describe("Mercato — svincolo volontario collegato alle API reali (EP08-04)", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchMyCreditsMock.mockReset().mockResolvedValue({
      fantasyTeamId: "team-1",
      balance: 150,
      version: 1,
      reconstructedBalance: 150,
    });
    previewVoluntaryReleaseMock.mockReset();
    applyVoluntaryReleaseMock.mockReset();
    fetchFantasyTeamsMock.mockReset().mockResolvedValue([]);
    fetchRosterOccupancyMock.mockReset().mockResolvedValue([]);
    fetchLeagueListoneMock.mockReset().mockResolvedValue([]);
    fetchTradeProposalsMock.mockReset().mockResolvedValue({ proposals: [] });
    createTradeProposalMock.mockReset();
    acceptTradeProposalMock.mockReset();
    rejectTradeProposalMock.mockReset();
    cancelTradeProposalMock.mockReset();
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("rosa senza giocatori mostra lo stato vuoto", async () => {
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(EMPTY_TEAM);
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-release-section"');
    expect(html).toContain("Nessun giocatore da svincolare");
    unmount();
  });

  it("rosa con un giocatore mostra il selettore di svincolo", async () => {
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(TEAM_WITH_PLAYER);
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="wireframe-market-success"');
    expect(html).toContain("Giocatore Svincolabile");
    expect(html).toContain("150 crediti");
    unmount();
  });

  it("errore nel caricamento della rosa mostra lo stato di errore", async () => {
    fetchMyFantasyTeamMock.mockReset().mockRejectedValue(
      new ApiError("Errore dal server.", 500, "internal_error"),
    );
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="wireframe-market-error"');
    expect(html).toContain("Errore dal server.");
    unmount();
  });
});

describe("Mercato — scambi collegati alle API reali (EP08-05/06)", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(TEAM_WITH_PLAYER);
    fetchMyCreditsMock.mockReset().mockResolvedValue({
      fantasyTeamId: "team-1",
      balance: 150,
      version: 1,
      reconstructedBalance: 150,
    });
    fetchFantasyTeamsMock.mockReset().mockResolvedValue([
      { id: "team-1", leagueId: "league-1", membershipId: "m-1", userId: "user-1", name: "La Mia Squadra", rosterSize: 25, filledSlots: 1, compositionStatus: "incomplete" },
      { id: "team-2", leagueId: "league-1", membershipId: "m-2", userId: "user-2", name: "Squadra Avversaria", rosterSize: 25, filledSlots: 1, compositionStatus: "incomplete" },
    ]);
    fetchRosterOccupancyMock.mockReset().mockResolvedValue([
      { athleteId: "athlete-2", fantasyTeamId: "team-2", teamName: "Squadra Avversaria", slotIndex: 0, purchaseCredits: 20 },
    ]);
    fetchLeagueListoneMock.mockReset().mockResolvedValue([
      {
        athleteId: "athlete-2",
        canonicalName: "Giocatore Avversario",
        seasonYear: 2026,
        officialRole: "D",
        effectiveRole: "D",
        providerPositionRaw: "Defender",
        mappingVersion: "v1.0.0",
        clubId: "club-2",
        clubName: "Napoli",
        override: null,
      },
    ]);
    previewVoluntaryReleaseMock.mockReset();
    applyVoluntaryReleaseMock.mockReset();
    fetchTradeProposalsMock.mockReset().mockResolvedValue({ proposals: [] });
    createTradeProposalMock.mockReset();
    acceptTradeProposalMock.mockReset();
    rejectTradeProposalMock.mockReset();
    cancelTradeProposalMock.mockReset();
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("nessuna proposta mostra lo stato vuoto e il form di creazione", async () => {
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-trade-empty"');
    expect(html).toContain('data-testid="market-trade-create-form"');
    expect(html).toContain("Squadra Avversaria");
    unmount();
  });

  it("errore nel caricamento delle proposte mostra lo stato di errore", async () => {
    fetchTradeProposalsMock.mockReset().mockRejectedValue(
      new ApiError("Errore dal server.", 500, "internal_error"),
    );
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-trade-load-error"');
    expect(html).toContain("Errore dal server.");
    unmount();
  });

  it("proposta ricevuta mostra Accetta/Rifiuta/Controproponi, proposta inviata mostra Annulla", async () => {
    fetchTradeProposalsMock.mockReset().mockResolvedValue({
      proposals: [
        {
          id: "proposal-received",
          leagueId: "league-1",
          proposerTeamId: "team-2",
          recipientTeamId: "team-1",
          offeredAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
          requestedAthletes: [],
          offeredCredits: 10,
          requestedCredits: 0,
          status: "proposed",
          expiresAt: "2026-09-01T00:00:00Z",
          createdAt: "2026-08-19T00:00:00Z",
          counterOfId: null,
        },
        {
          id: "proposal-sent",
          leagueId: "league-1",
          proposerTeamId: "team-1",
          recipientTeamId: "team-2",
          offeredAthletes: [],
          requestedAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
          offeredCredits: 5,
          requestedCredits: 0,
          status: "proposed",
          expiresAt: "2026-09-01T00:00:00Z",
          createdAt: "2026-08-19T00:00:00Z",
          counterOfId: null,
        },
      ],
    });
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-trade-proposal-proposal-received"');
    expect(html).toContain('data-testid="market-trade-proposal-proposal-sent"');
    expect(html).toContain("Accetta");
    expect(html).toContain("Rifiuta");
    expect(html).toContain("Controproponi");
    expect(html).toContain("Annulla");
    unmount();
  });
});
