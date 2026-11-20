import type { FantasyCoachDirectoryItem } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import {
  createNamedLeagueInvite,
  fetchManagerDirectory,
  revokeNamedLeagueInvite,
} from "../api/managerInvites";
import { AuthProvider } from "../auth/AuthContext";
import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
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
    createNamedLeagueInvite: vi.fn(),
    revokeNamedLeagueInvite: vi.fn(),
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
    expect(html).toContain("fa-manager-directory__title");
    expect(html).toContain("fa-manager-directory__intro");
    expect(html).toContain("Manuale");
    expect(html).toContain("IA");
    expect(html).toContain("Indisponibile");
    expect(html).toContain("Già invitato");
  });

  it("la ricerca non promette più la ricerca per email", () => {
    const html = renderDirectory({
      leagueId: "demo-league",
      isDemoMode: true,
      search: "",
    });
    expect(html).toContain("Cerca per nome o nickname");
    expect(html).not.toMatch(/Cerca per[^<]*email/);
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
    expect(capacity).toContain("Lega al completo");
    expect(capacity).toContain('data-testid="manager-directory-list"');
    expect(capacity).not.toContain('data-testid="manager-directory-error"');
    expect(capacity).not.toContain("Directory non disponibile");
  });

  it("a lega piena mostra l'avviso e tiene visibile la directory", () => {
    const html = renderDirectory({
      leagueId: "demo-league",
      isDemoMode: true,
      search: "",
      memberCount: 8,
      participantCount: 8,
    });
    expect(html).toContain('data-testid="manager-directory-capacity"');
    expect(html).toContain("Lega al completo");
    expect(html).toContain('data-testid="manager-directory-list"');
    expect(html).not.toContain("Directory non disponibile");
    expect(html).toContain("Invita");
  });

  it("tiene invitabile chi risulta accettato ma non è più in lega e ricarica senza refresh", async () => {
    const accepted: FantasyCoachDirectoryItem = {
      userId: "user-accepted",
      displayName: "Rosario Trotta",
      avatarUrl: null,
      userType: "human",
      availableForInvites: true,
      namedInviteStatus: "accepted",
      memberSince: "10/2026",
      concludedLeagues: 0,
      bestPosition: null,
      historySummary: "Nessuna lega conclusa",
    };
    vi.mocked(fetchManagerDirectory).mockResolvedValue({
      items: [accepted],
      page: 1,
      pageSize: 12,
      total: 1,
      totalPages: 1,
    });
    saveStoredSession({
      accessToken: "token-admin",
      refreshToken: "refresh-admin",
      user: { id: "admin-1", displayName: "Admin", globalRole: "member" },
    });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root: Root = createRoot(host);
    function renderDirectoryTree(reloadToken: number) {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(ManagerDirectory, {
            leagueId: "league-1",
            isDemoMode: false,
            reloadToken,
          }),
        }),
      );
    }
    await act(async () => {
      renderDirectoryTree(0);
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    const button = host.querySelector('[data-testid="manager-invite-user-accepted"]');
    expect(button?.textContent).toBe("Invita");
    expect(button?.hasAttribute("disabled")).toBe(false);
    expect(host.textContent).not.toContain("Aggiunto");

    await act(async () => {
      renderDirectoryTree(1);
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(vi.mocked(fetchManagerDirectory).mock.calls.length).toBeGreaterThanOrEqual(2);

    act(() => {
      root.unmount();
    });
    host.remove();
    clearStoredSession();
  });

  it("disabilita l'invito per chi è già in lega", async () => {
    const member: FantasyCoachDirectoryItem = {
      userId: "user-member",
      displayName: "Già Iscritto",
      avatarUrl: null,
      userType: "human",
      availableForInvites: false,
      inLeague: true,
      namedInviteStatus: null,
      memberSince: "10/2026",
      concludedLeagues: 0,
      bestPosition: null,
      historySummary: "Nessuna lega conclusa",
    };
    vi.mocked(fetchManagerDirectory).mockResolvedValue({
      items: [member],
      page: 1,
      pageSize: 12,
      total: 1,
      totalPages: 1,
    });
    saveStoredSession({
      accessToken: "token-admin",
      refreshToken: "refresh-admin",
      user: { id: "admin-1", displayName: "Admin", globalRole: "member" },
    });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root: Root = createRoot(host);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(ManagerDirectory, {
            leagueId: "league-1",
            isDemoMode: false,
          }),
        }),
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    const button = host.querySelector('[data-testid="manager-invite-user-member"]');
    expect(button?.textContent).toBe("Già in lega");
    expect(button?.hasAttribute("disabled")).toBe(true);
    act(() => {
      root.unmount();
    });
    host.remove();
    clearStoredSession();
  });
});

