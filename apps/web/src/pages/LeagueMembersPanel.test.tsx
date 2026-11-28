import type { LeagueMember } from "@fantappero/contracts";
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "../router/simpleRouter";
import { LeagueMembersPanel } from "./LeagueMembersPanel";

const fetchLeagueMembersMock = vi.fn();
const fetchManagerDirectoryMock = vi.fn();
const removeLeagueMemberMock = vi.fn();
const revokeLeagueAdminMock = vi.fn();
const ensureFantasyTeamsMock = vi.fn();
const assignRandomAiRosterMock = vi.fn();

// Per la finestra «Sostituisci» e per «Rimuovi» (fuori demo): niente chiamate vere all'API.
vi.mock("../api/leagues", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/leagues")>()),
  fetchLeagueMembers: (...args: unknown[]) => fetchLeagueMembersMock(...args),
  removeLeagueMember: (...args: unknown[]) => removeLeagueMemberMock(...args),
  revokeLeagueAdmin: (...args: unknown[]) => revokeLeagueAdminMock(...args),
  ensureFantasyTeams: (...args: unknown[]) => ensureFantasyTeamsMock(...args),
  assignRandomAiRoster: (...args: unknown[]) => assignRandomAiRosterMock(...args),
}));
vi.mock("../api/managerInvites", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/managerInvites")>()),
  fetchManagerDirectory: (...args: unknown[]) => fetchManagerDirectoryMock(...args),
}));
vi.mock("../auth/sessionStorage", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../auth/sessionStorage")>()),
  loadStoredSession: () => ({ accessToken: "token-admin", refreshToken: "refresh-admin" }),
}));

// Il pannello legge solo l'utente corrente: niente AuthProvider completo.
vi.mock("../auth/AuthContext", async (importOriginal) => {
  const original = await importOriginal<typeof import("../auth/AuthContext")>();
  return {
    ...original,
    useAuth: () => ({ user: { id: "demo-admin", displayName: "Marco", globalRole: "member" } }),
  };
});

/** In demo il pannello mostra 3 iscritti (admin, una persona, un'IA). */
function renderPanel(props: {
  participantCount: number;
  participantMin?: number | null;
  pendingInviteCount?: number;
}) {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: ["/lega/amministrazione"],
      children: createElement(LeagueMembersPanel, {
        leagueId: "demo-league",
        isDemoMode: true,
        search: "",
        ...props,
      }),
    }),
  );
}

function mismatchMessage(html: string): string {
  const host = document.createElement("div");
  host.innerHTML = html;
  const panel = host.querySelector('[data-testid="league-members-mismatch"]');
  expect(panel).not.toBeNull();
  return panel?.textContent ?? "";
}

describe("LeagueMembersPanel — numero partecipanti non allineato", () => {
  it("sotto il minimo non suggerisce di abbassare «Partecipanti»", () => {
    // 3 iscritti, minimo 4: il server rifiuterebbe 3 con invalid_participant_count.
    const message = mismatchMessage(renderPanel({ participantCount: 4, participantMin: 4 }));
    expect(message).toContain("Serve ancora 1 iscritto.");
    expect(message).not.toContain("abbassa");
  });

  it("da due iscritti mancanti in su resta il plurale (QA notturna 23→24/11)", () => {
    const message = mismatchMessage(renderPanel({ participantCount: 5, participantMin: 5 }));
    expect(message).toContain("Servono ancora 2 iscritti.");
  });

  it("dal minimo in su propone ancora di abbassare agli iscritti", () => {
    const atMin = mismatchMessage(renderPanel({ participantCount: 6, participantMin: 3 }));
    expect(atMin).toContain(
      "Servono ancora 3 iscritti, oppure abbassa «Partecipanti» nel regolamento a 3 e salva.",
    );
    const aboveMin = mismatchMessage(renderPanel({ participantCount: 6, participantMin: 2 }));
    expect(aboveMin).toContain("abbassa «Partecipanti» nel regolamento a 3");
  });

  it("senza minimo noto resta il comportamento di prima", () => {
    for (const html of [
      renderPanel({ participantCount: 4 }),
      renderPanel({ participantCount: 4, participantMin: null }),
    ]) {
      expect(mismatchMessage(html)).toContain(
        "Serve ancora 1 iscritto, oppure abbassa «Partecipanti» nel regolamento a 3 e salva.",
      );
    }
  });

  it("con più iscritti del previsto il messaggio non cambia", () => {
    const message = mismatchMessage(renderPanel({ participantCount: 2, participantMin: 4 }));
    expect(message).toContain("Ci sono più iscritti del previsto: alza «Partecipanti» a 3");
  });

  it("con iscritti allineati non mostra l'avviso", () => {
    const html = renderPanel({ participantCount: 3, participantMin: 4 });
    expect(html).not.toContain('data-testid="league-members-mismatch"');
    expect(html).toContain('data-testid="league-members-capacity"');
  });
});

