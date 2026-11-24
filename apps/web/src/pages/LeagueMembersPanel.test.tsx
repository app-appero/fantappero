import type { LeagueMember } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "../router/simpleRouter";
import { LeagueMembersPanel } from "./LeagueMembersPanel";

const fetchLeagueMembersMock = vi.fn();
const fetchManagerDirectoryMock = vi.fn();

// Solo per la finestra «Sostituisci» (fuori demo): i test in demo non chiamano l'API.
vi.mock("../api/leagues", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/leagues")>()),
  fetchLeagueMembers: (...args: unknown[]) => fetchLeagueMembersMock(...args),
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
