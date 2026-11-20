import {
  approvedModuleCatalog,
  type FantasyTurnSummary,
  type LineupContext,
  type LineupPlayer,
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
const saveMyLineupMock = vi.fn();
const saveLineupDraftMock = vi.fn();
const applyBestLineupMock = vi.fn();
const copyPreviousLineupToDraftMock = vi.fn();
const discardLineupDraftMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchMyLineup: (...args: unknown[]) => fetchMyLineupMock(...args),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
  applyBestLineup: (...args: unknown[]) => applyBestLineupMock(...args),
  copyPreviousLineupToDraft: (...args: unknown[]) => copyPreviousLineupToDraftMock(...args),
  discardLineupDraft: (...args: unknown[]) => discardLineupDraftMock(...args),
  saveLineupDraft: (...args: unknown[]) => saveLineupDraftMock(...args),
  saveMyLineup: (...args: unknown[]) => saveMyLineupMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    isDemoMode: false,
    activeLeagueId: "league-1",
    can: (permissions: string[]) => !permissions.includes("global:operate"),
  }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { FormationPage } from "./FormationPage";

const USER: SessionUser = { id: "user-1", displayName: "Membro Test", globalRole: "member" };

const TURN: FantasyTurnSummary = {
  id: "turn-4",
  leagueId: "league-1",
  number: 4,
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

// Rosa da 25 in ordine di rosa (P→D→C→A), 4-3-3 salvato.
const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
const ROSTER_IDS = [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 6)];
const STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
const SAVED_BENCH = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8"];
const SUCCESS =
  "Formazione svuotata. Scegli i titolari nell'elenco «Titolari», oppure usa «Applica formazione migliore».";

function rosterRow(athleteId: string, slotIndex: number, locked: readonly string[]): LineupRosterPlayer {
  return {
    athleteId,
    athleteName: `Giocatore ${athleteId}`,
    role: athleteId[0] as LineupRole,
    slotIndex,
    locked: locked.includes(athleteId),
  };
}

function player(athleteId: string, slotKind: "starter" | "bench", sortOrder: number): LineupPlayer {
  return { athleteId, athleteName: `Giocatore ${athleteId}`, role: athleteId[0] as LineupRole, slotKind, sortOrder };
}

function lineupContext(locked: readonly string[] = [], extra: Partial<LineupContext> = {}): LineupContext {
  return {
    leagueId: "league-1",
    roundId: "turn-4",
    roundNumber: 4,
    kind: "weekend",
    cutoffAt: "2026-11-22T14:00:00.000Z",
    status: "open",
    effectiveStatus: "open",
    modificationAllowed: true,
    lineupLockMarginMinutes: 0,
    maxTacticalMoves: 3,
    tacticalMovesUsed: 0,
    tacticalMovesRemaining: 3,
    modules: approvedModuleCatalog(),
    roster: ROSTER_IDS.map((athleteId, slotIndex) => rosterRow(athleteId, slotIndex, locked)),
    lineup: {
      id: "lineup-1",
      module: "4-3-3",
      revision: 1,
      submittedAt: "2026-11-19T09:00:00.000Z",
      systemGeneratedAi: false,
      aiAlgorithmVersion: null,
      aiDecidedAt: null,
      starters: STARTERS.map((athleteId, index) => player(athleteId, "starter", index)),
      bench: SAVED_BENCH.map((athleteId, index) => player(athleteId, "bench", index)),
    },
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues: [],
    ...extra,
  };
}

