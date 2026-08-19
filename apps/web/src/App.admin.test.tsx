import type { SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchAdminOverviewMock = vi.fn();
const fetchAdminUsersMock = vi.fn();
const fetchAdminLeaguesMock = vi.fn();
const fetchAdminListoneMock = vi.fn();
const refreshAdminListoneMock = vi.fn();

vi.mock("./api/auth", () => ({
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

vi.mock("./api/leagues", () => ({
  fetchMyLeagues: (...args: unknown[]) => fetchMyLeaguesMock(...args),
  fetchCompetitions: vi.fn(),
  fetchLeague: vi.fn(),
}));

vi.mock("./api/admin", () => ({
  fetchAdminOverview: (...args: unknown[]) => fetchAdminOverviewMock(...args),
  fetchAdminUsers: (...args: unknown[]) => fetchAdminUsersMock(...args),
  fetchAdminLeagues: (...args: unknown[]) => fetchAdminLeaguesMock(...args),
  fetchAdminListone: (...args: unknown[]) => fetchAdminListoneMock(...args),
  refreshAdminListone: (...args: unknown[]) => refreshAdminListoneMock(...args),
  promoteOperator: vi.fn(),
  revokeOperator: vi.fn(),
}));

import { AuthProvider } from "./auth/AuthContext";
import { clearStoredSession, saveStoredSession } from "./auth/sessionStorage";
import { MemoryRouter } from "./router/simpleRouter";
import { AppRoutes } from "./routes";

/**
 * Real (non-demo) session gate tests for /admin, per EP11-04a: the operator
 * identity must come from a mocked auth session — never from `?persona=`.
 */

const MEMBER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };
const OPERATOR: SessionUser = {
  id: "op-1",
  displayName: "Operatore Test",
  globalRole: "global_operator",
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
): Promise<{ html: string; unmount: () => void }> {
  fetchMeMock.mockResolvedValue(user);
  fetchMyLeaguesMock.mockResolvedValue([]);
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

describe("Admin panel identity gate (EP11-04a)", () => {
  beforeEach(() => {
    clearStoredSession();
    fetchAdminOverviewMock.mockReset();
    fetchAdminUsersMock.mockReset();
    fetchAdminLeaguesMock.mockReset();
    fetchAdminListoneMock.mockReset();
    refreshAdminListoneMock.mockReset();
  });

  afterEach(() => {
    clearStoredSession();
  });

  it("hides Pannello globale link for a member session", async () => {
    const { html, unmount } = await renderAppAt("/leghe", MEMBER);
    expect(html).not.toContain('data-testid="admin-panel-link"');
    unmount();
  });

  it("shows Pannello globale link for an operator session", async () => {
    const { html, unmount } = await renderAppAt("/leghe", OPERATOR);
    expect(html).toContain('data-testid="admin-panel-link"');
    expect(html).toContain("Pannello globale");
    unmount();
  });

  it("blocks /admin for a member session", async () => {
    const { html, unmount } = await renderAppAt("/admin", MEMBER);
    expect(html).toContain('data-testid="route-forbidden"');
    expect(html).not.toContain('data-testid="admin-dashboard-success"');
    unmount();
  });

  it("blocks /admin/utenti, /admin/leghe and /admin/listone for a member session", async () => {
    const usersResult = await renderAppAt("/admin/utenti", MEMBER);
    expect(usersResult.html).toContain('data-testid="route-forbidden"');
    usersResult.unmount();

    const leaguesResult = await renderAppAt("/admin/leghe", MEMBER);
    expect(leaguesResult.html).toContain('data-testid="route-forbidden"');
    leaguesResult.unmount();

    const listoneResult = await renderAppAt("/admin/listone", MEMBER);
    expect(listoneResult.html).toContain('data-testid="route-forbidden"');
    listoneResult.unmount();
  });

  it("allows an operator session into /admin with real overview data", async () => {
    fetchAdminOverviewMock.mockResolvedValue({
      operatorId: OPERATOR.id,
      operatorDisplayName: OPERATOR.displayName,
      environment: "test",
      usersCount: 3,
      operatorsCount: 1,
      leaguesCount: 2,
    });

    const { html, unmount } = await renderAppAt("/admin", OPERATOR);
    expect(html).toContain('data-surface="admin"');
    expect(html).toContain('data-testid="admin-dashboard-success"');
    expect(html).not.toContain('data-testid="route-forbidden"');
    unmount();
  });

  it("smoke: operator reaches /admin/utenti with real user data", async () => {
    fetchAdminUsersMock.mockResolvedValue({
      items: [
        {
          id: "target-1",
          email: "target@example.com",
          displayName: "Utente Target",
          platformRole: "user",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
      page: 1,
      pageSize: 20,
      total: 1,
      totalPages: 1,
    });

    const { html, unmount } = await renderAppAt("/admin/utenti", OPERATOR);
    expect(html).toContain('data-testid="admin-users-list"');
    expect(html).toContain("target@example.com");
    unmount();
  });

  it("smoke: operator reaches /admin/leghe with real league data", async () => {
    fetchAdminLeaguesMock.mockResolvedValue({
      items: [
        {
          id: "league-1",
          name: "Lega Globale",
          state: "active",
          ownerDisplayName: "Proprietario",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
      page: 1,
      pageSize: 20,
      total: 1,
      totalPages: 1,
    });

    const { html, unmount } = await renderAppAt("/admin/leghe", OPERATOR);
    expect(html).toContain('data-testid="admin-leagues-list"');
    expect(html).toContain("Lega Globale");
    unmount();
  });

  it("smoke: operator reaches /admin/listone with real listone data", async () => {
    fetchAdminListoneMock.mockResolvedValue([
      {
        athleteId: "athlete-1",
        canonicalName: "Giocatore Esempio",
        seasonYear: new Date().getFullYear(),
        officialRole: "A",
        providerPositionRaw: "Attacker",
        mappingVersion: "v1.0.0",
        clubId: "club-1",
        clubName: "Club Esempio",
      },
    ]);

    const { html, unmount } = await renderAppAt("/admin/listone", OPERATOR);
    expect(html).toContain('data-surface="admin"');
    expect(html).toContain('data-testid="admin-listone-refresh"');
    expect(html).toContain("Giocatore Esempio");
    expect(html).not.toContain('data-testid="route-forbidden"');
    unmount();
  });
});
