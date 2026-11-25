import type {
  TradeReplacementCandidateList,
  TradeReplacementPurchase,
  TradeReplacementStatus,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchTradeReplacementsMock = vi.fn();
const fetchCandidatesMock = vi.fn();
const buyMock = vi.fn();

vi.mock("../api/market", () => ({
  fetchTradeReplacements: (...args: unknown[]) => fetchTradeReplacementsMock(...args),
  fetchTradeReplacementCandidates: (...args: unknown[]) => fetchCandidatesMock(...args),
  buyTradeReplacement: (...args: unknown[]) => buyMock(...args),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ isDemoMode: false, activeLeagueId: "league-1", can: () => true }),
}));

vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token" }),
}));

import { MemoryRouter } from "../router/simpleRouter";
import { TradeReplacementProvider, useTradeReplacement } from "./TradeReplacementContext";
import { RosterShortfallBanner } from "./TradeShortfallNotice";

const PENDING: TradeReplacementStatus = {
  teamId: "team-1",
  rosterSize: 35,
  filledSlots: 34,
  balance: 120,
  pending: [{ id: "r1", role: "D", tradeProposalId: "p1", createdAt: "2026-11-25T10:00:00Z" }],
  missingRoles: [{ role: "D", count: 1 }],
  tradeProposalId: "p1",
  otherTeamName: "Squadra Rossa",
  receivedAthleteNames: ["G. Conti"],
  receivedCredits: 0,
  blockedReason: null,
  blockedMessage: null,
};

const DONE: TradeReplacementStatus = { ...PENDING, filledSlots: 35, balance: 108, pending: [], missingRoles: [] };

const CANDIDATES: TradeReplacementCandidateList = {
  role: "D",
  balance: 120,
  total: 2,
  candidates: [
    {
      athleteId: "a-cheap",
      name: "A. Bianchi",
      photoUrl: null,
      clubName: "Lecce",
      role: "D",
      marketValue: 12,
      seasonAverage: { value: 6.1, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true },
      affordable: true,
    },
    {
      athleteId: "a-rich",
      name: "T. Colombo",
      photoUrl: null,
      clubName: "Atalanta",
      role: "D",
      marketValue: 135,
      seasonAverage: null,
      affordable: false,
    },
  ],
};

