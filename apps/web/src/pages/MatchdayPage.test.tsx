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
  fetchH2HCalendar: vi.fn(),
  fetchH2HMatchup: vi.fn(),
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
  openFantasyTurn: vi.fn(),
  excludeFantasyTurnFixture: vi.fn(),
  recalculateFantasyTurnCutoff: vi.fn(),
  fetchPendingFixtures: vi.fn(),
  startCalendarRefresh: vi.fn(),
  fetchCalendarRefreshProgress: vi.fn(),
  refreshFullCalendar: vi.fn(),
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

describe("Matchday page H2H + europei", () => {
  it("renders H2H calendar with giornata selector defaulting to current round", () => {
    const html = renderRoute("/turni?persona=admin&stato=success");
    expect(html).toContain("Calendario fantallenatori");
    expect(html).toContain("Turni europei");
    expect(html).toContain('data-testid="h2h-calendar"');
    expect(html).toContain('data-testid="h2h-round-select"');
    expect(html).toContain("Giornata 2");
    expect(html).toContain("Marco FC");
    expect(html).toContain("Riposo");
    expect(html).toContain("storico");
  });

  it("renders european tab with competition columns and turn select", () => {
    const html = renderRoute("/turni?persona=admin&stato=success&tab=europei");
    expect(html).toContain('data-testid="matchday-turn-detail"');
    expect(html).toContain('data-testid="matchday-turn-select"');
    expect(html).toContain('data-testid="matchday-admin"');
    expect(html).toContain('data-testid="matchday-refresh-calendar"');
    expect(html).toContain("Aggiorna calendario");
    expect(html).toContain("West Ham");
    expect(html).toContain("Premier League");
    expect(html).toContain("Serie A");
    expect(html).toContain("Rinviata");
  });

  it("shows H2H empty state", () => {
    const html = renderRoute("/turni?persona=admin&stato=empty");
    expect(html).toContain('data-testid="h2h-empty"');
  });

  it("shows H2H error state with retry", () => {
    const html = renderRoute("/turni?persona=member&stato=error");
    expect(html).toContain('data-testid="h2h-error"');
    expect(html).toContain("Ricarica");
  });

  it("shows forbidden state", () => {
    const html = renderRoute("/turni?persona=member&stato=forbidden");
    expect(html).toContain('data-testid="matchday-forbidden"');
  });

  it("shows H2H loading state", () => {
    const html = renderRoute("/turni?persona=admin&stato=loading");
    expect(html).toContain('data-testid="h2h-loading"');
  });

  it("renders matchup detail demo", () => {
    const html = renderRoute("/turni/scontro/slot-demo-1?persona=admin&stato=success");
    expect(html).toContain('data-testid="matchup-detail"');
    expect(html).toContain("Marco FC");
    expect(html).toContain("Giulia United");
    expect(html).toContain("Provvisorio");
    expect(html).toContain("formazione effettiva");
    expect(html).toContain('data-testid="football-pitch"');
  });

  it("shows matchup forbidden state", () => {
    const html = renderRoute("/turni/scontro/slot-demo-1?persona=member&stato=forbidden");
    expect(html).toContain('data-testid="matchup-forbidden"');
  });
});
