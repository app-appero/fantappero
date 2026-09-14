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
  fetchLeague: vi.fn(),
  fetchLeagueMembersPublic: vi.fn(),
  fetchLeagueCalendar: vi.fn(),
  deleteLeague: vi.fn(),
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

describe("EP03-02 league admin page", () => {
  it("renders positive flow in demo admin mode", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('data-testid="league-admin-setup"');
    expect(html).toContain('data-testid="league-admin-form"');
    expect(html).toContain("Preset regolamento");
    expect(html).toContain("Partecipanti");
    expect(html).toContain("Crediti iniziali");
    expect(html).toContain("Salva configurazione");
    expect(html).toContain("Prossime fasi");
    expect(html).toContain('id="tab-configurazione"');
    expect(html).toContain('id="tab-invitati"');
    expect(html).toContain("Invitati");
    // Tab Invitati bloccata finché non si salva: contenuto invitati non montato.
    expect(html).not.toContain('data-testid="league-invite-create"');
    expect(html).not.toContain('data-testid="league-members-list"');
    expect(html).toContain('data-testid="league-season-panel"');
    expect(html).toContain("Stato stagione");
    expect(html).toContain("Prerequisiti mancanti");
    expect(html).toContain("partecipanti → rose → calendario");
    expect(html).toContain('data-testid="league-season-blocker-participant_count_mismatch"');
    expect(html).toContain('data-testid="league-season-blocker-locked-fantasy_teams_not_configured"');
    expect(html).toContain('data-testid="league-season-blocker-locked-calendar_not_configured"');
    expect(html).toContain("Vai ai partecipanti");
    expect(html).not.toContain("Vai a squadre e rose →");
    expect(html).not.toContain("Vai al calendario →");
    expect(html).not.toContain("Inizia la configurazione");
    expect(html).not.toContain("Avvia stagione");
    expect(html).toMatch(/id="tab-invitati"[^>]*disabled/);
  });

  it("renders empty state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&stato=empty");
    expect(html).toContain('data-testid="league-admin-empty"');
    expect(html).toContain("Nessuna lega selezionata");
  });

  it("renders error state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&stato=error");
    expect(html).toContain('data-testid="league-admin-error"');
    expect(html).toContain("Errore di caricamento");
  });

  it("blocks non-admin users", () => {
    const html = renderRoute("/lega/amministrazione?persona=member");
    expect(html).toContain('data-testid="route-forbidden"');
    expect(html).toContain("Permessi insufficienti");
  });

  it("renders empty invite state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&inviti=empty");
    expect(html).toContain('data-testid="league-invites-empty"');
    expect(html).toContain("Nessun invito");
  });

  it("renders invite error state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&inviti=error");
    expect(html).toContain('data-testid="league-invites-error"');
    expect(html).toContain("Inviti non disponibili");
  });

  it("renders empty participant state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&partecipanti=empty");
    expect(html).toContain('data-testid="league-members-empty"');
    expect(html).toContain("Nessun partecipante");
  });

  it("renders participant error state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&partecipanti=error");
    expect(html).toContain('data-testid="league-members-error"');
    expect(html).toContain("Partecipanti non disponibili");
  });

  it("renders participant loading state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&partecipanti=loading");
    expect(html).toContain('data-testid="league-members-loading"');
    expect(html).toContain("Caricamento partecipanti");
  });

  it("renders season empty state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&stagione=empty");
    expect(html).toContain('data-testid="league-season-empty"');
    expect(html).toContain("Nessuna informazione di stagione");
  });

  it("renders season error state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&stagione=error");
    expect(html).toContain('data-testid="league-season-error"');
    expect(html).toContain("Stato stagione non disponibile");
  });

  it("renders season loading state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&stagione=loading");
    expect(html).toContain('data-testid="league-season-loading"');
    expect(html).toContain("Caricamento stato stagione");
  });





  it("keeps invite CTAs behind the locked Invitati tab until configuration is saved", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('id="tab-invitati"');
    expect(html).toMatch(/id="tab-invitati"[^>]*disabled/);
    expect(html).not.toContain('data-testid="league-invite-copy-code"');
    expect(html).not.toContain('data-testid="league-invite-create"');
  });

  it("renders delete panel for draft leagues", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('data-testid="league-delete-panel"');
    expect(html).toContain("Elimina lega");
  });

  it("shows Prossime fasi with Configurazione and locked Invitati tabs", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain("Prossime fasi");
    expect(html).toContain('data-testid="league-admin-setup"');
    expect(html).toContain('id="tab-configurazione"');
    expect(html).toContain('id="tab-invitati"');
    expect(html).toContain("Prima salva la configurazione della lega");
    expect(html).not.toContain('data-testid="league-home-roster-link"');
  });
});


