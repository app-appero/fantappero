import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { AppRoutes } from "../routes";
import { MemoryRouter } from "../router/simpleRouter";
import { CreateLeagueSuccess } from "./CreateLeaguePage";

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

  it("renders a compact success view with optional invites after creation", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/leghe/crea?persona=admin"],
        children: createElement(CreateLeagueSuccess, {
          league: {
            id: "demo-created-league",
            name: "Test",
            seasonYear: new Date().getFullYear(),
            state: "draft",
            viewerRole: "league_admin",
            competitions: [],
            rules: {
              presetName: "standard",
              participantCount: 8,
              participantMin: 4,
              participantMax: 10,
              roster: {
                rosterSize: 35,
                goalkeepers: 3,
                defenders: 11,
                midfielders: 11,
                forwards: 10,
              },
              totalCredits: 1000,
              minFixturesPerRound: 25,
              turnCoverageThreshold: 0.75,
              lineupLockMarginMinutes: 15,
              minutesThreshold: 15,
              voluntaryReleaseRefundPercent: 50,
              leagueExitRefundPercent: 100,
              maxActiveTradeProposalsPerTeam: 10,
              options: {
                allowTrades: true,
                allowManualInvites: true,
                requireTradeApproval: false,
              },
            },
          },
          isDemoMode: true,
          search: "?persona=admin",
        }),
      }),
    );
    expect(html).toContain("fa-create-league-success");
    expect(html).toContain('data-testid="create-league-success"');
    expect(html).toContain("Fase 1 completata: lega salvata");
    expect(html).toContain("Invita fantallenatori");
    expect(html).toContain("fa-manager-directory--compact");
    expect(html).toContain('data-testid="create-league-go-admin"');
    expect(html).toContain("Configura la lega");
    expect(html).toContain('href="/lega/amministrazione?persona=admin"');
    expect(html).toContain('data-testid="create-league-done"');
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
