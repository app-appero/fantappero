import type { LeagueStanding, LeagueSummary, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchLeagueStandingsMock = vi.fn();
const fetchMyFantasyTeamMock = vi.fn();

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
  fetchLeagueStandings: (...args: unknown[]) => fetchLeagueStandingsMock(...args),
  fetchMyFantasyTeam: (...args: unknown[]) => fetchMyFantasyTeamMock(...args),
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
const MEMBER_USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

const STANDINGS: LeagueStanding[] = [
  {
    fantasyTeamId: "team-rival",
    teamName: "Rivali FC",
    managerUserId: "user-rival",
    position: 1,
    played: 2,
    won: 2,
    drawn: 0,
    lost: 0,
    fantasyGoalsFor: 5,
    fantasyGoalsAgainst: 1,
    fantasyPointsFor: 148.5,
    fantasyPointsAgainst: 130,
    points: 6,
    computedAt: "2026-08-20T12:00:00.000Z",
  },
  {
    fantasyTeamId: "team-mine",
    teamName: "La mia squadra",
    managerUserId: "user-1",
    position: 2,
    played: 2,
    won: 1,
    drawn: 0,
    lost: 1,
    fantasyGoalsFor: 3,
    fantasyGoalsAgainst: 4,
    fantasyPointsFor: 130,
    fantasyPointsAgainst: 148.5,
    points: 3,
    computedAt: "2026-08-20T12:00:00.000Z",
  },
];

async function flushAsync(rounds = 8): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

async function renderAppAt(path: string): Promise<{ html: string; unmount: () => void }> {
  fetchMeMock.mockResolvedValue(MEMBER_USER);
  fetchMyLeaguesMock.mockResolvedValue([LEAGUE]);
  saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: MEMBER_USER });

  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: Root | null = createRoot(container);

  await act(async () => {
    root!.render(
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
      root?.unmount();
      root = null;
      container.remove();
    },
  };
}

describe("StandingsPage real session", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchMeMock.mockReset();
    fetchMyLeaguesMock.mockReset();
    fetchLeagueStandingsMock.mockReset();
    fetchMyFantasyTeamMock.mockReset();
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("loads standings from the API and highlights the current team", async () => {
    fetchLeagueStandingsMock.mockResolvedValue(STANDINGS);
    fetchMyFantasyTeamMock.mockResolvedValue({
      id: "team-mine",
      leagueId: "league-1",
      membershipId: "m-1",
      userId: "user-1",
      userType: "human",
      name: "La mia squadra",
      rosterSize: 35,
      filledSlots: 35,
      compositionStatus: "validated",
      composition: null,
      slots: [],
    });

    const { html, unmount } = await renderAppAt("/classifica");
    try {
      expect(fetchLeagueStandingsMock).toHaveBeenCalledWith("access-token", "league-1");
      expect(html).toContain('data-testid="standings-success"');
      expect(html).toContain('data-testid="standings-table"');
      expect(html).toContain("Rivali FC");
      expect(html).toContain("La mia squadra");
      expect(html).toContain('data-testid="standings-row-current"');
    } finally {
      unmount();
    }
  });

  it("shows empty state when standings have not been computed yet", async () => {
    fetchLeagueStandingsMock.mockResolvedValue([]);
    fetchMyFantasyTeamMock.mockResolvedValue({
      id: "team-mine",
      leagueId: "league-1",
      membershipId: "m-1",
      userId: "user-1",
      userType: "human",
      name: "La mia squadra",
      rosterSize: 35,
      filledSlots: 0,
      compositionStatus: "incomplete",
      composition: null,
      slots: [],
    });

    const { html, unmount } = await renderAppAt("/classifica");
    try {
      expect(html).toContain('data-testid="standings-empty"');
      expect(html).toContain("Classifica non ancora disponibile");
    } finally {
      unmount();
    }
  });
});
