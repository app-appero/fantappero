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
const fetchTeamPlayersForTradeMock = vi.fn();
const fetchLeagueListoneMock = vi.fn();
const previewVoluntaryReleaseMock = vi.fn();
const applyVoluntaryReleaseMock = vi.fn();
const fetchMarketHistoryMock = vi.fn();
const fetchMarketGateMock = vi.fn();
const setMarketGateMock = vi.fn();
const fetchTradeProposalsMock = vi.fn();
const createTradeProposalMock = vi.fn();
const acceptTradeProposalMock = vi.fn();
const rejectTradeProposalMock = vi.fn();
const cancelTradeProposalMock = vi.fn();
const approveTradeProposalMock = vi.fn();
const rejectTradeProposalAsAdminMock = vi.fn();
const previewTradeProposalMock = vi.fn();
const fetchTradeReplacementsMock = vi.fn();

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
  fetchTeamPlayersForTrade: (...args: unknown[]) => fetchTeamPlayersForTradeMock(...args),
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
  approveTradeProposal: (...args: unknown[]) => approveTradeProposalMock(...args),
  rejectTradeProposalAsAdmin: (...args: unknown[]) => rejectTradeProposalAsAdminMock(...args),
  fetchMarketHistory: (...args: unknown[]) => fetchMarketHistoryMock(...args),
  fetchMarketGate: (...args: unknown[]) => fetchMarketGateMock(...args),
  setMarketGate: (...args: unknown[]) => setMarketGateMock(...args),
  previewTradeProposal: (...args: unknown[]) => previewTradeProposalMock(...args),
  fetchTradeReplacements: (...args: unknown[]) => fetchTradeReplacementsMock(...args),
  fetchTradeReplacementCandidates: vi.fn().mockResolvedValue({ role: "D", balance: 150, total: 0, candidates: [] }),
  buyTradeReplacement: vi.fn(),
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
const USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

const TEAM_WITH_PLAYER: FantasyTeam = {
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
      exceedsRoleQuota: false,
      athleteId: "athlete-1",
      athleteName: "Giocatore Svincolabile",
      photoUrl: null,
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

async function renderAppAt(
  path: string,
  leagues: LeagueSummary[] = [LEAGUE],
): Promise<{ html: string; container: HTMLDivElement; unmount: () => void }> {
  fetchMeMock.mockResolvedValue(USER);
  fetchMyLeaguesMock.mockResolvedValue(leagues);
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
    container,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    },
  };
}

