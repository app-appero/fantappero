import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "../router/simpleRouter";
import { LeagueMembersPanel } from "./LeagueMembersPanel";

// Il pannello legge solo l'utente corrente: niente AuthProvider completo.
vi.mock("../auth/AuthContext", async (importOriginal) => {
  const original = await importOriginal<typeof import("../auth/AuthContext")>();
  return {
    ...original,
    useAuth: () => ({ user: { id: "demo-admin", displayName: "Marco", globalRole: "member" } }),
  };
});

/**
 * «Rimuovi partecipante» chiede «Sei sicuro?» con il nome (Rosario 24/11, release 1.5).
 * In demo i partecipanti sono Marco (admin), Giulia (persona) e un'IA; la rimozione è locale.
 */
describe("LeagueMembersPanel — «Rimuovi» chiede conferma (1.5)", () => {
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

  beforeEach(async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(LeagueMembersPanel, {
            leagueId: "demo-league",
            isDemoMode: true,
            search: "",
            participantCount: 3,
          }),
        }),
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("il tocco su «Rimuovi» non rimuove: apre «Sei sicuro?» con il nome", async () => {
    expect(byTestId("league-members-remove-dialog")).toBeNull();
    await click("league-member-remove-demo-member-1");

    expect(container.querySelector('[role="dialog"]')?.textContent).toContain("Sei sicuro?");
    expect(byTestId("league-members-remove-dialog")?.textContent).toContain(
      "Vuoi rimuovere Giulia dalla lega?",
    );
    expect(byTestId("league-members-remove-confirm")?.textContent).toBe("Rimuovi");
    expect(byTestId("league-members-remove-cancel")?.textContent).toBe("Annulla");
    // Giulia è ancora in lista e nessuna rimozione è partita.
    expect(byTestId("league-members-list")?.textContent).toContain("Giulia");
    expect(byTestId("league-members-success")).toBeNull();
  });

  it("«Annulla» chiude la finestra e lascia il partecipante", async () => {
    await click("league-member-remove-demo-member-1");
    await click("league-members-remove-cancel");

    expect(byTestId("league-members-remove-dialog")).toBeNull();
    expect(byTestId("league-members-list")?.textContent).toContain("Giulia");
    expect(byTestId("league-members-success")).toBeNull();
  });

  it("la conferma rimuove solo il partecipante scelto", async () => {
    await click("league-member-remove-demo-member-1");
    await click("league-members-remove-confirm");

    expect(byTestId("league-members-remove-dialog")).toBeNull();
    const list = byTestId("league-members-list")?.textContent ?? "";
    expect(list).not.toContain("Giulia");
    expect(list).toContain("Allenatore IA 01");
    expect(byTestId("league-members-success")?.textContent).toContain(
      "Giulia è stato rimosso dalla lega.",
    );
  });
});
