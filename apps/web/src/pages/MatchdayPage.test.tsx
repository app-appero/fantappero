import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { AppRoutes } from "../routes";
import { MemoryRouter } from "../router/simpleRouter";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  fetchMe: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../api/leagues", () => ({
  fetchCompetitions: vi.fn(),
  fetchMyLeagues: vi.fn(),
  createLeague: vi.fn(),
  fetchLeague: vi.fn(),
  fetchLeagueMembersPublic: vi.fn(),
  fetchLeagueCalendar: vi.fn(),
  deleteLeague: vi.fn(),
  fetchLeagueAdminPanel: vi.fn(),
  updateLeagueRules: vi.fn(),
  transitionLeagueState: vi.fn(),
  fetchLeagueMembers: vi.fn(),
  transferLeagueAdmin: vi.fn(),
  removeLeagueMember: vi.fn(),
  fetchLeagueInvites: vi.fn(),
  createLeagueInvite: vi.fn(),
  revokeLeagueInvite: vi.fn(),
  acceptLeagueInvite: vi.fn(),
  fetchLeagueCalendarAdmin: vi.fn(),
  generateLeagueCalendar: vi.fn(),
  confirmLeagueCalendar: vi.fn(),
  fetchFantasyTurns: vi.fn(),
  fetchFantasyTurn: vi.fn(),
  previewFantasyTurn: vi.fn(),
  generateFantasyTurn: vi.fn(),
  openFantasyTurn: vi.fn(),
  excludeFantasyTurnFixture: vi.fn(),
  recalculateFantasyTurnCutoff: vi.fn(),
}));

function renderRoute(path: string) {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

describe("EP06-01 / EP06-07 matchday page", () => {
  it("renders success demo with turn detail and admin tools", () => {
    const html = renderRoute("/turni?persona=admin&stato=success");
    expect(html).toContain('data-testid="matchday-turn-detail"');
    expect(html).toContain('data-testid="matchday-admin"');
    expect(html).toContain("Genera turno");
    expect(html).toContain("West Ham");
    expect(html).toContain("Rinviata");
    expect(html).toContain('data-testid="matchday-lock-latched-fx-1"');
    expect(html).toContain('data-testid="matchday-cutoff-latch"');
  });

  it("shows empty state", () => {
    const html = renderRoute("/turni?persona=admin&stato=empty");
    expect(html).toContain('data-testid="matchday-empty"');
  });

  it("shows error state with retry", () => {
    const html = renderRoute("/turni?persona=member&stato=error");
    expect(html).toContain('data-testid="matchday-error"');
    expect(html).toContain("Ricarica");
  });

  it("shows forbidden state", () => {
    const html = renderRoute("/turni?persona=member&stato=forbidden");
    expect(html).toContain('data-testid="matchday-forbidden"');
  });

  it("shows loading state", () => {
    const html = renderRoute("/turni?persona=admin&stato=loading");
    expect(html).toContain('data-testid="matchday-loading"');
  });
});
