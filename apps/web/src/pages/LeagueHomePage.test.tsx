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

describe("EP03-UX-01 leagues page", () => {
  it("renders enter and join CTAs for members", () => {
    const html = renderRoute("/leghe?persona=member");
    expect(html).toContain("Entra in lega");
    expect(html).toContain('data-testid="leagues-join-link"');
    expect(html).toContain("Unisciti con codice");
    expect(html).toContain('data-testid="leagues-create-link"');
    expect(html).not.toContain("Amministrazione lega");
  });

  it("keeps admin secondary link alongside enter CTA", () => {
    const html = renderRoute("/leghe?persona=admin");
    expect(html).toContain("Entra in lega");
    expect(html).toContain("Amministrazione lega");
  });

  it("shows delete CTA for admin deletable leagues", () => {
    const html = renderRoute("/leghe?persona=admin");
    expect(html).toContain('data-testid="league-delete-demo-league-1"');
    expect(html).toContain('data-testid="league-delete-demo-league-3"');
    expect(html).toContain("Elimina lega");
  });

  it("hides delete CTA for members", () => {
    const html = renderRoute("/leghe?persona=member");
    expect(html).not.toContain('data-testid="league-delete-demo-league-1"');
    expect(html).not.toContain("Elimina lega");
  });

  it("renders empty state with join CTA", () => {
    const html = renderRoute("/leghe?persona=member&stato=empty");
    expect(html).toContain('data-testid="leagues-empty"');
    expect(html).toContain('data-testid="leagues-join-link"');
  });
});

describe("EP03-UX-02 league home", () => {
  it("renders home content for members", () => {
    const html = renderRoute("/lega/home?persona=member");
    expect(html).toContain('data-testid="league-home-content"');
    expect(html).toContain("Regolamento");
    expect(html).toContain('data-testid="league-home-members-list"');
    expect(html).toContain("disponibile dalla prossima fase");
  });

  it("shows admin link for admin persona", () => {
    const html = renderRoute("/lega/home?persona=admin");
    expect(html).toContain('data-testid="league-home-admin-link"');
  });

  it("renders empty state without selected league content when forced empty", () => {
    const html = renderRoute("/lega/home?persona=member&stato=empty");
    expect(html).toContain('data-testid="league-home-empty"');
  });

  it("renders error state", () => {
    const html = renderRoute("/lega/home?persona=member&stato=error");
    expect(html).toContain('data-testid="league-home-error"');
  });
});

describe("EP03-03 invite discoverability", () => {
  it("shows code and link copy actions after invite generation", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('data-testid="league-invite-created"');
    expect(html).toContain('data-testid="league-invite-code"');
    expect(html).toContain('data-testid="league-invite-url"');
    expect(html).toContain('data-testid="league-invite-copy-code"');
    expect(html).toContain('data-testid="league-invite-copy-url"');
    expect(html).toContain("link");
    expect(html).toContain("codice");
  });

  it("shows delete panel for draft league", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('data-testid="league-delete-panel"');
    expect(html).toContain("Elimina lega");
    expect(html).toContain('data-testid="league-delete-confirm"');
  });
});