describe("annulla invito nominativo", () => {
  const pending: FantasyCoachDirectoryItem = {
    userId: "user-pending",
    displayName: "Pina Pendente",
    avatarUrl: null,
    userType: "human",
    availableForInvites: true,
    namedInviteStatus: "pending",
    namedInviteId: "invite-1",
    memberSince: "10/2026",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  };

  function page(items: FantasyCoachDirectoryItem[]) {
    return { items, page: 1, pageSize: 10, total: items.length, totalPages: 1 };
  }

  async function mountDirectory() {
    saveStoredSession({
      accessToken: "token-admin",
      refreshToken: "refresh-admin",
      user: { id: "admin-1", displayName: "Admin", globalRole: "member" },
    });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root: Root = createRoot(host);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(ManagerDirectory, {
            leagueId: "league-1",
            isDemoMode: false,
          }),
        }),
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    return {
      host,
      cleanup() {
        act(() => {
          root.unmount();
        });
        host.remove();
        clearStoredSession();
      },
    };
  }

  async function click(element: Element | null) {
    expect(element).not.toBeNull();
    await act(async () => {
      (element as HTMLElement).click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it("chiede conferma, revoca l'invito e riporta la riga su «Invita»", async () => {
    vi.mocked(fetchManagerDirectory).mockReset();
    vi.mocked(revokeNamedLeagueInvite).mockReset();
    vi.mocked(fetchManagerDirectory)
      .mockResolvedValueOnce(page([pending]))
      .mockResolvedValue(
        page([{ ...pending, namedInviteStatus: "revoked", namedInviteId: "invite-1" }]),
      );
    vi.mocked(revokeNamedLeagueInvite).mockResolvedValue({
      id: "invite-1",
      leagueId: "league-1",
      leagueName: "Lega Test",
      recipientUserId: "user-pending",
      recipientDisplayName: "Pina Pendente",
      recipientUserType: "human",
      status: "revoked",
      expiresAt: "2026-12-01T00:00:00Z",
      respondedAt: null,
      createdAt: "2026-11-19T00:00:00Z",
      autoAccepted: false,
    });
    const { host, cleanup } = await mountDirectory();

    const invite = host.querySelector('[data-testid="manager-invite-user-pending"]');
    expect(invite?.textContent).toBe("Già invitato");
    expect(invite?.hasAttribute("disabled")).toBe(true);
    const revoke = host.querySelector('[data-testid="manager-revoke-user-pending"]');
    expect(revoke?.textContent).toBe("Annulla invito");

    // Primo click: solo la finestra di conferma, nessuna chiamata.
    await click(revoke);
    expect(host.querySelector('[data-testid="manager-revoke-dialog"]')?.textContent).toContain(
      "Pina Pendente",
    );
    expect(revokeNamedLeagueInvite).not.toHaveBeenCalled();

    await click(host.querySelector('[data-testid="manager-revoke-confirm"]'));
    expect(revokeNamedLeagueInvite).toHaveBeenCalledTimes(1);
    expect(revokeNamedLeagueInvite).toHaveBeenCalledWith("token-admin", "league-1", "invite-1");
    expect(vi.mocked(fetchManagerDirectory).mock.calls.length).toBe(2);
    expect(host.querySelector('[data-testid="manager-revoke-dialog"]')).toBeNull();

    const after = host.querySelector('[data-testid="manager-invite-user-pending"]');
    expect(after?.textContent).toBe("Invita");
    expect(after?.hasAttribute("disabled")).toBe(false);
    expect(host.querySelector('[data-testid="manager-revoke-user-pending"]')).toBeNull();
    expect(host.querySelector('[data-testid="manager-directory-success"]')?.textContent).toContain(
      "Invito annullato",
    );
    cleanup();
  });

  it("chiudendo la conferma non revoca nulla", async () => {
    vi.mocked(fetchManagerDirectory).mockReset();
    vi.mocked(revokeNamedLeagueInvite).mockReset();
    vi.mocked(fetchManagerDirectory).mockResolvedValue(page([pending]));
    const { host, cleanup } = await mountDirectory();

    await click(host.querySelector('[data-testid="manager-revoke-user-pending"]'));
    await click(host.querySelector('[data-testid="manager-revoke-cancel"]'));
    expect(host.querySelector('[data-testid="manager-revoke-dialog"]')).toBeNull();
    expect(revokeNamedLeagueInvite).not.toHaveBeenCalled();
    expect(host.querySelector('[data-testid="manager-invite-user-pending"]')?.textContent).toBe(
      "Già invitato",
    );
    cleanup();
  });

  it("mostra l'errore se l'invito non è più annullabile", async () => {
    vi.mocked(fetchManagerDirectory).mockReset();
    vi.mocked(revokeNamedLeagueInvite).mockReset();
    vi.mocked(fetchManagerDirectory).mockResolvedValue(page([pending]));
    vi.mocked(revokeNamedLeagueInvite).mockRejectedValue(
      new ApiError("L'invito non è più revocabile.", 400, "named_invite_not_pending"),
    );
    const { host, cleanup } = await mountDirectory();

    await click(host.querySelector('[data-testid="manager-revoke-user-pending"]'));
    await click(host.querySelector('[data-testid="manager-revoke-confirm"]'));
    expect(revokeNamedLeagueInvite).toHaveBeenCalledTimes(1);
    expect(
      host.querySelector('[data-testid="manager-directory-revoke-error"]')?.textContent,
    ).toContain("non è più annullabile");
    expect(host.querySelector('[data-testid="manager-directory-success"]')).toBeNull();
    cleanup();
  });

  it("dopo «Invito già inviato» ricarica la directory: la riga non offre più «Invita»", async () => {
    vi.mocked(fetchManagerDirectory).mockReset();
    vi.mocked(createNamedLeagueInvite).mockReset();
    // La directory caricata prima che un altro admin (o un'altra scheda) invitasse Pina.
    vi.mocked(fetchManagerDirectory)
      .mockResolvedValueOnce(page([{ ...pending, namedInviteStatus: null, namedInviteId: null }]))
      .mockResolvedValue(page([pending]));
    vi.mocked(createNamedLeagueInvite).mockRejectedValue(
      new ApiError("Invito già inviato.", 400, "named_invite_already_pending"),
    );
    const { host, cleanup } = await mountDirectory();

    const invite = host.querySelector('[data-testid="manager-invite-user-pending"]');
    expect(invite?.textContent).toBe("Invita");
    await click(invite);
    expect(createNamedLeagueInvite).toHaveBeenCalledWith("token-admin", "league-1", "user-pending");
    expect(vi.mocked(fetchManagerDirectory).mock.calls.length).toBe(2);

    const after = host.querySelector('[data-testid="manager-invite-user-pending"]');
    expect(after?.textContent).toBe("Già invitato");
    expect(after?.hasAttribute("disabled")).toBe(true);
    expect(host.querySelector('[data-testid="manager-revoke-user-pending"]')?.textContent).toBe(
      "Annulla invito",
    );
    expect(
      host.querySelector('[data-testid="manager-directory-invite-error"]')?.textContent,
    ).toContain("Hai già invitato questo fantallenatore.");
    cleanup();
  });

  it("senza id invito (backend precedente) resta solo «Già invitato»", async () => {
    vi.mocked(fetchManagerDirectory).mockReset();
    vi.mocked(fetchManagerDirectory).mockResolvedValue(
      page([{ ...pending, namedInviteId: undefined }]),
    );
    const { host, cleanup } = await mountDirectory();

    expect(host.querySelector('[data-testid="manager-invite-user-pending"]')?.textContent).toBe(
      "Già invitato",
    );
    expect(host.querySelector('[data-testid="manager-revoke-user-pending"]')).toBeNull();
    cleanup();
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
