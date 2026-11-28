import type { FantasyTurnDetail, FantasyTurnFixture, FantasyTurnSummary, SessionUser } from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import stylesCss from "../styles.css?raw";

const fetchFantasyTurnsMock = vi.fn();
const fetchFantasyTurnMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchFantasyTurn: (...args: unknown[]) => fetchFantasyTurnMock(...args),
  excludeFantasyTurnFixture: vi.fn(),
  reincludeFantasyTurnFixture: vi.fn(),
  excludeUnplayedFantasyTurnFixtures: vi.fn(),
  fetchH2HCalendar: vi.fn().mockResolvedValue(null),
  fetchPendingFixtures: vi.fn().mockResolvedValue([]),
  fetchLineupLockCountdown: vi.fn().mockResolvedValue(null),
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    isDemoMode: false,
    activeLeagueId: "league-1",
    can: (permissions: string[]) => !permissions.includes("league:admin"),
  }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { BrowserRouter } from "../router/simpleRouter";
import { MatchdayPage } from "./MatchdayPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const USER: SessionUser = { id: "user-1", displayName: "Marco", globalRole: "member" };

const SUMMARY: FantasyTurnSummary = {
  id: "turn-12",
  leagueId: "league-1",
  number: 12,
  kind: "weekend",
  windowStartAt: "2026-11-27T22:00:00.000Z",
  windowEndAt: "2026-12-02T22:00:00.000Z",
  opensAt: null,
  closesAt: null,
  cutoffAt: "2026-11-28T14:00:00.000Z",
  status: "open",
  effectiveStatus: "open",
  skipReason: null,
  fixtureCount: 5,
  generatedAt: "2026-11-27T08:00:00.000Z",
  modificationAllowed: true,
  matchStatus: "scheduled",
};

function fixture(index: number, competition: string, home: string, away: string): FantasyTurnFixture {
  return {
    id: `rf-${index}`,
    fixtureId: `fx-${index}`,
    includedReason: "window",
    excludedAt: null,
    kickoffAt: "2026-11-30T22:35:00.000Z",
    observedKickoffAt: null,
    lockLatchedAt: null,
    statusShort: "NS",
    statusElapsed: null,
    homeGoals: null,
    awayGoals: null,
    homeClubName: home,
    awayClubName: away,
    homeClubLogoUrl: null,
    awayClubLogoUrl: null,
    competitionName: competition,
    providerId: 1000 + index,
    updatedAt: null,
    feedState: "fresh",
    feedStateLabel: "Aggiornato",
  };
}

const DETAIL: FantasyTurnDetail = {
  ...SUMMARY,
  homologationStatus: "provisional",
  excludedFixtures: [],
  fixtures: [
    fixture(1, "Bundesliga", "Borussia Mönchengladbach", "Bayern München"),
    fixture(2, "Serie A", "Inter", "Milan"),
    fixture(3, "Ligue 1", "Paris Saint-Germain", "Olympique de Marseille"),
    fixture(4, "La Liga", "Atlético Madrid", "Athletic Club"),
    fixture(5, "Premier League", "Manchester United", "Wolverhampton Wanderers"),
  ],
};

type CssRule = { selector: string; body: string };

/** Regole (anche dentro le media query) di styles.css, senza commenti. */
function cssRules(css: string): CssRule[] {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...withoutComments.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => ({
    selector: (match[1] ?? "").trim().replace(/\s+/g, " "),
    body: match[2] ?? "",
  }));
}

function bodiesFor(selector: string): string[] {
  return cssRules(stylesCss)
    .filter((rule) => rule.selector.split(",").some((part) => part.trim() === selector))
    .map((rule) => rule.body);
}

describe("Turni europei su telefono: la pagina sta nello schermo (Rosario 27/11, Chrome su Android a 390px)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    window.history.replaceState(null, "", "/turni?tab=europei");
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchFantasyTurnMock.mockReset();
    fetchFantasyTurnsMock.mockResolvedValue([SUMMARY]);
    fetchFantasyTurnMock.mockResolvedValue(DETAIL);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
    window.history.replaceState(null, "", "/");
  });

  async function renderTurni() {
    await act(async () => {
      root.render(
        createElement(BrowserRouter, {
          children: createElement(ToastProvider, { children: createElement(MatchdayPage) }),
        }),
      );
    });
  }

  it("la pagina porta la classe che stringe la colonna e la barra dei campionati sta dentro", async () => {
    await renderTurni();

    const page = container.querySelector(".fa-page-container");
    expect(page?.classList.contains("fa-matchday-page")).toBe(true);
    // La colonna della pagina (la griglia con le schede Calendario/Turni europei) è figlia diretta.
    expect(page?.querySelector(":scope > .fa-page-container__body")).not.toBeNull();

    const bar = container.querySelector(".fa-matchday-competitions-tabs .fa-tablist");
    expect(bar).not.toBeNull();
    const names = [...bar!.querySelectorAll(".fa-tab")].map((tab) => tab.textContent?.trim());
    expect(names).toEqual(["Bundesliga", "Serie A", "Ligue 1", "La Liga", "Premier League"]);
    // Le carte delle partite del campionato scelto ci sono tutte.
    expect(container.querySelectorAll('[data-testid="matchday-competition-Bundesliga"] .fa-match-card')).toHaveLength(1);
  });

  it("styles.css: la colonna è larga quanto lo schermo, non quanto la barra dei campionati", () => {
    const column = bodiesFor(".fa-matchday-page > .fa-page-container__body");
    expect(column.length).toBeGreaterThan(0);
    expect(column.join(";")).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)/);
    // Le schede annidate possono restringersi sotto il loro contenuto.
    expect(bodiesFor(".fa-matchday-page .fa-tabs").join(";")).toMatch(/min-width:\s*0/);
    expect(bodiesFor(".fa-matchday-page .fa-tab-panel").join(";")).toMatch(/min-width:\s*0/);
  });

  it("styles.css: la barra dei campionati scorre in orizzontale e le schede non vanno a capo", () => {
    const bar = bodiesFor(".fa-matchday-competitions-tabs .fa-tablist").join(";");
    expect(bar).toMatch(/flex-wrap:\s*nowrap/);
    expect(bar).toMatch(/overflow-x:\s*auto/);
    expect(bodiesFor(".fa-matchday-competitions-tabs .fa-tab").join(";")).toMatch(/flex:\s*0 0 auto/);
  });

  it("styles.css: nessuna regola della pagina Turni fissa una larghezza da schermo largo", () => {
    for (const rule of cssRules(stylesCss)) {
      if (!/\.fa-matchday-(page|europei|europei-detail|competition|competitions-tabs|fixture)\b/.test(rule.selector)) {
        continue;
      }
      expect(rule.body, rule.selector).not.toMatch(/(?:^|[;\s])width\s*:\s*\d+(?:\.\d+)?(?:px|rem)/);
      expect(rule.body, rule.selector).not.toMatch(/(?:^|[;\s])min-width\s*:\s*(?:3[5-9]\d|[4-9]\d\d)px/);
    }
  });
});
