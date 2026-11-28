import {
  approvedModuleCatalog,
  type FantasyTurnDetail,
  type FantasyTurnSummary,
  type LineupContext,
  type LineupLockCountdown,
  type SessionUser,
} from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import stylesCss from "../styles.css?raw";

// 28/11, decisione di Rosario: una sola riga «Prossimo blocco». La fascia dell'intestazione
// (`header-lock-strip`, in AppLayout) resta; la seconda riga sotto il titolo di Turni e di
// Formazione non c'è più quando c'è il conto alla rovescia. Quando il conto non c'è («Turno non
// ancora aperto», «Turno saltato», «Formazione confermata») il testo di stato della pagina
// resta, perché su telefono la fascia lo nasconde. Il test monta l'app vera (intestazione +
// pagina), con un conto alla rovescia che riguarda proprio il turno mostrato dalla pagina: è il
// caso in cui prima le righe erano due.

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchLineupLockCountdownMock = vi.fn();
const fetchFantasyTurnsMock = vi.fn();
const fetchFantasyTurnMock = vi.fn();
const fetchMyLineupMock = vi.fn();

vi.mock("../api/auth", () => ({
  fetchMe: (...args: unknown[]) => fetchMeMock(...args),
  refresh: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../api/leagues", () => ({
  fetchCompetitions: vi.fn(),
  fetchMyLeagues: (...args: unknown[]) => fetchMyLeaguesMock(...args),
  fetchLineupLockCountdown: (...args: unknown[]) => fetchLineupLockCountdownMock(...args),
  fetchFantasyTurns: (...args: unknown[]) => fetchFantasyTurnsMock(...args),
  fetchFantasyTurn: (...args: unknown[]) => fetchFantasyTurnMock(...args),
  fetchMyLineup: (...args: unknown[]) => fetchMyLineupMock(...args),
  fetchFantasyTeams: vi.fn().mockResolvedValue([]),
  fetchH2HCalendar: vi.fn().mockResolvedValue(null),
  fetchPendingFixtures: vi.fn().mockResolvedValue([]),
  excludeFantasyTurnFixture: vi.fn(),
  reincludeFantasyTurnFixture: vi.fn(),
  excludeUnplayedFantasyTurnFixtures: vi.fn(),
  applyBestLineup: vi.fn(),
  copyPreviousLineupToDraft: vi.fn(),
  discardLineupDraft: vi.fn(),
  saveLineupDraft: vi.fn(),
  saveMyLineup: vi.fn(),
}));

vi.mock("../api/managerInvites", () => ({
  fetchPendingInviteCount: vi.fn().mockResolvedValue(0),
}));

vi.mock("../api/market", () => ({
  fetchTradeReplacements: vi.fn().mockResolvedValue([]),
}));

vi.mock("../api/notifications", () => ({
  fetchNotifications: vi.fn().mockResolvedValue({
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
    unreadCount: 0,
  }),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  fetchNotificationPreferences: vi.fn(),
  updateNotificationPreference: vi.fn(),
}));

import { AuthProvider } from "../auth/AuthContext";
import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { AppRoutes } from "../routes";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const USER: SessionUser = { id: "user-1", displayName: "Marco", globalRole: "member" };
const LEAGUE = { id: "league-1", name: "Lega Test", role: "member" };
const ROUND_ID = "turn-12";

function countdownFor(roundId: string): LineupLockCountdown {
  return {
    leagueId: "league-1",
    roundId,
    roundNumber: 12,
    roundStatus: "open",
    state: "counting_down",
    nextLockAt: new Date(Date.now() + 8 * 3_600_000).toISOString(),
    serverNow: new Date().toISOString(),
  };
}

/** Nessun conto alla rovescia: la risposta del server porta solo lo stato (e lo stato del turno). */
function idleCountdownFor(
  roundId: string,
  state: LineupLockCountdown["state"],
  roundStatus: string,
): LineupLockCountdown {
  return {
    leagueId: "league-1",
    roundId,
    roundNumber: 12,
    roundStatus,
    state,
    nextLockAt: null,
    serverNow: new Date().toISOString(),
  };
}