async function flush(rounds = 8): Promise<void> {
  for (let index = 0; index < rounds; index += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

function BannerProbe() {
  const { banner, open } = useTradeReplacement();
  return banner ? createElement(RosterShortfallBanner, { banner, onChoose: open }) : null;
}

async function render(path = "/rosa"): Promise<{ container: HTMLDivElement; unmount: () => void }> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);
  const tree: ReactNode = createElement(MemoryRouter, {
    initialEntries: [path],
    children: createElement(ToastProvider, {
      children: createElement(TradeReplacementProvider, { children: createElement(BannerProbe) }),
    }),
  });
  await act(async () => {
    root.render(tree);
  });
  await flush();
  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

function byTestId(container: HTMLElement, id: string): HTMLElement | null {
  return container.querySelector(`[data-testid="${id}"]`);
}

async function click(element: HTMLElement | null): Promise<void> {
  expect(element).not.toBeNull();
  await act(async () => {
    element?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await flush();
}

describe("Sostituto dopo lo scambio sbilanciato (1.5)", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    fetchTradeReplacementsMock.mockReset().mockResolvedValue(PENDING);
    fetchCandidatesMock.mockReset().mockResolvedValue(CANDIDATES);
    buyMock.mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("si apre da sola una volta per sessione e mostra scambio, testo, etichette e liberi", async () => {
    const { container, unmount } = await render();
    expect(byTestId(container, "replacement-sheet")).not.toBeNull();
    expect(byTestId(container, "replacement-done")?.textContent).toContain("Scambio fatto: è arrivato G. Conti");
    expect(byTestId(container, "replacement-intro")?.textContent).toBe(
      "Ti manca 1 Difensore. Scegline uno tra i liberi: lo paghi il suo Valore.",
    );
    expect(byTestId(container, "replacement-chips")?.textContent).toContain("Rosa 34/35");
    expect(byTestId(container, "replacement-chips")?.textContent).toContain("Crediti 120");
    expect(byTestId(container, "replacement-chips")?.textContent).toContain("Solo D");
    expect(fetchCandidatesMock).toHaveBeenCalledWith("token", "league-1", { role: "D", search: "", order: "valore" });
    const cheap = byTestId(container, "replacement-candidate-a-cheap");
    expect(cheap?.textContent).toContain("Lecce");
    expect(cheap?.textContent).toContain("Valore 12");
    expect(cheap?.textContent).toContain("Media");
    expect(byTestId(container, "replacement-take-a-cheap")?.textContent).toBe("Prendi · 12");
    const rich = byTestId(container, "replacement-take-a-rich") as HTMLButtonElement | null;
    expect(rich?.disabled).toBe(true);
    expect(byTestId(container, "replacement-candidate-a-rich")?.textContent).toContain("Costa più dei tuoi crediti");
    expect(container.textContent).toContain("Finché non scegli non puoi schierare la formazione.");

    // «Più tardi» chiude; il riquadro della pagina resta e riapre la finestra.
    await click(byTestId(container, "replacement-later"));
    expect(byTestId(container, "replacement-sheet")).toBeNull();
    expect(byTestId(container, "roster-shortfall-banner")?.textContent).toContain("Rosa incompleta: 34/35");
    expect(byTestId(container, "roster-shortfall-banner")?.textContent).toContain(
      "Ti manca un Difensore dopo lo scambio. Sceglilo per poter schierare la formazione.",
    );
    expect(byTestId(container, "roster-shortfall-banner-choose")?.textContent).toBe("Scegli il sostituto (Difensore)");
    unmount();

    // Nella stessa sessione non si riapre da sola.
    const again = await render();
    expect(byTestId(again.container, "replacement-sheet")).toBeNull();
    await click(byTestId(again.container, "roster-shortfall-banner-choose"));
    expect(byTestId(again.container, "replacement-sheet")).not.toBeNull();
    again.unmount();
  });

  it("dal link della notifica si apre anche se rimandata", async () => {
    window.sessionStorage.setItem("fa.sostituto.rimandato.league-1", "1");
    const { container, unmount } = await render("/rosa?sostituto=1&lega=league-1");
    expect(byTestId(container, "replacement-sheet")).not.toBeNull();
    unmount();
  });

  it("conferma con il conto e compra al Valore", async () => {
    const purchase: TradeReplacementPurchase = {
      athleteId: "a-cheap",
      athleteName: "A. Bianchi",
      role: "D",
      priceCredits: 12,
      balance: 108,
      status: DONE,
    };
    buyMock.mockResolvedValue(purchase);
    const { container, unmount } = await render();
    await click(byTestId(container, "replacement-take-a-cheap"));
    expect(container.textContent).toContain("Prendi A. Bianchi per 12 crediti?");
    const bill = byTestId(container, "replacement-bill")?.textContent ?? "";
    expect(bill).toContain("Crediti ora");
    expect(bill).toContain("120");
    expect(bill).toContain("Valore di A. Bianchi");
    expect(bill).toContain("− 12");
    expect(bill).toContain("Ti restano");
    expect(bill).toContain("108");
    expect(byTestId(container, "replacement-confirm-note")?.textContent).toBe(
      "La rosa torna 35/35 e puoi schierare subito la formazione. Vale anche a mercato chiuso.",
    );
    await click(byTestId(container, "replacement-confirm"));
    expect(buyMock).toHaveBeenCalledWith("token", "league-1", "a-cheap");
    // Rosa di nuovo completa: la finestra e il riquadro spariscono.
    expect(byTestId(container, "replacement-sheet")).toBeNull();
    expect(byTestId(container, "roster-shortfall-banner")).toBeNull();
    unmount();
  });

  it("se il calciatore è appena stato preso lo dice e torna all'elenco", async () => {
    buyMock.mockRejectedValue(new Error("A. Bianchi è già nella rosa di un'altra squadra della lega: scegline un altro."));
    const { container, unmount } = await render();
    await click(byTestId(container, "replacement-take-a-cheap"));
    await click(byTestId(container, "replacement-confirm"));
    expect(byTestId(container, "replacement-error")).not.toBeNull();
    expect(byTestId(container, "replacement-list")).not.toBeNull();
    unmount();
  });

  it("senza sostituti non apre nulla e non mostra riquadri", async () => {
    fetchTradeReplacementsMock.mockResolvedValue(DONE);
    const { container, unmount } = await render();
    expect(byTestId(container, "replacement-sheet")).toBeNull();
    expect(byTestId(container, "roster-shortfall-banner")).toBeNull();
    unmount();
  });

  it("corsa Mercato 25/11: nessun libero alla portata, riquadro in alto ed elenco tutto grigio", async () => {
    fetchTradeReplacementsMock.mockResolvedValue({
      ...PENDING,
      balance: 0,
      canAffordReplacement: false,
      cheapestReplacementPrice: 12,
      replacementCosts: [{ role: "D", count: 1, cheapestPrice: 12, totalPrice: 12 }],
    });
    fetchCandidatesMock.mockResolvedValue({
      ...CANDIDATES,
      balance: 0,
      candidates: CANDIDATES.candidates.map((item) => ({ ...item, affordable: false })),
    });
    const { container, unmount } = await render();
    expect(byTestId(container, "replacement-unaffordable")?.textContent).toBe(
      "Nessun libero alla tua portata: hai 0 crediti e il più economico costa 12. Chiedi all'admin di assegnarti un Difensore.",
    );
    // L'elenco resta visibile, con tutte le righe spente.
    expect(byTestId(container, "replacement-list")).not.toBeNull();
    for (const id of ["a-cheap", "a-rich"]) {
      expect(byTestId(container, `replacement-candidate-${id}`)?.className).toContain("fa-replacement__row--disabled");
      expect((byTestId(container, `replacement-take-${id}`) as HTMLButtonElement | null)?.disabled).toBe(true);
    }
    unmount();
  });

  it("con i crediti che bastano niente riquadro", async () => {
    fetchTradeReplacementsMock.mockResolvedValue({
      ...PENDING,
      canAffordReplacement: true,
      cheapestReplacementPrice: 12,
      replacementCosts: [{ role: "D", count: 1, cheapestPrice: 12, totalPrice: 12 }],
    });
    const { container, unmount } = await render();
    expect(byTestId(container, "replacement-sheet")).not.toBeNull();
    expect(byTestId(container, "replacement-unaffordable")).toBeNull();
    unmount();
  });

  it("corsa Mercato 25/11: dopo l'ultimo sostituto, se un ruolo resta sotto quota, la conferma lo dice", async () => {
    fetchTradeReplacementsMock.mockResolvedValue({
      ...PENDING,
      underQuotaRoles: [
        { role: "D", count: 10, quota: 11 },
        { role: "C", count: 10, quota: 11 },
      ],
    });
    buyMock.mockResolvedValue({
      athleteId: "a-cheap",
      athleteName: "A. Bianchi",
      role: "D",
      priceCredits: 12,
      balance: 108,
      status: { ...DONE, underQuotaRoles: [{ role: "C", count: 10, quota: 11 }] },
    } satisfies TradeReplacementPurchase);
    const { container, unmount } = await render();
    await click(byTestId(container, "replacement-take-a-cheap"));
    expect(byTestId(container, "replacement-confirm-note")?.textContent).toBe(
      "La rosa torna 35/35 e puoi schierare subito la formazione. Vale anche a mercato chiuso. " +
        "Ruoli sotto quota: 10 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.",
    );
    await click(byTestId(container, "replacement-confirm"));
    expect(buyMock).toHaveBeenCalledWith("token", "league-1", "a-cheap");
    expect(document.body.textContent).toContain(
      "Hai preso A. Bianchi per 12 crediti. La rosa è completa: puoi schierare la formazione. " +
        "Ruoli sotto quota: 10 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.",
    );
    unmount();
  });

  it("a turno in corso dice quando si potrà scegliere e non fa prendere nessuno", async () => {
    fetchTradeReplacementsMock.mockResolvedValue({
      ...PENDING,
      blockedReason: "round_in_progress",
      blockedMessage: "Il turno 12 è in corso e le rose sono ferme: potrai scegliere il sostituto appena il turno 12 sarà calcolato.",
    });
    const { container, unmount } = await render();
    expect(byTestId(container, "replacement-blocked")?.textContent).toContain("appena il turno 12 sarà calcolato");
    expect((byTestId(container, "replacement-take-a-cheap") as HTMLButtonElement | null)?.disabled).toBe(true);
    unmount();
  });
});
