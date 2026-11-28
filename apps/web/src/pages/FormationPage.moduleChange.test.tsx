import {
  approvedModuleCatalog,
  type FantasyModule,
  type FantasyTurnSummary,
  type LineupContext,
  type LineupRole,
  type LineupRosterPlayer,
  type SessionUser,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFantasyTurnsMock = vi.fn();
const fetchMyLineupMock = vi.fn();
const apiRequestMock = vi.fn();

// `applyBestLineup` resta quello vero: così il test controlla anche il corpo della richiesta.
vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  apiRequest: (...args: unknown[]) => apiRequestMock(...args),
}));
vi.mock("../api/leagues", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/leagues")>()),
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchMyLineup: (...args: unknown[]) => fetchMyLineupMock(...args),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
  copyPreviousLineupToDraft: vi.fn(),
  discardLineupDraft: vi.fn(),
  saveLineupDraft: vi.fn(),
  saveMyLineup: vi.fn(),
}));
vi.mock("../auth/AuthContext", () => ({
  // Fantallenatore della lega (non operatore): vede e modifica la propria formazione.
  useAuth: () => ({
    isDemoMode: false,
    activeLeagueId: "league-1",
    can: (permissions: string[]) => !permissions.includes("global:operate"),
  }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { ApiError } from "../api/client";
import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { FormationPage } from "./FormationPage";

const USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

const TURN: FantasyTurnSummary = {
  id: "turn-2",
  leagueId: "league-1",
  number: 2,
  kind: "weekend",
  windowStartAt: "2026-11-20T22:00:00.000Z",
  windowEndAt: "2026-11-24T22:00:00.000Z",
  opensAt: null,
  closesAt: null,
  cutoffAt: "2026-11-22T14:00:00.000Z",
  status: "open",
  effectiveStatus: "open",
  skipReason: null,
  fixtureCount: 10,
  generatedAt: "2026-11-18T08:00:00.000Z",
  modificationAllowed: true,
  matchStatus: "scheduled",
};

const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
const ROSTER_IDS = [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 6)];
const ROSTER: LineupRosterPlayer[] = ROSTER_IDS.map((athleteId, slotIndex) => ({
  athleteId,
  athleteName: `Giocatore ${athleteId}`,
  role: athleteId[0] as LineupRole,
  slotIndex,
  locked: false,
}));
const STARTERS_433 = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
const BENCH_433 = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8"];

function lineupContext(module: FantasyModule, starters: string[], bench: string[]): LineupContext {
  return {
    leagueId: "league-1",
    roundId: "turn-2",
    roundNumber: 2,
    kind: "weekend",
    cutoffAt: "2026-11-22T14:00:00.000Z",
    status: "open",
    effectiveStatus: "open",
    modificationAllowed: true,
    lineupLockMarginMinutes: 0,
    modules: approvedModuleCatalog(),
    roster: ROSTER,
    lineup: null,
    previousLineup: null,
    draft: {
      module,
      starterAthleteIds: starters,
      benchAthleteIds: bench,
      savedAt: "2026-11-19T10:00:00.000Z",
    },
    copyAvailable: false,
    copyIssues: [],
    issues: [],
  };
}

// Risposta del server per il 4-4-2: diversa dai «compatibili», così si vede che arriva in pagina.
const BEST_442_STARTERS = ["P2", "D5", "D6", "D1", "D2", "C4", "C5", "C1", "C2", "A4", "A5"];
const BEST_442 = lineupContext(
  "4-4-2",
  BEST_442_STARTERS,
  ROSTER_IDS.filter((athleteId) => !BEST_442_STARTERS.includes(athleteId)),
);

describe("FormationPage — cambio modulo con la formazione migliore (decisione del 19/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const moduleSelect = () => container.querySelector<HTMLSelectElement>('[data-testid="formation-module"]');
  const starterName = (index: number) =>
    container.querySelector(`[data-testid="formation-starter-${index}"] .fa-starter-row__name`)?.textContent;
  const toastText = () => container.querySelector(".fa-toast-region")?.textContent ?? "";

  async function render() {
    fetchFantasyTurnsMock.mockResolvedValue([TURN]);
    fetchMyLineupMock.mockResolvedValue(lineupContext("4-3-3", STARTERS_433, BENCH_433));
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/formazione"],
          children: createElement(ToastProvider, { children: createElement(FormationPage) }),
        }),
      );
    });
  }

  async function chooseModule(code: FantasyModule) {
    const select = moduleSelect();
    expect(select).not.toBeNull();
    await act(async () => {
      select!.value = code;
      select!.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchMyLineupMock.mockReset();
    apiRequestMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("chiede la formazione migliore sul nuovo modulo e mostra quella restituita", async () => {
    let resolveBest: (detail: LineupContext) => void = () => {};
    apiRequestMock.mockImplementation(
      () => new Promise<LineupContext>((resolve) => (resolveBest = resolve)),
    );
    await render();
    expect(starterName(0)).toBe("Giocatore P1");

    await chooseModule("4-4-2");

    expect(apiRequestMock).toHaveBeenCalledTimes(1);
    expect(apiRequestMock).toHaveBeenCalledWith("/leagues/league-1/turni/turn-2/formazione/migliore", {
      method: "POST",
      accessToken: "access-token",
      body: { mode: "keep_module", module: "4-4-2" },
    });
    // In attesa: stesso stato occupato del tasto «Applica formazione migliore».
    expect(container.querySelector<HTMLButtonElement>('[data-testid="formation-apply-best"]')?.disabled).toBe(true);
    expect(moduleSelect()?.disabled).toBe(true);

    await act(async () => {
      resolveBest(BEST_442);
    });

    expect(moduleSelect()?.value).toBe("4-4-2");
    expect(moduleSelect()?.disabled).toBe(false);
    BEST_442_STARTERS.forEach((athleteId, index) => {
      expect(starterName(index)).toBe(`Giocatore ${athleteId}`);
    });
    expect(container.querySelector<HTMLButtonElement>('[data-testid="formation-apply-best"]')?.disabled).toBe(false);
    expect(toastText()).toContain("Modulo 4-4-2: formazione migliore applicata in bozza.");
    // Solo la bozza: nessuna conferma della formazione (che consumerebbe mosse).
    expect(apiRequestMock.mock.calls.every(([path]) => String(path).endsWith("/formazione/migliore"))).toBe(true);
  });

  it("se il server non risponde tiene i compatibili e lo dice con un messaggio breve", async () => {
    apiRequestMock.mockRejectedValue(new ApiError("Servizio non disponibile.", 503, "service_unavailable"));
    await render();

    await chooseModule("4-4-2");

    expect(moduleSelect()?.value).toBe("4-4-2");
    // 4-4-2: [P, D, D, D, D, C, C, C, C, A, A] — il quarto centrocampista manca, A3 torna in panchina.
    const expected = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", null, "A1", "A2"];
    expected.forEach((athleteId, index) => {
      expect(starterName(index)).toBe(athleteId ? `Giocatore ${athleteId}` : "Seleziona calciatore");
    });
    expect(container.querySelector('[data-testid="formation-bench-order"]')?.textContent).toContain("Giocatore A3");
    expect(toastText()).toContain(
      "Non è stato possibile scegliere i migliori per il nuovo modulo: ho tenuto i giocatori compatibili.",
    );
  });

  it("con pochi disponibili tiene i compatibili e mostra il messaggio del server", async () => {
    // 28/11: gli indisponibili non entrano titolari, quindi chi allena deve sapere cosa manca.
    const message =
      "Formazione migliore non applicata: per il modulo 4-4-2 mancano calciatori disponibili (1 centrocampista). " +
      "Gli indisponibili non vengono messi titolari: scegli tu chi schierare o cambia modulo.";
    apiRequestMock.mockRejectedValue(new ApiError(message, 400, "ai_lineup_incomplete"));
    await render();

    await chooseModule("4-4-2");

    expect(moduleSelect()?.value).toBe("4-4-2");
    expect(starterName(7)).toBe("Giocatore C3");
    expect(starterName(8)).toBe("Seleziona calciatore");
    expect(starterName(10)).toBe("Giocatore A2");
    expect(toastText()).not.toContain("Non è stato possibile");
    expect(toastText()).toContain("mancano calciatori disponibili (1 centrocampista)");
  });

  it("tace sugli altri rifiuti previsti (turno chiuso)", async () => {
    apiRequestMock.mockRejectedValue(new ApiError("Turno chiuso.", 400, "turn_modification_closed"));
    await render();

    await chooseModule("4-4-2");

    expect(moduleSelect()?.value).toBe("4-4-2");
    expect(toastText()).not.toContain("Non è stato possibile");
    expect(toastText()).not.toContain("Turno chiuso");
  });
});