describe("LeagueMembersPanel — inviti nominativi in attesa (Rosario, 20/11)", () => {
  function capacityText(html: string): string {
    const host = document.createElement("div");
    host.innerHTML = html;
    return host.querySelector('[data-testid="league-members-capacity"]')?.textContent ?? "";
  }

  it("accanto al conto degli iscritti mostra gli inviti in attesa, solo se ci sono", () => {
    expect(capacityText(renderPanel({ participantCount: 4, pendingInviteCount: 1 }))).toBe(
      "Iscritti: 3 / Previsti: 4 · 1 invito in attesa",
    );
    expect(capacityText(renderPanel({ participantCount: 5, pendingInviteCount: 2 }))).toBe(
      "Iscritti: 3 / Previsti: 5 · 2 inviti in attesa",
    );
    expect(capacityText(renderPanel({ participantCount: 4 }))).toBe("Iscritti: 3 / Previsti: 4");
    expect(capacityText(renderPanel({ participantCount: 4, pendingInviteCount: 0 }))).toBe(
      "Iscritti: 3 / Previsti: 4",
    );
  });
});

describe("LeagueMembersPanel — Sostituisci, «2. Chi vuoi mettere» (QA 21/11)", () => {
  const MEMBERS: LeagueMember[] = [
    {
      userId: "admin-1",
      displayName: "Marco",
      email: "marco@example.com",
      userType: "human",
      role: "league_admin",
      joinedAt: "2026-08-01T10:00:00Z",
    },
    {
      userId: "member-1",
      displayName: "Giulia",
      email: "giulia@example.com",
      userType: "human",
      role: "member",
      joinedAt: "2026-08-02T10:00:00Z",
    },
  ];
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    fetchLeagueMembersMock.mockReset().mockResolvedValue(MEMBERS);
    fetchManagerDirectoryMock
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 8 });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("la ricerca dice «Cerca per nome o nickname», come la directory: l'email non si cerca più", async () => {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(LeagueMembersPanel, {
            leagueId: "league-1",
            isDemoMode: false,
            search: "",
          }),
        }),
      );
    });
    const open = container.querySelector<HTMLButtonElement>(
      '[data-testid="league-members-replace-open"]',
    );
    expect(open?.disabled).toBe(false);
    await act(async () => {
      open?.click();
    });

    const panel = container.querySelector('[data-testid="league-members-replace-panel"]');
    expect(panel).not.toBeNull();
    const input = panel?.querySelector<HTMLInputElement>('input[name="replace-coach-query"]');
    expect(input).not.toBeNull();
    const label = panel?.querySelector(`label[for="${input?.id}"]`);
    expect(label?.textContent).toBe("Cerca per nome o nickname");
    expect(panel?.textContent).not.toMatch(/email/i);

    // Il campo cerca nella directory dei fantallenatori (nome e nickname), come la pagina.
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setter?.call(input, "giul");
      input?.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 300));
    });
    expect(fetchManagerDirectoryMock).toHaveBeenLastCalledWith(
      "token-admin",
      "league-1",
      expect.objectContaining({ query: "giul", available: true }),
    );
  });
});