/** I tre testi che la pagina non deve perdere (su telefono la fascia in alto non li mostra). */
const IDLE_CASES = [
  { state: "turn_not_open", roundStatus: "scheduled", label: "Turno non ancora aperto" },
  { state: "turn_not_open", roundStatus: "skipped", label: "Turno saltato" },
  { state: "no_pending_lock", roundStatus: "open", label: "Formazione confermata" },
] as const;

const SUMMARY: FantasyTurnSummary = {
  id: ROUND_ID,
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
  fixtureCount: 0,
  generatedAt: "2026-11-27T08:00:00.000Z",
  modificationAllowed: true,
  matchStatus: "scheduled",
};

const DETAIL: FantasyTurnDetail = {
  ...SUMMARY,
  homologationStatus: "provisional",
  excludedFixtures: [],
  fixtures: [],
};

function lineupContext(): LineupContext {
  return {
    leagueId: "league-1",
    roundId: ROUND_ID,
    roundNumber: 12,
    kind: "weekend",
    cutoffAt: "2026-11-28T14:00:00.000Z",
    status: "open",
    effectiveStatus: "open",
    modificationAllowed: true,
    lineupLockMarginMinutes: 0,
    modules: approvedModuleCatalog(),
    roster: [],
    lineup: null,
    previousLineup: null,
    draft: null,
    copyAvailable: false,
    copyIssues: [],
    issues: [],
  };
}

async function flushAsync(rounds = 10): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

/** Quante volte il testo «Prossimo blocco» compare nella pagina intera. */
function occurrences(container: HTMLElement): number {
  return (container.textContent ?? "").split("Prossimo blocco").length - 1;
}

