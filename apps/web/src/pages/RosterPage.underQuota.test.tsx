import type { FantasyTeam, LeagueSummary, SessionUser, TradeReplacementStatus } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Corsa Mercato del 25/11: rosa alla misura (35/35) ma un ruolo sotto quota. La pagina Rosa lo
// dice in un riquadro informativo, senza bloccare niente; con sostituti da scegliere si vede il
// riquadro dei sostituti al suo posto.

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchMyFantasyTeamMock = vi.fn();
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
  refreshLeagueListone: vi.fn(),
  fetchTeamPlayersForTrade: vi.fn().mockResolvedValue([]),
  assignRandomAiRoster: vi.fn(),
  assignRosterSlot: vi.fn(),
  confirmRosterCsvImport: vi.fn(),
  createRosterTurnSnapshot: vi.fn(),
  downloadAllRostersExcelExport: vi.fn(),
  downloadRosterExcelExport: vi.fn(),
  downloadRosterExcelTemplate: vi.fn(),
  ensureFantasyTeams: vi.fn(),
  fetchFantasyTeamCreditsForAdmin: vi.fn(),
  fetchFantasyTeamForAdmin: vi.fn(),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchLeagueListone: vi.fn().mockResolvedValue([]),
  fetchMyCreditMovements: vi.fn().mockResolvedValue({ fantasyTeamId: "team-1", balance: 40, version: 1, entries: [] }),
  fetchMyCredits: vi.fn().mockResolvedValue({ fantasyTeamId: "team-1", balance: 40, version: 1, reconstructedBalance: 40 }),
  fetchMyFantasyTeam: (...args: unknown[]) => fetchMyFantasyTeamMock(...args),
  fetchMyRosterHistory: vi.fn().mockResolvedValue({ fantasyTeamId: "team-1", intervals: [] }),
  fetchRosterOccupancy: vi.fn().mockResolvedValue([]),
  fetchRosterTurnSnapshot: vi.fn(),
  fetchRosterTurnSnapshots: vi.fn().mockResolvedValue([]),
  fetchTeamRosterHistoryForAdmin: vi.fn(),
  postAdminCreditMovement: vi.fn(),
  previewBulkRosterImport: vi.fn(),
  previewRosterCsvImport: vi.fn(),
  releaseRosterSlot: vi.fn(),
}));

vi.mock("../api/market", () => ({
  fetchMarketGate: vi.fn().mockResolvedValue({ marketOpen: true }),
  setMarketGate: vi.fn(),
  fetchTradeReplacements: (...args: unknown[]) => fetchTradeReplacementsMock(...args),
  fetchTradeReplacementCandidates: vi.fn().mockResolvedValue({ role: "D", balance: 40, total: 0, candidates: [] }),
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

function team(filledSlots: number, underQuotaRoles: { role: "C"; count: number; quota: number }[]): FantasyTeam {
  return {
    id: "team-1",
    leagueId: "league-1",
    membershipId: "membership-1",
    userId: "user-1",
    userType: "human",
    name: "Squadra Test",
    rosterSize: 35,
    filledSlots,
    compositionStatus: "validated",
    composition: {
      status: "validated",
      filledSlots,
      competitionCount: 3,
      requireComplete: true,
      validatedAt: null,
      limits: { rosterSize: 35, goalkeepers: 3, defenders: 11, midfielders: 11, forwards: 10 },
      counts: { P: 3, D: 12, C: 9, A: 11 },
      issues: [],
      underQuotaRoles,
    },
    slots: [],
  };
}

const NO_REPLACEMENT: TradeReplacementStatus = {
  teamId: "team-1",
  rosterSize: 35,
  filledSlots: 35,
  balance: 40,
  pending: [],
  missingRoles: [],
  tradeProposalId: null,
  otherTeamName: null,
  receivedAthleteNames: [],
  receivedCredits: 0,
  blockedReason: null,
  blockedMessage: null,
};

async function flushAsync(rounds = 8): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

async function renderRoster(): Promise<{ container: HTMLDivElement; unmount: () => void }> {
  fetchMeMock.mockResolvedValue(USER);
  fetchMyLeaguesMock.mockResolvedValue([LEAGUE]);
  saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);
  await act(async () => {
    root.render(
      createElement(MemoryRouter, {
        initialEntries: ["/rosa"],
        children: createElement(AuthProvider, { children: createElement(AppRoutes) }),
      }),
    );
  });
  await flushAsync();
  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

function byTestId(container: HTMLElement, id: string): HTMLElement | null {
  return container.querySelector(`[data-testid="${id}"]`);
}

describe("Rosa: ruoli sotto quota con la rosa piena (corsa Mercato del 25/11)", () => {
  beforeEach(() => {
    clearStoredSession();
    window.sessionStorage.clear();
    fetchTradeReplacementsMock.mockReset().mockResolvedValue(NO_REPLACEMENT);
  });

  afterEach(() => {
    clearStoredSession();
    document.body.innerHTML = "";
  });

  it("35/35 con 9 Centrocampisti su 11: riquadro informativo, non bloccante", async () => {
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(team(35, [{ role: "C", count: 9, quota: 11 }]));
    const { container, unmount } = await renderRoster();
    const notice = byTestId(container, "roster-under-quota");
    expect(notice?.textContent).toBe(
      "Ruoli sotto quota: 9 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.",
    );
    expect(notice?.getAttribute("role")).toBe("note");
    expect(notice?.className).toContain("fa-shortfall--info");
    expect(byTestId(container, "roster-shortfall-banner")).toBeNull();
    unmount();
  });

  it("nessun riquadro con i ruoli alla quota o con la rosa non ancora alla misura", async () => {
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(team(35, []));
    const full = await renderRoster();
    expect(byTestId(full.container, "roster-under-quota")).toBeNull();
    full.unmount();

    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(team(20, [{ role: "C", count: 4, quota: 11 }]));
    const partial = await renderRoster();
    expect(byTestId(partial.container, "roster-under-quota")).toBeNull();
    partial.unmount();
  });

  it("con sostituti da scegliere si vede il riquadro dei sostituti, non questo", async () => {
    fetchMyFantasyTeamMock.mockReset().mockResolvedValue(team(35, [{ role: "C", count: 9, quota: 11 }]));
    fetchTradeReplacementsMock.mockReset().mockResolvedValue({
      ...NO_REPLACEMENT,
      filledSlots: 34,
      pending: [{ id: "r1", role: "C", tradeProposalId: "p1", createdAt: "2026-11-25T10:00:00Z" }],
      missingRoles: [{ role: "C", count: 1 }],
      tradeProposalId: "p1",
    });
    // La finestra si apre da sola una volta per sessione: già vista, resta chiusa.
    window.sessionStorage.setItem("fa.sostituto.rimandato.league-1", "1");
    const { container, unmount } = await renderRoster();
    expect(byTestId(container, "roster-shortfall-banner")).not.toBeNull();
    expect(byTestId(container, "roster-under-quota")).toBeNull();
    unmount();
  });
});