describe("LeagueMembersPanel — «Rimuovi»: «allineato agli iscritti» solo se i previsti cambiano (QA 28/11, D1)", () => {
  function makeMember(index: number): LeagueMember {
    return {
      userId: `member-${index}`,
      displayName: `Fantallenatore ${index}`,
      email: `f${index}@example.com`,
      userType: "human",
      role: "member",
      joinedAt: "2026-08-02T10:00:00Z",
    };
  }
  const ADMIN: LeagueMember = {
    userId: "admin-1",
    displayName: "Marco",
    email: "marco@example.com",
    userType: "human",
    role: "league_admin",
    joinedAt: "2026-08-01T10:00:00Z",
  };
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function click(id: string) {
    const element = byTestId(id);
    expect(element, id).not.toBeNull();
    await act(async () => {
      element!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
  }

  async function renderWith(memberCount: number, participantCount: number) {
    const members = [ADMIN, ...Array.from({ length: memberCount - 1 }, (_, i) => makeMember(i + 1))];
    fetchLeagueMembersMock.mockReset().mockResolvedValue(members);
    removeLeagueMemberMock.mockReset().mockImplementation(async (_token: string, _league: string, userId: string) =>
      members.find((member) => member.userId === userId),
    );
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(LeagueMembersPanel, {
            leagueId: "league-1",
            isDemoMode: false,
            search: "",
            participantCount,
            participantMin: 4,
          }),
        }),
      );
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("4 previsti e 3 iscritti: la conferma e l'esito dicono che i previsti restano 4", async () => {
    await renderWith(3, 4);
    expect(byTestId("league-members-capacity")?.textContent).toBe("Iscritti: 3 / Previsti: 4");

    await click("league-member-remove-member-1");
    const dialog = byTestId("league-members-remove-dialog")?.textContent ?? "";
    expect(dialog).toBe("Vuoi rimuovere Fantallenatore 1 dalla lega? I partecipanti previsti restano 4.");
    expect(dialog).not.toContain("allinea");

    await click("league-members-remove-confirm");
    expect(removeLeagueMemberMock).toHaveBeenCalledWith("token-admin", "league-1", "member-1");
    const success = byTestId("league-members-success")?.textContent ?? "";
    expect(success).toContain("Fantallenatore 1 è stato rimosso dalla lega. I partecipanti previsti restano 4.");
    expect(success).not.toContain("allineato agli iscritti");
    // A schermo i previsti sono ancora 4 (il server non li ha toccati), gli iscritti 2.
    expect(byTestId("league-members-capacity")?.textContent).toBe("Iscritti: 2 / Previsti: 4");
  });

  it("8 previsti e 6 iscritti: restano 5 iscritti, la conferma e l'esito dicono che i previsti si allineano", async () => {
    await renderWith(6, 8);

    await click("league-member-remove-member-1");
    expect(byTestId("league-members-remove-dialog")?.textContent).toBe(
      "Vuoi rimuovere Fantallenatore 1 dalla lega? Il numero dei partecipanti previsti si allinea agli iscritti rimasti.",
    );

    await click("league-members-remove-confirm");
    expect(byTestId("league-members-success")?.textContent).toContain(
      "Fantallenatore 1 è stato rimosso dalla lega. Il numero partecipanti previsti è stato allineato agli iscritti (5).",
    );
  });

  it("previsti non noti: nessuna frase sui previsti", async () => {
    const members = [ADMIN, makeMember(1), makeMember(2), makeMember(3), makeMember(4)];
    fetchLeagueMembersMock.mockReset().mockResolvedValue(members);
    removeLeagueMemberMock.mockReset().mockResolvedValue(members[1]);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(LeagueMembersPanel, {
            leagueId: "league-1",
            isDemoMode: false,
            search: "",
          }),
        }),
      );
    });
    await click("league-member-remove-member-1");
    expect(byTestId("league-members-remove-dialog")?.textContent).toBe(
      "Vuoi rimuovere Fantallenatore 1 dalla lega?",
    );
    await click("league-members-remove-confirm");
    expect(byTestId("league-members-success")?.textContent).toContain(
      "Fantallenatore 1 è stato rimosso dalla lega.",
    );
  });
});

