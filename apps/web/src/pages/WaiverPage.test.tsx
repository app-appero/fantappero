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
  fetchMyCredits: vi.fn(),
  fetchMyFantasyTeam: vi.fn(),
}));

vi.mock("../api/market", () => ({
  createAuctionSession: vi.fn(),
  closeAuctionSession: vi.fn(),
  resolveAuctionSession: vi.fn(),
  fetchAuctionSessions: vi.fn(),
  fetchAuctionSession: vi.fn(),
  submitAuctionBid: vi.fn(),
  withdrawAuctionBid: vi.fn(),
  fetchMyAuctionBids: vi.fn(),
  createWaiverSession: vi.fn(),
  closeWaiverSession: vi.fn(),
  resolveWaiverSession: vi.fn(),
  fetchWaiverSessions: vi.fn(),
  fetchWaiverSession: vi.fn(),
  submitWaiverBid: vi.fn(),
  withdrawWaiverBid: vi.fn(),
  fetchMyWaiverBids: vi.fn(),
  previewVoluntaryRelease: vi.fn(),
  applyVoluntaryRelease: vi.fn(),
  createTradeProposal: vi.fn(),
  fetchTradeProposals: vi.fn(),
  fetchTradeProposal: vi.fn(),
  cancelTradeProposal: vi.fn(),
  acceptTradeProposal: vi.fn(),
  rejectTradeProposal: vi.fn(),
  counterTradeProposal: vi.fn(),
  approveTradeProposal: vi.fn(),
  rejectTradeProposalAsAdmin: vi.fn(),
  fetchMarketHistory: vi.fn(),
}));

function renderRoute(path: string) {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, { children: createElement(AppRoutes) }),
    }),
  );
}

describe("WaiverPage — layout demo (EP08-03)", () => {
  it("admin: pannello sessione + offerta svincolati", () => {
    const html = renderRoute("/svincoli?persona=admin&stato=success");
    expect(html).toContain('data-testid="wireframe-region-waiver-admin"');
    expect(html).toContain("Apri svincolati");
    expect(html).toContain('data-testid="wireframe-region-waiver-bid"');
    expect(html).toContain('data-testid="waiver-bid-panel"');
  });

  it("member: solo offerta, nessun pannello admin", () => {
    const html = renderRoute("/svincoli?persona=member&stato=success");
    expect(html).not.toContain('data-testid="wireframe-region-waiver-admin"');
    expect(html).toContain('data-testid="wireframe-region-waiver-bid"');
  });

  it("permessi insufficienti mostra lo stato forbidden", () => {
    const html = renderRoute("/svincoli?persona=member&stato=forbidden");
    expect(html).toContain('data-testid="waiver-forbidden"');
  });
});
