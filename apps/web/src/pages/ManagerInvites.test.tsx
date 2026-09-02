import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { ManagerDirectory } from "../components/ManagerDirectory";
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
  fetchMyLeagues: vi.fn(),
}));

vi.mock("../api/managerInvites", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/managerInvites")>();
  return {
    ...original,
    fetchManagerDirectory: vi.fn(),
    fetchReceivedNamedInvites: vi.fn(),
    acceptReceivedNamedInvite: vi.fn(),
    declineReceivedNamedInvite: vi.fn(),
  };
});

function renderRoute(path: string) {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, { children: createElement(AppRoutes) }),
    }),
  );
}

function renderDirectory(props: Parameters<typeof ManagerDirectory>[0]) {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: ["/fantallenatori"],
      children: createElement(ManagerDirectory, props),
    }),
  );
}

describe("directory fantallenatori", () => {
  it("mostra persone, AI e stati di invito nella demo", () => {
    const html = renderDirectory({
      leagueId: "demo-league",
      isDemoMode: true,
      search: "",
    });
    expect(html).toContain('data-testid="manager-directory-list"');
    expect(html).toContain("Lucia Bianchi");
    expect(html).toContain("Manuale");
    expect(html).toContain("IA");
    expect(html).toContain("Indisponibile");
    expect(html).toContain("Già invitato");
  });

  it("mostra lo stato errore e permessi insufficienti", () => {
    const error = renderDirectory({ isDemoMode: true, search: "?directory=error" });
    const forbidden = renderDirectory({
      isDemoMode: true,
      search: "?directory=forbidden",
    });
    expect(error).toContain('data-testid="manager-directory-error"');
    expect(forbidden).toContain("Non hai i permessi");
  });

  it("copre gli stati vuoto e capienza", () => {
    const empty = renderDirectory({ isDemoMode: true, search: "?directory=empty" });
    const capacity = renderDirectory({
      leagueId: "demo-league",
      isDemoMode: true,
      search: "?directory=capacity",
    });
    expect(empty).toContain('data-testid="manager-directory-empty"');
    expect(capacity).toContain('data-testid="manager-directory-capacity"');
  });
});

describe("inviti nominativi ricevuti", () => {
  it("espone azioni Accetta e Rifiuta", () => {
    const html = renderRoute("/inviti?persona=member");
    expect(html).toContain('data-testid="received-invites-list"');
    expect(html).toContain("Accetta");
    expect(html).toContain("Rifiuta");
  });

  it("mostra lo stato forbidden demo", () => {
    const html = renderRoute("/inviti?persona=member&invitiRicevuti=forbidden");
    expect(html).toContain('data-testid="received-invites-error"');
    expect(html).toContain("Non hai i permessi");
  });
});
