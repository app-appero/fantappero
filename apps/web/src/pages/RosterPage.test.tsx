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
  fetchLeagueListone: vi.fn(),
  refreshLeagueListone: vi.fn(),
  fetchMyFantasyTeam: vi.fn(),
  fetchFantasyTeams: vi.fn(),
  fetchFantasyTeamForAdmin: vi.fn(),
  fetchRosterOccupancy: vi.fn(),
  ensureFantasyTeams: vi.fn(),
  assignRosterSlot: vi.fn(),
  releaseRosterSlot: vi.fn(),
  fetchMyCredits: vi.fn(),
  fetchMyCreditMovements: vi.fn(),
  fetchFantasyTeamCreditsForAdmin: vi.fn(),
  postAdminCreditMovement: vi.fn(),
  downloadRosterCsvTemplate: vi.fn(),
  previewRosterCsvImport: vi.fn(),
  confirmRosterCsvImport: vi.fn(),
  fetchMyRosterHistory: vi.fn(),
  fetchTeamRosterHistoryForAdmin: vi.fn(),
  fetchMyRosterAsOf: vi.fn(),
  fetchRosterTurnSnapshots: vi.fn(),
  fetchRosterTurnSnapshot: vi.fn(),
  createRosterTurnSnapshot: vi.fn(),
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

describe("EP05-01/02/03 roster, credits and manual assignment", () => {
  it("renders success roster in demo mode", () => {
    const html = renderRoute("/rosa?persona=member&stato=success");
    expect(html).toContain('data-testid="wireframe-roster-success"');
    expect(html).toContain('data-testid="roster-summary"');
    expect(html).toContain('data-testid="roster-composition"');
    expect(html).toContain('data-testid="roster-composition-status"');
    expect(html).toContain("Incompleta");
    expect(html).toContain('data-testid="roster-filled-table"');
    expect(html).toContain('data-testid="roster-filled-table-P"');
    expect(html).toContain('data-testid="roster-filled-table-D"');
    expect(html).toContain('data-testid="roster-filled-table-C"');
    expect(html).toContain('data-testid="roster-filled-table-A"');
    expect(html).toContain("Portieri");
    expect(html).toContain("Difensori");
    expect(html).toContain("Centrocampisti");
    expect(html).toContain("Attaccanti");
    expect(html).toContain('data-testid="roster-credits-balance"');
    expect(html).toContain("Crediti residui");
  });

  it("renders empty roster state", () => {
    const html = renderRoute("/rosa?persona=member&stato=empty");
    expect(html).toContain('data-testid="roster-empty"');
    expect(html).toContain("Rosa vuota");
    expect(html).toContain('data-testid="roster-credits"');
  });

  it("renders error roster state", () => {
    const html = renderRoute("/rosa?persona=member&stato=error");
    expect(html).toContain('data-testid="roster-error"');
    expect(html).toContain("Rosa non disponibile");
  });

  it("renders forbidden roster state", () => {
    const html = renderRoute("/rosa?persona=member&stato=forbidden");
    expect(html).toContain('data-testid="roster-forbidden"');
    expect(html).toContain("Permessi insufficienti");
  });

  it("shows admin ensure, listone assign/remove table and credit adjustment", () => {
    const html = renderRoute("/rosa?persona=admin&stato=success");
    expect(html).toContain('data-testid="roster-admin-tools"');
    expect(html).toContain("Assicura squadre partecipanti");
    expect(html).toContain('data-testid="roster-admin-random-ai"');
    expect(html).toContain("Assegna rosa random (IA)");
    expect(html).toContain('data-testid="roster-admin-manual"');
    expect(html).toContain("Inserimento manuale rose");
    expect(html).toContain('data-testid="roster-admin-team"');
    expect(html).toContain('data-testid="roster-admin-listone-table-all"');
    expect(html).toContain('data-testid="roster-admin-listone-search"');
    expect(html).toContain('data-testid="roster-admin-release-a1"');
    expect(html).toContain('data-testid="roster-admin-assign-a3"');
    expect(html).toContain(">Rimuovi<");
    expect(html).toContain(">Assegna<");
    expect(html).toContain('data-testid="roster-admin-credits"');
    expect(html).toContain("Aggiusta crediti");
    expect(html).not.toContain('data-testid="roster-csv-import"');
    expect(html).not.toContain("Import CSV rose");
    expect(html).not.toContain('data-testid="roster-listone-refresh"');
  });

  it("shows listone for member but hides admin-only tools", () => {
    const html = renderRoute("/rosa?persona=member&stato=success");
    expect(html).toContain('data-testid="roster-admin-manual"');
    expect(html).toContain('data-testid="roster-admin-listone-table-all"');
    expect(html).toContain('data-testid="roster-admin-listone-search"');
    expect(html).toContain('data-testid="roster-admin-assign-a3"');
    expect(html).toContain('data-testid="roster-admin-release-a1"');
    expect(html).not.toContain('data-testid="roster-listone-refresh"');
    expect(html).not.toContain('data-testid="roster-admin-tools"');
    expect(html).not.toContain('data-testid="roster-admin-credits"');
    expect(html).not.toContain('data-testid="roster-admin-team"');
    expect(html).not.toContain('data-testid="roster-csv-import"');
    expect(html).not.toContain("Assicura squadre partecipanti");
    expect(html).not.toContain("Aggiusta crediti");
  });

  it("renders roster history success in demo mode", () => {
    const html = renderRoute("/rosa?persona=member&stato=success&sezione=storico");
    expect(html).toContain('data-testid="roster-section-tabs"');
    expect(html).toContain('data-testid="roster-history"');
    expect(html).toContain('data-testid="roster-history-success"');
    expect(html).toContain("Intervalli di possesso");
    expect(html).toContain('data-testid="roster-snapshots"');
    expect(html).toContain('data-testid="roster-snapshot-detail"');
    expect(html).not.toContain('data-testid="roster-snapshot-create"');
  });

  it("renders empty roster history in demo mode", () => {
    const html = renderRoute("/rosa?persona=member&stato=empty&sezione=storico");
    expect(html).toContain('data-testid="roster-history-empty"');
    expect(html).toContain("Nessun possesso registrato");
    expect(html).toContain('data-testid="roster-snapshot-empty"');
  });

  it("keeps forbidden state without history panel", () => {
    const html = renderRoute("/rosa?persona=member&stato=forbidden&sezione=storico");
    expect(html).toContain('data-testid="roster-forbidden"');
    expect(html).not.toContain('data-testid="roster-history"');
  });

  it("shows admin snapshot create control in history section", () => {
    const html = renderRoute("/rosa?persona=admin&stato=success&sezione=storico");
    expect(html).toContain('data-testid="roster-snapshot-create"');
    expect(html).toContain("Crea snapshot turno");
  });
});
