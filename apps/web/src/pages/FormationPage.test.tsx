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
  fetchFantasyTurns: vi.fn(),
  fetchFantasyTurn: vi.fn(),
  fetchMyLineup: vi.fn(),
  saveMyLineup: vi.fn(),
  copyPreviousLineupToDraft: vi.fn(),
  saveLineupDraft: vi.fn(),
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

describe("EP06-06 formation page", () => {
  it("renders success demo with module, ordered bench, substitutions, tactical moves, copy and draft", () => {
    const html = renderRoute("/formazione?persona=member&stato=success");
    expect(html).toContain('data-testid="wireframe-formation-success"');
    expect(html).toContain('data-testid="football-pitch"');
    expect(html).toContain('data-testid="formation-module"');
    expect(html).toContain('data-testid="formation-save"');
    expect(html).toContain('data-testid="formation-copy"');
    expect(html).toContain('data-testid="formation-draft"');
    expect(html).toContain('data-testid="formation-previous-hint"');
    expect(html).toContain("Copia formazione precedente");
    expect(html).toContain("Salva bozza");
    expect(html).toContain("rivalidata su rosa e disponibilità");
    expect(html).toContain('data-testid="formation-lock-hint"');
    expect(html).toContain("viene rinviato");
    expect(html).toContain('data-testid="formation-moves"');
    expect(html).toContain('data-testid="formation-moves-hint"');
    expect(html).toContain('data-testid="formation-bench-order"');
    expect(html).toContain('data-testid="formation-sub-hint"');
    expect(html).toContain('data-testid="formation-bench-position-0"');
    expect(html).toContain('data-testid="formation-bench-panchina"');
    expect(html).toContain('data-testid="formation-bench-tribuna"');
    expect(html).toContain("4-3-3");
    expect(html).toContain("Portiere 1 (bloccato)");
    expect(html).toContain("Maignan (bloccato)");
    expect(html).toContain("Meret");
    expect(html).toContain("Acerbi");
    expect(html).toContain("Panchina — massimo 5 subentri");
    expect(html).toContain("può subentrare");
    expect(html).toContain("oltre i 5 cambi");
    expect(html).toContain("Entrano al massimo 5 panchinari");
    expect(html).toContain("Mosse tattiche: 0/3 usate");
    expect(html).toContain("Questo salvataggio non consuma mosse");
    expect(html).toContain("Le sostituzioni automatiche non consumano mosse");
    expect(html).toContain("fa-badge--success");
    expect(html).toContain("fa-badge--warning");
    expect(html).toContain("Partita già iniziata");
    expect(html).toContain("Salva formazione");
    expect(html).toContain('data-testid="formation-starter-0"');
  });

  it("shows empty state", () => {
    const html = renderRoute("/formazione?persona=member&stato=empty");
    expect(html).toContain('data-testid="formation-empty"');
  });

  it("shows error state with retry", () => {
    const html = renderRoute("/formazione?persona=member&stato=error");
    expect(html).toContain('data-testid="formation-error"');
    expect(html).toContain("Riprova");
  });

  it("shows forbidden state", () => {
    const html = renderRoute("/formazione?persona=member&stato=forbidden");
    expect(html).toContain('data-testid="formation-forbidden"');
    expect(html).toContain("Permessi insufficienti");
  });

  it("shows loading state", () => {
    const html = renderRoute("/formazione?persona=member&stato=loading");
    expect(html).toContain('data-testid="formation-loading"');
  });
});

describe("EP-turni-automazione: nessun trigger IA duplicato su Formazione", () => {
  it("non mostra più la card Formazioni IA: la generazione è automatica (cron) o manuale solo dal pannello operatore", () => {
    const html = renderRoute("/formazione?persona=admin&stato=success");
    expect(html).not.toContain('data-testid="formation-ai-admin"');
    expect(html).not.toContain("Formazioni IA");
  });
});
