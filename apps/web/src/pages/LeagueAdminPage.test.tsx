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
    expect(html).toContain('data-testid="league-admin-form"');
    expect(html).toContain("Preset regolamento");
    expect(html).toContain("Partecipanti");
    expect(html).toContain("Crediti iniziali");
    expect(html).toContain("Salva configurazione");
    expect(html).toContain("Inviti");
    expect(html).toContain("Partecipanti iscritti");
    expect(html).toContain('data-testid="league-members-list"');
    expect(html).toContain("Trasferisci admin");
    expect(html).toContain("Rimuovi");
    expect(html).toContain('data-testid="league-invite-create"');
    expect(html).toContain('data-testid="league-season-panel"');
    expect(html).toContain("Stato e avvio stagione");
    expect(html).toContain("Bozza");
    expect(html).toContain("Apri configurazione");
    expect(html).toContain('data-testid="league-calendar-panel"');
    expect(html).toContain("Calendario scontri diretti");
    expect(html).toContain('data-testid="league-calendar-generate"');
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
    expect(html).toContain("Nessuna transizione disponibile");
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

  it("renders calendar empty state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&calendario=empty");
    expect(html).toContain('data-testid="league-calendar-empty"');
    expect(html).toContain("Nessun calendario");
  });

  it("renders calendar error state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&calendario=error");
    expect(html).toContain('data-testid="league-calendar-error"');
    expect(html).toContain("Calendario non disponibile");
  });

  it("renders calendar loading state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&calendario=loading");
    expect(html).toContain('data-testid="league-calendar-loading"');
    expect(html).toContain("Caricamento calendario");
  });

  it("renders calendar forbidden state", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin&calendario=forbidden");
    expect(html).toContain('data-testid="league-calendar-forbidden"');
    expect(html).toContain("Permessi insufficienti");
  });

  it("renders invite code and link copy CTAs", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('data-testid="league-invite-copy-code"');
    expect(html).toContain('data-testid="league-invite-copy-url"');
    expect(html).toContain("Copia codice");
    expect(html).toContain("Copia link");
  });

  it("renders delete panel for draft leagues", () => {
    const html = renderRoute("/lega/amministrazione?persona=admin");
    expect(html).toContain('data-testid="league-delete-panel"');
    expect(html).toContain("Elimina lega");
  });
});

