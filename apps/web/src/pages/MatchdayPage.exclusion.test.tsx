import type {
  FantasyTurnDetail,
  FantasyTurnExclusionResult,
  FantasyTurnFixture,
  FantasyTurnSummary,
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

vi.mock("../api/leagues", () => ({
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchFantasyTurn: (...args: unknown[]) => fetchFantasyTurnMock(...args),
  excludeFantasyTurnFixture: (...args: unknown[]) => excludeFantasyTurnFixtureMock(...args),
  reincludeFantasyTurnFixture: (...args: unknown[]) => reincludeFantasyTurnFixtureMock(...args),
  excludeUnplayedFantasyTurnFixtures: vi.fn(),
  fetchH2HCalendar: vi.fn().mockResolvedValue(null),
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
    expect(container.textContent).toContain("Esclusione in corso. Poi ricalcolo la giornata.");
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
    await act(async () => {
      resolveReinclude(
        exclusionResult(detail(TURN_2, [fixture("fx-20")]), "Partita rimessa nel turno. Giornata ricalcolata."),
      );
    });

    expect(q("matchday-exclude-progress")).toBeNull();
    expect(container.textContent).toContain("Reinclusione in corso. Poi ricalcolo la giornata.");
    expect(container.textContent).not.toContain("Esclusione in corso");
    expect(q<HTMLSelectElement>("matchday-turn-select")?.value).toBe("turn-2");
    expect(q("matchday-exclude-fx-20")).not.toBeNull();
    expect(q("matchday-excluded-fixtures")).toBeNull();
  });
});
