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
  deleteLeague: vi.fn(),
}));

function renderCreateLeague(path = "/leghe/crea?persona=admin") {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

describe("EP03-01 create league page", () => {
  it("renders demo create form with competitions", () => {
    const html = renderCreateLeague();
    expect(html).toContain('data-testid="create-league-form"');
    expect(html).toContain("Nome lega");
    expect(html).toContain("Campionati (minimo 3)");
    expect(html).toContain("Premier League");
    expect(html).toContain('data-testid="create-league-select-all"');
    expect(html).toContain("Seleziona tutto");
    const year = new Date().getFullYear();
    expect(html).toContain(`${year}-${year + 1}`);
    expect(html).toContain('data-testid="create-league-season"');
  });

  it("redirects unauthenticated users away from create route", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/leghe/crea"],
        children: createElement(AuthProvider, {
          children: createElement(AppRoutes),
        }),
      }),
    );
    expect(html).toContain('data-testid="auth-redirect"');
  });
});

function renderLeagues(path = "/leghe?persona=admin") {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

describe("EP03-01 leagues page", () => {
  it("renders create and join league actions in demo mode", () => {
    const html = renderLeagues();
    expect(html).toContain('data-testid="header-create-league-link"');
    expect(html).toContain("Crea lega");
    expect(html).toContain('data-testid="header-join-league-link"');
    expect(html).toContain("Unisciti con codice");
  });
});
