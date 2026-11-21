import type {
  FantasyTurnDetail,
  FantasyTurnExclusionResult,
  FantasyTurnFixture,
  FantasyTurnSummary,
  H2HCalendar,
  SessionUser,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFantasyTurnsMock = vi.fn();
const fetchFantasyTurnMock = vi.fn();
const excludeFantasyTurnFixtureMock = vi.fn();
const reincludeFantasyTurnFixtureMock = vi.fn();
const fetchH2HCalendarMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchFantasyTurn: (...args: unknown[]) => fetchFantasyTurnMock(...args),
  excludeFantasyTurnFixture: (...args: unknown[]) => excludeFantasyTurnFixtureMock(...args),
  reincludeFantasyTurnFixture: (...args: unknown[]) => reincludeFantasyTurnFixtureMock(...args),
  excludeUnplayedFantasyTurnFixtures: vi.fn(),
  fetchH2HCalendar: (...args: unknown[]) => fetchH2HCalendarMock(...args),
  fetchPendingFixtures: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
}));
vi.mock("../auth/AuthContext", () => ({
  // Admin della lega: vede «Escludi» e «Rimetti nel turno».
  useAuth: () => ({ isDemoMode: false, activeLeagueId: "league-1", can: () => true }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { MatchdayPage } from "./MatchdayPage";

const USER: SessionUser = { id: "user-1", displayName: "Admin Test", globalRole: "member" };

function summary(id: string, number: number): FantasyTurnSummary {
  return {
    id,
    leagueId: "league-1",
    number,
    kind: "weekend",
    windowStartAt: `2026-11-${20 + number * 2}T22:00:00.000Z`,
    windowEndAt: `2026-11-${21 + number * 2}T22:00:00.000Z`,
    opensAt: null,
    closesAt: null,
    cutoffAt: null,
    status: "scheduled",
    effectiveStatus: "scheduled",
    skipReason: null,
    fixtureCount: 1,
    generatedAt: "2026-11-18T08:00:00.000Z",
    modificationAllowed: true,
    matchStatus: "scheduled",
  };
}

function fixture(fixtureId: string): FantasyTurnFixture {
  return {
    id: `row-${fixtureId}`,
    fixtureId,
    includedReason: "window",
    excludedAt: null,
    kickoffAt: "2026-11-25T19:45:00.000Z",
    observedKickoffAt: null,
    lockLatchedAt: null,
    statusShort: "NS",
    statusElapsed: null,
    homeGoals: null,
    awayGoals: null,
    homeClubName: "Inter",
    awayClubName: "Milan",
    homeClubLogoUrl: null,
    awayClubLogoUrl: null,
    competitionName: "Serie A",
    providerId: 1,
    updatedAt: null,
    feedState: "fresh",
    feedStateLabel: "Aggiornato",
  };
}

function detail(base: FantasyTurnSummary, fixtures: FantasyTurnFixture[], excluded: FantasyTurnFixture[] = []): FantasyTurnDetail {
  return {
    ...base,
    fixtureCount: fixtures.length,
    homologationStatus: "provisional",
    fixtures,
    excludedFixtures: excluded,
  };
}

// Il turno 1 è quello di default (il primo non concluso); l'admin lavora sul turno 2.
const TURN_1 = summary("turn-1", 1);
const TURN_2 = summary("turn-2", 2);

const H2H_CALENDAR: H2HCalendar = {
  id: "calendar-1",
  leagueId: "league-1",
  status: "confirmed",
  format: "single_round_robin",
  algorithmVersion: "v1",
  participantCount: 4,
  roundCount: 3,
  matchupCount: 6,
  byeCount: 0,
  generatedAt: "2026-11-01T10:00:00.000Z",
  confirmedAt: "2026-11-01T12:00:00.000Z",
  live: false,
  rounds: [],
  summary: { message: "Calendario confermato." },
};

describe("MatchdayPage — esclusione e reinclusione di una partita", () => {
  let container: HTMLDivElement;
  let root: Root;

  const q = <T extends Element>(testId: string) =>
    container.querySelector(`[data-testid="${testId}"]`) as T | null;

  async function renderAndOpenTurn2(turn2: FantasyTurnDetail) {
    fetchFantasyTurnsMock.mockResolvedValue([TURN_1, TURN_2]);
    fetchFantasyTurnMock.mockImplementation(async (_token: string, _league: string, turnId: string) =>
      turnId === "turn-2" ? turn2 : detail(TURN_1, [fixture("fx-10")]),
    );
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/turni?tab=europei"],
          children: createElement(ToastProvider, { children: createElement(MatchdayPage) }),
        }),
      );
    });
    expect(q<HTMLSelectElement>("matchday-turn-select")?.value).toBe("turn-1");
    const select = q<HTMLSelectElement>("matchday-turn-select")!;
    await act(async () => {
      select.value = "turn-2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(q<HTMLSelectElement>("matchday-turn-select")?.value).toBe("turn-2");
    expect(q("matchday-turn-detail")?.querySelector("h2")?.textContent).toBe("Turno 2");
  }

  async function click(testId: string) {
    await act(async () => {
      q<HTMLButtonElement>(testId)!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  }

  function exclusionResult(turn: FantasyTurnDetail, message: string): FantasyTurnExclusionResult {
    return { turn, excludedCount: 1, recalculated: true, resultFinal: false, homologated: false, message };
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchFantasyTurnMock.mockReset();
    excludeFantasyTurnFixtureMock.mockReset();
    reincludeFantasyTurnFixtureMock.mockReset();
    // Di base la lega ha il calendario H2H: dopo l'esclusione la giornata si ricalcola.
    fetchH2HCalendarMock.mockReset();
    fetchH2HCalendarMock.mockResolvedValue(H2H_CALENDAR);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("dopo «Escludi» resta sul turno scelto e aggiorna solo l'elenco dei turni", async () => {
    await renderAndOpenTurn2(detail(TURN_2, [fixture("fx-20")]));
    excludeFantasyTurnFixtureMock.mockResolvedValue(
      exclusionResult(detail(TURN_2, [], [fixture("fx-20")]), "Partita esclusa. Giornata ricalcolata."),
    );
    const turnDetailCalls = fetchFantasyTurnMock.mock.calls.length;

    await click("matchday-exclude-fx-20");

    expect(excludeFantasyTurnFixtureMock).toHaveBeenCalledWith("access-token", "league-1", "turn-2", {
      fixtureId: "fx-20",
    });
    // L'esito sostituisce l'avviso «in corso» (QA 20-21/11).
    expect(container.textContent).not.toContain("Esclusione in corso. Poi ricalcolo la giornata.");
    expect(container.querySelector(".fa-toast--info")?.textContent).toContain(
      "Partita esclusa. Giornata ricalcolata.",
    );
    expect(q<HTMLSelectElement>("matchday-turn-select")?.value).toBe("turn-2");
    expect(q("matchday-turn-detail")?.querySelector("h2")?.textContent).toBe("Turno 2");
    expect(q("matchday-reinclude-fx-20")).not.toBeNull();
    expect(q("matchday-success")?.textContent).toBe("Partita esclusa. Giornata ricalcolata.");
    // L'elenco dei turni si aggiorna (conteggi), ma nessun turno viene riselezionato.
    expect(fetchFantasyTurnsMock).toHaveBeenCalledTimes(2);
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(turnDetailCalls);
  });

  it("«Rimetti nel turno» annuncia la reinclusione e resta sul turno scelto", async () => {
    await renderAndOpenTurn2(detail(TURN_2, [], [fixture("fx-20")]));
    let resolveReinclude: (result: FantasyTurnExclusionResult) => void = () => undefined;
    reincludeFantasyTurnFixtureMock.mockReturnValue(
      new Promise<FantasyTurnExclusionResult>((resolve) => {
        resolveReinclude = resolve;
      }),
    );

    await click("matchday-reinclude-fx-20");

    expect(reincludeFantasyTurnFixtureMock).toHaveBeenCalledWith("access-token", "league-1", "turn-2", {
      fixtureId: "fx-20",
    });
    // Mentre il server lavora: avviso e nota nella pagina parlano di reinclusione.
    expect(q("matchday-exclude-progress")?.textContent).toBe("Reinclusione in corso. Poi ricalcolo la giornata.");
    expect(container.querySelector(".fa-toast")?.textContent).toContain(
      "Reinclusione in corso. Poi ricalcolo la giornata.",
    );
    await act(async () => {
      resolveReinclude(
        exclusionResult(detail(TURN_2, [fixture("fx-20")]), "Partita rimessa nel turno. Giornata ricalcolata."),
      );
    });

    expect(q("matchday-exclude-progress")).toBeNull();
    // Arrivato l'esito, l'avviso «in corso» si chiude e resta solo quello con l'esito.
    expect(container.textContent).not.toContain("Reinclusione in corso");
    expect(container.querySelectorAll(".fa-toast")).toHaveLength(1);
    expect(container.textContent).toContain("Partita rimessa nel turno. Giornata ricalcolata.");
    expect(container.textContent).not.toContain("Esclusione in corso");
    expect(q<HTMLSelectElement>("matchday-turn-select")?.value).toBe("turn-2");
    expect(q("matchday-exclude-fx-20")).not.toBeNull();
    expect(q("matchday-excluded-fixtures")).toBeNull();
  });

  it("un turno aperto col primo blocco passato è «In corso» e uno saltato «Turno saltato»", async () => {
    const started: FantasyTurnSummary = {
      ...TURN_1,
      status: "open",
      effectiveStatus: "open",
      modificationAllowed: false,
      // Primo blocco un'ora fa, primo calcio d'inizio fra 15 minuti: nessuna partita è live.
      firstLockAt: new Date(Date.now() - 60 * 60_000).toISOString(),
      cutoffAt: new Date(Date.now() + 15 * 60_000).toISOString(),
    };
    const skipped: FantasyTurnSummary = { ...TURN_2, status: "skipped", effectiveStatus: "skipped" };
    const next = summary("turn-3", 3);
    fetchFantasyTurnsMock.mockResolvedValue([started, skipped, next]);
    fetchFantasyTurnMock.mockResolvedValue(detail(started, [fixture("fx-10")]));
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/turni?tab=europei"],
          children: createElement(ToastProvider, { children: createElement(MatchdayPage) }),
        }),
      );
    });

    const options = Array.from(
      q<HTMLSelectElement>("matchday-turn-select")?.querySelectorAll("option") ?? [],
    ).map((option) => option.textContent);
    // Il turno in corso occupa il posto del prossimo: il successivo è «Da disputare».
    expect(options).toEqual([
      "Turno 1 — In corso",
      "Turno 2 — Turno saltato",
      "Turno 3 — Da disputare",
    ]);
    expect(q("matchday-turn-detail")?.textContent).toContain("Stato: In corso");
  });

  it("senza calendario non annuncia né segnala un ricalcolo (QA 20-21/11)", async () => {
    fetchH2HCalendarMock.mockResolvedValue(null);
    await renderAndOpenTurn2(detail(TURN_2, [fixture("fx-20")]));
    let resolveExclude: (result: FantasyTurnExclusionResult) => void = () => undefined;
    excludeFantasyTurnFixtureMock.mockReturnValue(
      new Promise<FantasyTurnExclusionResult>((resolve) => {
        resolveExclude = resolve;
      }),
    );

    await click("matchday-exclude-fx-20");

    expect(q("matchday-exclude-progress")?.textContent).toBe("Esclusione in corso.");
    expect(container.textContent).not.toContain("ricalcolo");
    await act(async () => {
      resolveExclude({
        turn: detail(TURN_2, [], [fixture("fx-20")]),
        excludedCount: 1,
        recalculated: false,
        resultFinal: false,
        homologated: false,
        recalculationSkipped: true,
        message: "Partita esclusa.",
      });
    });

    expect(container.textContent).not.toContain("Il ricalcolo non è riuscito");
    expect(container.textContent).not.toContain("Esclusione in corso");
    expect(container.querySelectorAll(".fa-toast")).toHaveLength(1);
    expect(container.querySelector(".fa-toast--success")?.textContent).toContain("Partita esclusa.");
    expect(container.querySelector(".fa-toast--warning")).toBeNull();
    expect(q("matchday-success")?.textContent).toBe("Partita esclusa.");
  });
});