describe("Una sola riga «Prossimo blocco»: la fascia dell'intestazione (28/11, Rosario)", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function renderAppAt(path: string) {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: [path],
          children: createElement(ToastProvider, {
            children: createElement(AuthProvider, { children: createElement(AppRoutes) }),
          }),
        }),
      );
    });
    await flushAsync();
  }

  function expectOnlyHeaderStrip() {
    const strips = container.querySelectorAll('[data-testid="header-lock-strip"]');
    expect(strips).toHaveLength(1);
    expect(strips[0]?.textContent).toMatch(/Prossimo blocco\d{2}:\d{2}:\d{2}/);
    // Tutta la pagina: un solo «Prossimo blocco», ed è quello della fascia.
    expect(occurrences(container)).toBe(1);
    expect(container.querySelectorAll('[data-testid="lock-countdown"]')).toHaveLength(1);
    // Il corpo della pagina (fuori dall'intestazione) non ne ha.
    const main = container.querySelector("#main-content");
    expect(main).not.toBeNull();
    expect(main?.textContent ?? "").not.toContain("Prossimo blocco");
    expect(main?.querySelector('[data-testid="lock-countdown"]')).toBeNull();
  }

  beforeEach(() => {
    clearStoredSession();
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    fetchMeMock.mockReset().mockResolvedValue(USER);
    fetchMyLeaguesMock.mockReset().mockResolvedValue([LEAGUE]);
    fetchLineupLockCountdownMock.mockReset().mockResolvedValue(countdownFor(ROUND_ID));
    fetchFantasyTurnsMock.mockReset().mockResolvedValue([SUMMARY]);
    fetchFantasyTurnMock.mockReset().mockResolvedValue(DETAIL);
    fetchMyLineupMock.mockReset().mockResolvedValue(lineupContext());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
    document.body.classList.remove("fa-moves-docked");
    vi.unstubAllGlobals();
  });

  it("Turni: con il conto alla rovescia, «Prossimo blocco» c'è solo nella fascia in alto", async () => {
    await renderAppAt("/turni?tab=europei");

    // La pagina mostra proprio il turno del conto alla rovescia (il caso delle due righe).
    expect(container.querySelector('[data-testid="matchday-turn-detail"] h2')?.textContent).toBe("Turno 12");
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledWith("access-token", "league-1");
    expectOnlyHeaderStrip();
  });

  it("Formazione: con il conto alla rovescia, «Prossimo blocco» c'è solo nella fascia in alto", async () => {
    await renderAppAt("/formazione");

    expect(container.querySelector('[data-testid="wireframe-formation-success"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="formation-round"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="formation-lock-countdown"]')).toBeNull();
    // «Mosse usate N/M» resta: è un'altra informazione.
    expect(container.querySelector('[data-testid="formation-moves-badge"]')?.textContent).toMatch(
      /^Mosse usate \d+\/\d+$/,
    );
    expectOnlyHeaderStrip();
  });

  describe.each(IDLE_CASES)(
    "senza conto alla rovescia, «$label»: il testo di stato della pagina resta",
    ({ state, roundStatus, label }) => {
      beforeEach(() => {
        fetchLineupLockCountdownMock.mockResolvedValue(idleCountdownFor(ROUND_ID, state, roundStatus));
      });

      it("Turni: il testo c'è nella pagina e non compare nessun «Prossimo blocco»", async () => {
        await renderAppAt("/turni?tab=europei");

        expect(container.querySelector('[data-testid="matchday-turn-detail"] h2')?.textContent).toBe("Turno 12");
        const main = container.querySelector("#main-content");
        const note = main?.querySelector('[data-testid="lock-countdown"]');
        expect(note?.textContent).toBe(label);
        expect(note?.getAttribute("data-state")).toBe(state);
        expect(occurrences(container)).toBe(0);
      });

      it("Formazione: il testo c'è nella pagina e non compare nessun «Prossimo blocco»", async () => {
        await renderAppAt("/formazione");

        expect(container.querySelector('[data-testid="wireframe-formation-success"]')).not.toBeNull();
        const note = container.querySelector('#main-content [data-testid="formation-lock-countdown"]');
        expect(note?.textContent).toBe(label);
        expect(note?.getAttribute("data-state")).toBe(state);
        expect(occurrences(container)).toBe(0);
      });
    },
  );

  it("senza conto, la pagina di un altro turno non mostra il testo del turno di riferimento", async () => {
    // Come prima: il testo di stato riguarda il turno del conto alla rovescia, non quello scelto.
    fetchLineupLockCountdownMock.mockResolvedValue(idleCountdownFor("turn-13", "turn_not_open", "scheduled"));
    await renderAppAt("/turni?tab=europei");

    expect(container.querySelector('#main-content [data-testid="lock-countdown"]')).toBeNull();
  });

  it("Formazione, barra delle mosse agganciata: un solo «Prossimo blocco» alla volta (la barra prende il posto della fascia)", async () => {
    // Scorrendo, la riga delle mosse esce dalla vista: «Mosse N/M» e conto alla rovescia si uniscono in una
    // barra fissa e la fascia dell'intestazione si nasconde (non coesistono).
    class DockingObserver {
      constructor(private readonly callback: IntersectionObserverCallback) {}
      observe(target: Element) {
        this.callback(
          [
            {
              isIntersecting: false,
              target,
              boundingClientRect: { bottom: -40 } as DOMRectReadOnly,
            } as IntersectionObserverEntry,
          ],
          this as unknown as IntersectionObserver,
        );
      }
      disconnect() {}
      unobserve() {}
      takeRecords() {
        return [];
      }
    }
    vi.stubGlobal("IntersectionObserver", DockingObserver);

    await renderAppAt("/formazione");

    const dock = container.querySelector('[data-testid="formation-moves-dock"]');
    expect(dock).not.toBeNull();
    expect(document.body.classList.contains("fa-moves-docked")).toBe(true);
    expect(dock?.textContent).toMatch(/Prossimo blocco\d{2}:\d{2}:\d{2}/);
    expect(dock?.textContent).toMatch(/Mosse \d+\/\d+/);
    // In pagina ce ne sono due nel DOM (barra e fascia), ma la fascia è nascosta dallo stile:
    // sul computer sparisce, sul telefono resta il posto ma invisibile.
    const hide = stylesCss.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(hide).toMatch(/\.fa-moves-docked \.fa-lock-countdown-bar\s*\{\s*display:\s*none;/);
    expect(hide).toMatch(
      /\.fa-moves-docked \.fa-app-chrome > \.fa-lock-countdown-bar\s*\{[^}]*visibility:\s*hidden;/,
    );
  });
});