// Sezione nascosta da MarketPage (SHOW_VOLUNTARY_RELEASE = false, ADR-0006): la tab
// "Scambi" propone solo scambi. Test tenuti per un eventuale ripristino della UI.
describe.skip("Mercato — svincolo volontario collegato alle API reali (EP08-04)", () => {
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
    fetchMarketHistoryMock
      .mockReset()
      .mockResolvedValue({ items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 });
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
    fetchTeamPlayersForTradeMock.mockReset().mockResolvedValue([
      {
        athleteId: "athlete-2",
        athleteName: "Giocatore Avversario",
        slotIndex: 0,
        purchaseCredits: 20,
      },
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
    fetchMarketHistoryMock
      .mockReset()
      .mockResolvedValue({ items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 });
    fetchMarketGateMock.mockReset().mockResolvedValue({ marketOpen: true });
    setMarketGateMock.mockReset().mockResolvedValue({ marketOpen: true });
    createTradeProposalMock.mockReset();
    acceptTradeProposalMock.mockReset();
    rejectTradeProposalMock.mockReset();
    cancelTradeProposalMock.mockReset();
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("rosa vuota apre gli scambi, mostra l'avviso e disabilita i controlli", async () => {
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue({
      ...TEAM_WITH_PLAYER,
      slots: [],
      filledSlots: 0,
    });
    const { container, unmount } = await renderAppAt("/mercato");
    expect(container.querySelector('[data-testid="market-trade-form-section"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="market-trade-create-form"]')).not.toBeNull();
    expect(container.innerHTML).toContain('data-testid="market-trade-empty-roster"');
    expect(container.innerHTML).toContain("Nessun calciatore in rosa");
    const select = container.querySelector('select[name="trade-recipient"]') as HTMLSelectElement | null;
    const credits = container.querySelector('input[name="trade-credits"]') as HTMLInputElement | null;
    const creditsDirection = container.querySelector(
      'fieldset:has(input[name="trade-credits-direction"])',
    ) as HTMLFieldSetElement | null;
    const expiry = container.querySelector('input[name="trade-has-expires-at"]') as HTMLInputElement | null;
    const submit = container.querySelector(
      '[data-testid="market-trade-create-form"] button[type="submit"]',
    ) as HTMLButtonElement | null;
    expect(select?.disabled).toBe(true);
    expect(credits?.disabled).toBe(true);
    expect(creditsDirection?.disabled).toBe(true);
    expect(expiry?.disabled).toBe(true);
    expect(submit?.disabled).toBe(true);
    unmount();
  });

  it("nessuna proposta mostra lo stato vuoto e il form di creazione", async () => {
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-trade-empty"');
    expect(html).toContain('data-testid="market-trade-create-form"');
    expect(html).toContain("Squadra Avversaria");
    expect(html).toContain('data-testid="market-gate-bar"');
    expect(html).not.toContain('data-testid="market-gate-switch"');
    unmount();
  });

  it("l'admin vede l'interruttore del mercato nella tab scambi", async () => {
    const { html, unmount } = await renderAppAt("/mercato", [
      { id: "league-1", name: "Lega Test", role: "league_admin" },
    ]);
    expect(html).toContain('data-testid="market-gate-switch"');
    expect(html).toContain('data-testid="market-trade-create-form"');
    unmount();
  });

  it("a lega non al completo il banner spiega perché e gli scambi sono fermi (20/11)", async () => {
    fetchMarketGateMock.mockReset().mockResolvedValue({
      marketOpen: false,
      memberCount: 5,
      participantCount: 8,
      leagueFull: false,
      marketBlockedReason: "league_not_full",
    });
    const { container, unmount } = await renderAppAt("/mercato", [
      { id: "league-1", name: "Lega Test", role: "league_admin" },
    ]);
    const banner = container.querySelector('[data-testid="market-gate-not-full"]');
    expect(banner?.textContent).toBe("Il mercato si apre quando la lega è al completo (5/8).");
    const gateSwitch = container.querySelector(
      '[data-testid="market-gate-switch"]',
    ) as HTMLButtonElement | null;
    expect(gateSwitch?.disabled).toBe(true);
    const submit = container.querySelector(
      '[data-testid="market-trade-create-form"] button[type="submit"]',
    ) as HTMLButtonElement | null;
    expect(submit?.textContent).toContain("Proponi scambio");
    expect(submit?.disabled).toBe(true);
    unmount();
  });

  it("accanto al conto il banner mostra gli inviti nominativi in attesa (Rosario, 20/11)", async () => {
    fetchMarketGateMock.mockReset().mockResolvedValue({
      marketOpen: false,
      memberCount: 3,
      participantCount: 4,
      leagueFull: false,
      marketBlockedReason: "league_not_full",
      pendingInviteCount: 1,
    });
    const { container, unmount } = await renderAppAt("/mercato", [
      { id: "league-1", name: "Lega Test", role: "league_admin" },
    ]);
    const banner = container.querySelector('[data-testid="market-gate-not-full"]');
    expect(banner?.textContent).toBe(
      "Il mercato si apre quando la lega è al completo (3/4 · 1 invito in attesa).",
    );
    // Gli inviti non rendono la lega al completo: l'interruttore resta fermo.
    const gateSwitch = container.querySelector(
      '[data-testid="market-gate-switch"]',
    ) as HTMLButtonElement | null;
    expect(gateSwitch?.disabled).toBe(true);
    unmount();

    fetchMarketGateMock.mockReset().mockResolvedValue({
      marketOpen: false,
      memberCount: 2,
      participantCount: 4,
      leagueFull: false,
      marketBlockedReason: "league_not_full",
      pendingInviteCount: 2,
    });
    const plural = await renderAppAt("/mercato", [
      { id: "league-1", name: "Lega Test", role: "league_admin" },
    ]);
    expect(
      plural.container.querySelector('[data-testid="market-gate-not-full"]')?.textContent,
    ).toBe("Il mercato si apre quando la lega è al completo (2/4 · 2 inviti in attesa).");
    plural.unmount();
  });

  it("con mercato chiuso il form scambi resta disponibile", async () => {
    fetchMarketGateMock.mockReset().mockResolvedValue({ marketOpen: false });
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain("Rosa e asta sono bloccate");
    expect(html).toContain('data-testid="market-trade-create-form"');
    expect(html).toContain("Proponi scambio");
    unmount();
  });

  it("selezionando la squadra destinataria carica i giocatori richiesti", async () => {
    const { container, unmount } = await renderAppAt("/mercato");
    const select = container.querySelector('select[name="trade-recipient"]') as HTMLSelectElement | null;
    expect(select).not.toBeNull();
    await act(async () => {
      select!.value = "team-2";
      select!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushAsync();
    expect(fetchTeamPlayersForTradeMock).toHaveBeenCalledWith("access-token", "league-1", "team-2");
    expect(container.innerHTML).toContain("Giocatore Avversario");
    expect(container.innerHTML).not.toContain("Scegli prima una squadra destinataria.");
    unmount();
  });

  it("senza spuntare 'Imposta una scadenza' la proposta viene inviata senza scadenza", async () => {
    createTradeProposalMock.mockReset().mockResolvedValue({});
    const { container, unmount } = await renderAppAt("/mercato");
    const select = container.querySelector('select[name="trade-recipient"]') as HTMLSelectElement | null;
    const form = container.querySelector(
      '[data-testid="market-trade-create-form"]',
    ) as HTMLFormElement | null;
    expect(select).not.toBeNull();
    expect(form).not.toBeNull();
    await act(async () => {
      select!.value = "team-2";
      select!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushAsync();
    expect(container.querySelector('input[name="trade-expires-at"]')).toBeNull();
    await act(async () => {
      form!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushAsync();
    expect(createTradeProposalMock).toHaveBeenCalledWith(
      "access-token",
      "league-1",
      expect.objectContaining({ expiresAt: null }),
    );
    unmount();
  });

  it("con 'Imposta una scadenza' spuntato ma senza data la proposta non viene inviata", async () => {
    createTradeProposalMock.mockReset().mockResolvedValue({});
    const { container, unmount } = await renderAppAt("/mercato");
    const select = container.querySelector('select[name="trade-recipient"]') as HTMLSelectElement | null;
    const checkbox = container.querySelector(
      'input[name="trade-has-expires-at"]',
    ) as HTMLInputElement | null;
    const form = container.querySelector(
      '[data-testid="market-trade-create-form"]',
    ) as HTMLFormElement | null;
    expect(checkbox).not.toBeNull();
    await act(async () => {
      select!.value = "team-2";
      select!.dispatchEvent(new Event("change", { bubbles: true }));
      checkbox!.click();
    });
    await flushAsync();
    expect(container.querySelector('input[name="trade-expires-at"]')).not.toBeNull();
    await act(async () => {
      form!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushAsync();
    expect(createTradeProposalMock).not.toHaveBeenCalled();
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

  it("Accetta chiede conferma: Indietro chiude senza accettare, Accetta scambio chiama l'API", async () => {
    const received = {
      id: "proposal-received",
      leagueId: "league-1",
      proposerTeamId: "team-2",
      recipientTeamId: "team-1",
      offeredAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
      requestedAthletes: [{ id: "athlete-1", name: "Giocatore Svincolabile" }],
      offeredCredits: 10,
      requestedCredits: 0,
      status: "proposed",
      expiresAt: null,
      createdAt: "2026-08-19T00:00:00Z",
      counterOfId: null,
    };
    fetchTradeProposalsMock.mockReset().mockResolvedValue({ proposals: [received] });
    acceptTradeProposalMock.mockReset().mockResolvedValue({ ...received, status: "accepted" });
    const { container, unmount } = await renderAppAt("/mercato");
    const query = (testId: string) =>
      container.querySelector(`[data-testid="${testId}"]`) as HTMLButtonElement | null;

    const accept = query("market-trade-accept-proposal-received");
    expect(accept?.textContent).toContain("Accetta");
    expect(query("market-trade-accept-dialog")).toBeNull();

    // Il primo tocco apre solo la conferma, con il riepilogo dello scambio.
    await act(async () => {
      accept!.click();
    });
    expect(acceptTradeProposalMock).not.toHaveBeenCalled();
    expect(container.querySelector('[role="dialog"]')?.textContent).toContain("Accettare lo scambio?");
    expect(query("market-trade-accept-dialog")?.textContent).toBe(
      "Riceverai Giocatore Avversario + 10 crediti e cederai Giocatore Svincolabile. " +
        "Una volta accettato non potrai annullarlo.",
    );
    expect(query("market-trade-accept-cancel")?.textContent).toBe("Indietro");
    expect(query("market-trade-accept-confirm")?.textContent).toBe("Accetta scambio");

    // Indietro chiude la conferma senza accettare.
    await act(async () => {
      query("market-trade-accept-cancel")!.click();
    });
    expect(query("market-trade-accept-dialog")).toBeNull();
    expect(acceptTradeProposalMock).not.toHaveBeenCalled();

    // Solo «Accetta scambio» accetta davvero.
    await act(async () => {
      query("market-trade-accept-proposal-received")!.click();
    });
    await act(async () => {
      query("market-trade-accept-confirm")!.click();
    });
    await flushAsync();
    expect(acceptTradeProposalMock).toHaveBeenCalledTimes(1);
    expect(acceptTradeProposalMock).toHaveBeenCalledWith("access-token", "league-1", "proposal-received");
    expect(query("market-trade-accept-dialog")).toBeNull();
    unmount();
  });

  it("1.5: chi accetta uno scambio che lo lascia corto vede l'avviso e poi sceglie il sostituto", async () => {
    const received = {
      id: "proposal-short",
      leagueId: "league-1",
      proposerTeamId: "team-2",
      recipientTeamId: "team-1",
      offeredAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
      requestedAthletes: [
        { id: "athlete-1", name: "Giocatore Svincolabile" },
        { id: "athlete-3", name: "Secondo Ceduto" },
      ],
      offeredCredits: 0,
      requestedCredits: 0,
      status: "proposed",
      expiresAt: null,
      createdAt: "2026-08-19T00:00:00Z",
      counterOfId: null,
      proposerRosterAfter: { teamId: "team-2", teamName: "Squadra Avversaria", sizeAfter: 36, rosterSize: 35, missingRoles: [] },
      recipientRosterAfter: {
        teamId: "team-1",
        teamName: "La Mia Squadra",
        sizeAfter: 34,
        rosterSize: 35,
        missingRoles: [{ role: "D", count: 1 }],
      },
    };
    fetchTradeProposalsMock.mockReset().mockResolvedValue({ proposals: [received] });
    acceptTradeProposalMock.mockReset().mockResolvedValue({ ...received, status: "accepted" });
    fetchTradeReplacementsMock.mockReset().mockRejectedValue(new Error("nessuno"));
    const { container, unmount } = await renderAppAt("/mercato");
    const query = (testId: string) =>
      container.querySelector(`[data-testid="${testId}"]`) as HTMLButtonElement | null;
    await act(async () => {
      query("market-trade-accept-proposal-short")!.click();
    });
    expect(query("trade-shortfall-warning")?.textContent).toContain("Dopo lo scambio avrai 34/35");
    expect(query("trade-shortfall-warning")?.textContent).toContain(
      "Ti mancherà un Difensore. Appena accetti dovrai sceglierlo dagli svincolati, al suo Valore. " +
        "Finché non lo scegli non potrai schierare la formazione.",
    );
    expect(query("market-trade-accept-cancel")?.textContent).toBe("Annulla");
    expect(query("market-trade-accept-confirm")?.textContent).toBe("Accetta e scegli");

    fetchTradeReplacementsMock.mockReset().mockResolvedValue({
      teamId: "team-1",
      rosterSize: 35,
      filledSlots: 34,
      balance: 150,
      pending: [{ id: "r1", role: "D", tradeProposalId: "proposal-short", createdAt: "2026-11-25T10:00:00Z" }],
      missingRoles: [{ role: "D", count: 1 }],
      tradeProposalId: "proposal-short",
      otherTeamName: "Squadra Avversaria",
      receivedAthleteNames: ["Giocatore Avversario"],
      receivedCredits: 0,
      blockedReason: null,
      blockedMessage: null,
    });
    await act(async () => {
      query("market-trade-accept-confirm")!.click();
    });
    await flushAsync();
    expect(acceptTradeProposalMock).toHaveBeenCalledWith("access-token", "league-1", "proposal-short");
    // Scambio fatto: si apre subito «Scegli il sostituto».
    expect(query("replacement-sheet")).not.toBeNull();
    expect(query("replacement-done")?.textContent).toContain("Scambio fatto: è arrivato Giocatore Avversario");
    unmount();
  });

  it("1.5: chi propone uno scambio che lo lascerebbe corto lo vede prima di inviarlo", async () => {
    createTradeProposalMock.mockReset().mockResolvedValue({});
    previewTradeProposalMock.mockReset().mockResolvedValue({
      proposerRosterAfter: {
        teamId: "team-1",
        teamName: "La Mia Squadra",
        sizeAfter: 33,
        rosterSize: 35,
        missingRoles: [{ role: "D", count: 2 }],
      },
      recipientRosterAfter: { teamId: "team-2", teamName: "Squadra Avversaria", sizeAfter: 37, rosterSize: 35, missingRoles: [] },
    });
    const { container, unmount } = await renderAppAt("/mercato");
    const query = (testId: string) =>
      container.querySelector(`[data-testid="${testId}"]`) as HTMLButtonElement | null;
    const select = container.querySelector('select[name="trade-recipient"]') as HTMLSelectElement;
    await act(async () => {
      select.value = "team-2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushAsync();
    const offered = container.querySelector(
      '[data-testid="market-trade-offered-athletes"] input[type="checkbox"]',
    ) as HTMLInputElement;
    await act(async () => {
      offered.click();
    });
    const form = container.querySelector('[data-testid="market-trade-create-form"]') as HTMLFormElement;
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushAsync();
    expect(previewTradeProposalMock).toHaveBeenCalledWith("access-token", "league-1", {
      recipientTeamId: "team-2",
      offeredAthleteIds: ["athlete-1"],
      requestedAthleteIds: [],
    });
    expect(createTradeProposalMock).not.toHaveBeenCalled();
    expect(query("market-trade-propose-warning")?.textContent).toContain("Dopo lo scambio avrai 33/35");
    expect(query("market-trade-propose-warning")?.textContent).toContain(
      "Ti mancheranno 2 Difensori. Se lo scambio viene accettato dovrai sceglierli dagli svincolati, al loro Valore.",
    );
    await act(async () => {
      query("market-trade-propose-confirm")!.click();
    });
    await flushAsync();
    expect(createTradeProposalMock).toHaveBeenCalledTimes(1);
    unmount();
  });

  it("1.5: l'admin che approva vede quale squadra resterà corta", async () => {
    const pending = {
      id: "proposal-pending-short",
      leagueId: "league-1",
      proposerTeamId: "team-2",
      recipientTeamId: "team-3",
      offeredAthletes: [{ id: "athlete-5", name: "Primo" }, { id: "athlete-6", name: "Secondo" }],
      requestedAthletes: [{ id: "athlete-7", name: "Terzo" }],
      offeredCredits: 0,
      requestedCredits: 0,
      status: "pending_approval",
      expiresAt: null,
      createdAt: "2026-08-19T00:00:00Z",
      counterOfId: null,
      proposerRosterAfter: {
        teamId: "team-2",
        teamName: "Squadra Avversaria",
        sizeAfter: 34,
        rosterSize: 35,
        missingRoles: [{ role: "D", count: 1 }],
      },
      recipientRosterAfter: { teamId: "team-3", teamName: "Terza", sizeAfter: 36, rosterSize: 35, missingRoles: [] },
    };
    fetchTradeProposalsMock.mockReset().mockResolvedValue({ proposals: [pending] });
    approveTradeProposalMock.mockReset().mockResolvedValue({ ...pending, status: "executed" });
    fetchTradeReplacementsMock.mockReset().mockRejectedValue(new Error("nessuno"));
    const adminLeague: LeagueSummary = { id: "league-1", name: "Lega Test", role: "league_admin" };
    const { container, unmount } = await renderAppAt("/mercato", [adminLeague]);
    const query = (testId: string) =>
      container.querySelector(`[data-testid="${testId}"]`) as HTMLButtonElement | null;
    await act(async () => {
      query("market-trade-approve-proposal-pending-short")!.click();
    });
    expect(approveTradeProposalMock).not.toHaveBeenCalled();
    expect(query("market-trade-approve-warning")?.textContent).toContain(
      "Dopo lo scambio Squadra Avversaria avrà 34/35",
    );
    expect(query("market-trade-approve-warning")?.textContent).toContain("Le mancherà un Difensore. Appena approvi");
    await act(async () => {
      query("market-trade-approve-confirm")!.click();
    });
    await flushAsync();
    expect(approveTradeProposalMock).toHaveBeenCalledWith("access-token", "league-1", "proposal-pending-short");
    unmount();
  });

  it("Rifiuta resta senza conferma", async () => {
    fetchTradeProposalsMock.mockReset().mockResolvedValue({
      proposals: [
        {
          id: "proposal-received",
          leagueId: "league-1",
          proposerTeamId: "team-2",
          recipientTeamId: "team-1",
          offeredAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
          requestedAthletes: [],
          offeredCredits: 0,
          requestedCredits: 0,
          status: "proposed",
          expiresAt: null,
          createdAt: "2026-08-19T00:00:00Z",
          counterOfId: null,
        },
      ],
    });
    rejectTradeProposalMock.mockReset().mockResolvedValue({});
    const { container, unmount } = await renderAppAt("/mercato");
    const card = container.querySelector('[data-testid="market-trade-proposal-proposal-received"]');
    const reject = [...(card?.querySelectorAll("button") ?? [])].find(
      (button) => (button.textContent ?? "") === "Rifiuta",
    );
    await act(async () => {
      reject!.click();
    });
    await flushAsync();
    expect(rejectTradeProposalMock).toHaveBeenCalledWith("access-token", "league-1", "proposal-received");
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(acceptTradeProposalMock).not.toHaveBeenCalled();
    unmount();
  });

  it("admin: proposta in attesa di approvazione mostra Approva/Rifiuta (admin)", async () => {
    fetchTradeProposalsMock.mockReset().mockResolvedValue({
      proposals: [
        {
          id: "proposal-pending",
          leagueId: "league-1",
          proposerTeamId: "team-1",
          recipientTeamId: "team-2",
          offeredAthletes: [],
          requestedAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
          offeredCredits: 5,
          requestedCredits: 0,
          status: "pending_approval",
          expiresAt: "2026-09-01T00:00:00Z",
          createdAt: "2026-08-19T00:00:00Z",
          counterOfId: null,
        },
      ],
    });
    const adminLeague: LeagueSummary = { id: "league-1", name: "Lega Test", role: "league_admin" };
    const { html, unmount } = await renderAppAt("/mercato", [adminLeague]);
    expect(html).toContain('data-testid="market-trade-admin-actions-proposal-pending"');
    expect(html).toContain("Approva");
    expect(html).toContain("Rifiuta (admin)");
    unmount();
  });

  it("proposta in attesa di crediti: Accetta è sospeso, e le statistiche contano gli scambi eseguiti", async () => {
    const base = {
      leagueId: "league-1",
      offeredAthletes: [],
      requestedAthletes: [],
      offeredCredits: 0,
      requestedCredits: 0,
      expiresAt: null,
      createdAt: "2026-08-19T00:00:00Z",
      counterOfId: null,
    };
    fetchTradeProposalsMock.mockReset().mockResolvedValue({
      proposals: [
        {
          ...base,
          id: "p-wait",
          proposerTeamId: "team-2",
          recipientTeamId: "team-1",
          offeredCredits: 500,
          status: "proposed",
          awaitingCredits: true,
        },
        { ...base, id: "p-done", proposerTeamId: "team-1", recipientTeamId: "team-2", status: "executed" },
        { ...base, id: "p-acc", proposerTeamId: "team-1", recipientTeamId: "team-2", status: "accepted" },
        { ...base, id: "p-no", proposerTeamId: "team-1", recipientTeamId: "team-2", status: "cancelled" },
        { ...base, id: "p-rej", proposerTeamId: "team-1", recipientTeamId: "team-2", status: "rejected" },
      ],
    });
    const adminLeague: LeagueSummary = { id: "league-1", name: "Lega Test", role: "league_admin" };
    const { html, container, unmount } = await renderAppAt("/mercato", [adminLeague]);
    expect(html).toContain("In attesa di crediti");
    const wait = container.querySelector('[data-testid="market-trade-proposal-p-wait"]');
    const acceptButton = [...(wait?.querySelectorAll("button") ?? [])].find((b) =>
      (b.textContent ?? "").includes("In attesa di crediti"),
    );
    expect(acceptButton?.hasAttribute("disabled")).toBe(true);
    // Sospeso: nessuna conferma da aprire, nessuna chiamata.
    await act(async () => {
      acceptButton!.click();
    });
    expect(container.querySelector('[data-testid="market-trade-accept-dialog"]')).toBeNull();
    expect(acceptTradeProposalMock).not.toHaveBeenCalled();
    const stats = container.querySelector('[data-testid="market-trade-stats"]');
    const statText = (label: string) =>
      [...(stats?.querySelectorAll(".fa-trade-stat") ?? [])]
        .find((node) => (node.textContent ?? "").includes(label))
        ?.querySelector("strong")?.textContent;
    expect(statText("Scambi conclusi")).toBe("2");
    expect(statText("Da approvare")).toBe("0");
    unmount();
  });

  it("membro non vede le azioni admin su una proposta in attesa di approvazione", async () => {
    fetchTradeProposalsMock.mockReset().mockResolvedValue({
      proposals: [
        {
          id: "proposal-pending",
          leagueId: "league-1",
          proposerTeamId: "team-1",
          recipientTeamId: "team-2",
          offeredAthletes: [],
          requestedAthletes: [{ id: "athlete-2", name: "Giocatore Avversario" }],
          offeredCredits: 5,
          requestedCredits: 0,
          status: "pending_approval",
          expiresAt: "2026-09-01T00:00:00Z",
          createdAt: "2026-08-19T00:00:00Z",
          counterOfId: null,
        },
      ],
    });
    const { html, unmount } = await renderAppAt("/mercato", [LEAGUE]);
    expect(html).not.toContain('data-testid="market-trade-admin-actions-proposal-pending"');
    unmount();
  });
});

// Sezione nascosta da MarketPage (SHOW_MARKET_HISTORY = false, ADR-0006): lo storico
// scambi resta consultabile in Rosa. Test tenuti per un eventuale ripristino della UI.
describe.skip("Mercato — storico collegato alle API reali (EP08-08)", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(TEAM_WITH_PLAYER);
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
    fetchMarketHistoryMock.mockReset();
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("nessun evento mostra lo stato vuoto", async () => {
    fetchMarketHistoryMock.mockResolvedValue({
      items: [],
      page: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0,
    });
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-history-empty"');
    unmount();
  });

  it("errore nel caricamento dello storico mostra lo stato di errore", async () => {
    fetchMarketHistoryMock.mockRejectedValue(
      new ApiError("Errore dal server.", 500, "internal_error"),
    );
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-history-error"');
    expect(html).toContain("Errore dal server.");
    unmount();
  });

  it("elenca gli eventi e mostra la paginazione", async () => {
    fetchMarketHistoryMock.mockResolvedValue({
      items: [
        {
          id: "event-1",
          occurredAt: "2026-08-19T10:00:00Z",
          category: "acquisto",
          action: "market_session_resolved",
          actorId: "user-1",
          details: { sessionId: "session-1" },
        },
      ],
      page: 1,
      pageSize: 20,
      total: 25,
      totalPages: 2,
    });
    const { html, unmount } = await renderAppAt("/mercato");
    expect(html).toContain('data-testid="market-history-entry-event-1"');
    expect(html).toContain("market_session_resolved");
    expect(html).toContain("Pagina 1 di 2");
    expect(html).toContain("25 eventi");
    unmount();
  });

  it("passa la categoria selezionata come filtro alla chiamata API", async () => {
    fetchMarketHistoryMock.mockResolvedValue({
      items: [],
      page: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0,
    });
    const { unmount } = await renderAppAt("/mercato");
    expect(fetchMarketHistoryMock).toHaveBeenCalledWith(
      "access-token",
      "league-1",
      expect.objectContaining({ category: undefined, fantasyTeamId: undefined }),
    );
    unmount();
  });
});
