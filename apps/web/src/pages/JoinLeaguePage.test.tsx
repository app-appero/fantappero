import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { MemoryRouter } from "../router/simpleRouter";
import { AppRoutes } from "../routes";

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
  fetchLeagueAdminPanel: vi.fn(),
  updateLeagueRules: vi.fn(),
  transitionLeagueState: vi.fn(),
  fetchLeagueInvites: vi.fn(),
  createLeagueInvite: vi.fn(),
  revokeLeagueInvite: vi.fn(),
  acceptLeagueInvite: vi.fn(),
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

describe("EP03-03 join league page", () => {
  it("renders code entry empty flow", () => {
    const html = renderRoute("/leghe/invito?persona=member");
    expect(html).toContain('data-testid="join-league-form"');
    expect(html).toContain("Codice invito");
    expect(html).toContain("link");
    expect(html).toContain("codice");
    expect(html).toContain("ricerca pubblica");
  });

  it("renders token positive flow", () => {
    const html = renderRoute("/leghe/invito?persona=member&token=test-token");
    expect(html).toContain("Il link invito è pronto");
    expect(html).toContain("Entra nella lega");
  });

  it("renders error flow", () => {
    const html = renderRoute("/leghe/invito?persona=member&stato=error");
    expect(html).toContain('data-testid="join-league-error"');
    expect(html).toContain("Ingresso non riuscito");
  });

  it("renders success flow with home CTA", () => {
    const html = renderRoute("/leghe/invito?persona=member&stato=success");
    expect(html).toContain('data-testid="join-league-success"');
    expect(html).toContain("Ingresso completato");
    expect(html).toContain('data-testid="join-league-open-home"');
    expect(html).toContain("Apri home lega");
  });
});