describe("LeagueMembersPanel — il messaggio di esito resta dopo il ricaricamento del genitore (QA 28/11, N3)", () => {
  const ADMIN: LeagueMember = {
    userId: "demo-admin",
    displayName: "Marco",
    email: "marco@example.com",
    userType: "human",
    role: "league_admin",
    joinedAt: "2026-08-01T10:00:00Z",
  };
  const CO_ADMIN: LeagueMember = {
    userId: "admin-2",
    displayName: "Elena",
    email: "elena@example.com",
    userType: "human",
    role: "league_admin",
    joinedAt: "2026-08-01T11:00:00Z",
  };
  const MEMBER_1: LeagueMember = {
    userId: "member-1",
    displayName: "Giulia",
    email: "giulia@example.com",
    userType: "human",
    role: "member",
    joinedAt: "2026-08-02T10:00:00Z",
  };
  const MEMBER_2: LeagueMember = {
    userId: "member-2",
    displayName: "Paolo",
    email: "paolo@example.com",
    userType: "human",
    role: "member",
    joinedAt: "2026-08-03T10:00:00Z",
  };
  const AI_MEMBER: LeagueMember = {
    userId: "ai-1",
    displayName: "Allenatore IA 01",
    email: "ia-01@example.com",
    userType: "ai",
    role: "member",
    joinedAt: "2026-08-04T10:00:00Z",
  };
  let container: HTMLDivElement;
  let root: Root;
  let current: LeagueMember[];

  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function flush() {
    for (let i = 0; i < 4; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }

  async function click(id: string) {
    const element = byTestId(id);
    expect(element, id).not.toBeNull();
    await act(async () => {
      element!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await flush();
  }

  /** Come LeagueAdminPage: ogni cambio riuscito (o richiesto da fuori) cambia `reloadToken`. */
  function ReloadingHost() {
    const [reloadToken, setReloadToken] = useState(0);
    return createElement(
      "div",
      null,
      createElement(
        "button",
        {
          type: "button",
          "data-testid": "host-external-reload",
          onClick: () => setReloadToken((value) => value + 1),
        },
        "Ricarica da fuori",
      ),
      createElement(LeagueMembersPanel, {
        leagueId: "league-1",
        isDemoMode: false,
        search: "",
        participantCount: 8,
        participantMin: 4,
        reloadToken,
        onMembersChanged: () => setReloadToken((value) => value + 1),
      }),
    );
  }

  beforeEach(async () => {
    current = [ADMIN, CO_ADMIN, MEMBER_1, MEMBER_2, AI_MEMBER];
    ensureFantasyTeamsMock.mockReset().mockResolvedValue({ teams: [{ id: "team-ai", userId: "ai-1" }] });
    assignRandomAiRosterMock.mockReset().mockResolvedValue({ filledSlots: 35, rosterSize: 35 });
    fetchLeagueMembersMock.mockReset().mockImplementation(async () => [...current]);
    removeLeagueMemberMock.mockReset().mockImplementation(async (_token: string, _league: string, userId: string) => {
      const removed = current.find((member) => member.userId === userId);
      current = current.filter((member) => member.userId !== userId);
      return removed;
    });
    revokeLeagueAdminMock.mockReset().mockImplementation(async (_token: string, _league: string, userId: string) => {
      current = current.map((member) =>
        member.userId === userId ? { ...member, role: "member" as const } : member,
      );
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(ReloadingHost),
        }),
      );
    });
    await flush();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("«Rimuovi»: «… è stato rimosso dalla lega» resta a schermo dopo che il genitore ricarica gli iscritti", async () => {
    expect(fetchLeagueMembersMock).toHaveBeenCalledTimes(1);

    await click("league-member-remove-member-1");
    await click("league-members-remove-confirm");

    expect(removeLeagueMemberMock).toHaveBeenCalledWith("token-admin", "league-1", "member-1");
    // Il genitore ha ricaricato davvero gli iscritti (secondo giro) e l'elenco è aggiornato...
    expect(fetchLeagueMembersMock.mock.calls.length).toBeGreaterThan(1);
    expect(byTestId("league-member-remove-member-1")).toBeNull();
    // ...ma l'esito non si è cancellato.
    expect(byTestId("league-members-success")?.textContent).toContain(
      "Giulia è stato rimosso dalla lega.",
    );

    // Il consenso a tenerlo valeva per quel solo ricaricamento: uno successivo, chiesto da
    // fuori, lo toglie.
    await click("host-external-reload");
    expect(byTestId("league-members-success")).toBeNull();
  });

  it("«Amministratori»: «… non è più amministratore» resta a schermo dopo il ricaricamento", async () => {
    await click("league-members-admin-open");
    await click("league-members-admin-revoke-admin-2");

    expect(revokeLeagueAdminMock).toHaveBeenCalledWith("token-admin", "league-1", "admin-2");
    expect(fetchLeagueMembersMock.mock.calls.length).toBeGreaterThan(1);
    expect(byTestId("league-members-success")?.textContent).toContain(
      "Elena non è più amministratore.",
    );
  });

  it("un ricaricamento chiesto da fuori azzera ancora il messaggio", async () => {
    // «Assegna rosa random» mostra un esito senza chiedere il ricaricamento al genitore.
    await click("league-members-random-ai-ai-1");
    expect(byTestId("league-members-success")?.textContent).toContain(
      "Rosa random assegnata a Allenatore IA 01: 35/35 giocatori.",
    );
    const callsAfterAction = fetchLeagueMembersMock.mock.calls.length;

    // Una nuova iscrizione o un invito dalla directory: cambia `reloadToken` senza che sia
    // un'azione del pannello, quindi l'esito vecchio non ha più motivo di restare.
    await click("host-external-reload");

    expect(fetchLeagueMembersMock.mock.calls.length).toBeGreaterThan(callsAfterAction);
    expect(byTestId("league-members-success")).toBeNull();
  });
});
