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
  fetchLeagueListone: vi.fn(),
  refreshLeagueListone: vi.fn(),
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

describe("AuctionPage layout + listone", () => {
  it("admin: sessione + offerta + listone senza Aggiorna", () => {
    const html = renderRoute("/asta?persona=admin");
    expect(html).toContain('data-testid="wireframe-region-auction-admin"');
    expect(html).toContain("Apri asta");
    expect(html).toContain('data-testid="wireframe-region-auction-bid"');
    expect(html).toContain('data-testid="auction-bid-panel"');
    expect(html).toContain('data-testid="auction-listone-card"');
    expect(html).toContain("Listone ufficiale");
    expect(html).toContain("Rui Patrício");
    expect(html).toContain("Portieri");
    expect(html).toContain("Difensori");
    expect(html).toContain("Centrocampisti");
    expect(html).toContain("Attaccanti");
    expect(html).not.toContain('data-testid="auction-listone-refresh"');
  });

  it("member: offerta + listone senza admin e senza Aggiorna", () => {
    const html = renderRoute("/asta?persona=member");
    expect(html).not.toContain('data-testid="wireframe-region-auction-admin"');
    expect(html).toContain('data-testid="wireframe-region-auction-bid"');
    expect(html).toContain('data-testid="auction-bid-panel"');
    expect(html).toContain('data-testid="auction-listone-card"');
    expect(html).not.toContain('data-testid="auction-listone-refresh"');
  });

  it("mostra empty state demo sul listone", () => {
    const html = renderRoute("/asta?persona=admin&stato=empty");
    expect(html).toContain('data-testid="wireframe-region-auction-bid"');
    expect(html).toContain('data-testid="auction-listone-empty-all"');
    expect(html).toContain("Il listone è vuoto");
  });
});
