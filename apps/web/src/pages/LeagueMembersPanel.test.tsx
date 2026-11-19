import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
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

/** In demo il pannello mostra 3 iscritti (admin, una persona, un'IA). */
function renderPanel(props: { participantCount: number; participantMin?: number | null }) {
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
    expect(message).toContain("Servono ancora 1 iscritti.");
    expect(message).not.toContain("abbassa");
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
        "Servono ancora 1 iscritti, oppure abbassa «Partecipanti» nel regolamento a 3 e salva.",
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