describe("FormationPage — «Svuota formazione» (Rosario, 20/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = <T extends Element = HTMLElement>(testId: string) =>
    container.querySelector<T>(`[data-testid="${testId}"]`);
  const starterName = (index: number) =>
    container.querySelector(`[data-testid="formation-starter-${index}"] .fa-starter-row__name`)?.textContent;
  const starters = () => STARTERS.map((_, index) => starterName(index));
  const toastText = () => container.querySelector(".fa-toast-region")?.textContent ?? "";
  /** La panchina come la mostra la pagina: un id per posto, in ordine. */
  const shownBench = () => {
    const out: string[] = [];
    for (let index = 0; ; index += 1) {
      const row = byTestId(`formation-bench-change-${index}`);
      if (!row) {
        return out;
      }
      out.push(/Giocatore (\w+)/.exec(row.textContent ?? "")?.[1] ?? "?");
    }
  };

  async function render(context: LineupContext) {
    fetchFantasyTurnsMock.mockResolvedValue([TURN]);
    fetchMyLineupMock.mockResolvedValue(context);
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/formazione"],
          children: createElement(ToastProvider, { children: createElement(FormationPage) }),
        }),
      );
    });
  }

  async function click(testId: string) {
    const button = byTestId<HTMLButtonElement>(testId);
    expect(button).not.toBeNull();
    expect(button?.disabled).toBe(false);
    await act(async () => {
      button!.click();
    });
  }

  function expectNoServerCalls() {
    expect(saveMyLineupMock).not.toHaveBeenCalled();
    expect(saveLineupDraftMock).not.toHaveBeenCalled();
    expect(applyBestLineupMock).not.toHaveBeenCalled();
    expect(copyPreviousLineupToDraftMock).not.toHaveBeenCalled();
    expect(discardLineupDraftMock).not.toHaveBeenCalled();
    // Solo il caricamento iniziale della formazione: svuotare non chiama il server.
    expect(fetchMyLineupMock).toHaveBeenCalledTimes(1);
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    for (const mock of [
      fetchFantasyTurnsMock,
      fetchMyLineupMock,
      saveMyLineupMock,
      saveLineupDraftMock,
      applyBestLineupMock,
      copyPreviousLineupToDraftMock,
      discardLineupDraftMock,
    ]) {
      mock.mockReset();
    }
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("conferma, «Indietro» non tocca niente, «Svuota formazione» svuota e «Annulla modifiche» rimette tutto", async () => {
    await render(lineupContext());
    const savedStarters = starters();
    expect(savedStarters[0]).toBe("Giocatore P1");
    expect(shownBench()).toEqual(SAVED_BENCH);
    expect(byTestId<HTMLButtonElement>("formation-revert")?.disabled).toBe(true);

    // Tasto con il contorno rosso accanto agli altri strumenti; la conferma si apre e si chiude.
    expect(byTestId("formation-clear")?.textContent).toBe("Svuota formazione");
    expect(byTestId("formation-clear")?.className).toContain("fa-formation-clear");
    await click("formation-clear");
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog?.textContent).toContain("Svuotare la formazione?");
    expect(dialog?.textContent).toContain(
      "Tolgo tutti i titolari e rimetto la panchina nell'ordine della rosa, così la ricomponi da capo.",
    );
    const points = [...(byTestId("formation-clear-points")?.querySelectorAll("li") ?? [])].map((li) => li.textContent);
    expect(points).toEqual([
      "I giocatori già bloccati restano al loro posto.",
      "Finché non salvi, vale ancora la formazione salvata: puoi tornare indietro con «Annulla modifiche».",
      "A turno iniziato, salvare la nuova formazione conta come una mossa.",
    ]);
    expect(byTestId("formation-clear-cancel")?.textContent).toBe("Indietro");
    expect(byTestId("formation-clear-confirm")?.textContent).toBe("Svuota formazione");

    await click("formation-clear-cancel");
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(starters()).toEqual(savedStarters);
    expect(shownBench()).toEqual(SAVED_BENCH);
    expect(toastText()).not.toContain("Formazione svuotata");

    await click("formation-clear");
    await click("formation-clear-confirm");
    expect(container.querySelector('[role="dialog"]')).toBeNull();

    // 0/11 titolari, panchina nell'ordine della rosa con 1P·3D·3C·3A nei primi 10.
    expect(starters()).toEqual(STARTERS.map(() => "Seleziona calciatore"));
    expect(shownBench()).toEqual([
      "P1", "D1", "D2", "D3", "C1", "C2", "C3", "A1", "A2", "A3",
      "P2", "P3", "D4", "D5", "D6", "D7", "D8", "C4", "C5", "C6", "C7", "C8", "A4", "A5", "A6",
    ]);
    expect(toastText()).toContain(SUCCESS);
    expect(byTestId("formation-issues")?.textContent).toContain("esattamente 11 titolari (attuali: 0)");
    expect(byTestId("formation-issues")?.textContent).not.toContain("Nei primi 10 della panchina");
    // Salvataggio spento finché mancano i titolari; «Annulla modifiche» e «Ripristina» disponibili.
    expect(byTestId<HTMLButtonElement>("formation-save")?.disabled).toBe(true);
    expect(byTestId<HTMLButtonElement>("formation-revert")?.disabled).toBe(false);
    expect(byTestId("formation-reset")).not.toBeNull();
    // Già svuotata: niente altro da togliere.
    expect(byTestId<HTMLButtonElement>("formation-clear")?.disabled).toBe(true);
    // Nessuna mossa prevista: nessuna partita è iniziata.
    expect(byTestId("formation-moves-draft-badge")).toBeNull();
    expectNoServerCalls();

    await click("formation-revert");
    expect(starters()).toEqual(savedStarters);
    expect(shownBench()).toEqual(SAVED_BENCH);
    expect(byTestId<HTMLButtonElement>("formation-revert")?.disabled).toBe(true);
    expect(byTestId<HTMLButtonElement>("formation-clear")?.disabled).toBe(false);
    expectNoServerCalls();
  });

  it("a turno iniziato i bloccati restano al loro posto e chi sale non li fa scorrere", async () => {
    // A3 titolare e D7 (4° in panchina) hanno già giocato.
    await render(lineupContext(["A3", "D7"]));

    await click("formation-clear");
    await click("formation-clear-confirm");

    expect(starters()).toEqual([...STARTERS.slice(0, 10).map(() => "Seleziona calciatore"), "Giocatore A3"]);
    // Chi è davanti a D7 non può scavalcarlo: resta dov'è, e il messaggio lo dice.
    expect(shownBench().slice(0, 4)).toEqual(["P2", "D5", "D6", "D7"]);
    expect(toastText()).toContain("In panchina resta al suo posto anche chi è davanti a un giocatore già bloccato.");
    // L'anteprima della mossa tattica continua a funzionare.
    expect(byTestId("formation-moves-draft-badge")?.textContent).toContain("Mossa in bozza → 1/3");

    // D5 sale titolare: il suo posto in panchina lo prende D1 (titolare tolto), D7 resta 4°.
    await click("formation-starter-1");
    await click("formation-starter-1-option-D5");
    expect(starterName(1)).toBe("Giocatore D5");
    expect(shownBench().slice(0, 4)).toEqual(["P2", "D1", "D6", "D7"]);
    expectNoServerCalls();
  });

  it("con il turno non più modificabile il tasto è spento", async () => {
    await render(lineupContext([], { modificationAllowed: false }));
    expect(byTestId<HTMLButtonElement>("formation-clear")?.disabled).toBe(true);
  });
});
