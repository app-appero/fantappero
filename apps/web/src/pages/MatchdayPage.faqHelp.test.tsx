import type { FantasyTurnDetail, FantasyTurnSummary, SessionUser } from "@fantappero/contracts";
import { FAQ_HELP, faqHelpItem } from "@fantappero/contracts";
import { ToastProvider } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  // Fantallenatore della lega (non admin): vede i turni, non «Escludi».
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

function summary(id: string, number: number, status: FantasyTurnSummary["status"]): FantasyTurnSummary {
  return {
    id,
    leagueId: "league-1",
    number,
    kind: "weekend",
    windowStartAt: `2026-11-${10 + number}T22:00:00.000Z`,
    windowEndAt: `2026-11-${12 + number}T22:00:00.000Z`,
    opensAt: null,
    closesAt: null,
    cutoffAt: `2026-11-${11 + number}T14:00:00.000Z`,
    status,
    effectiveStatus: status,
    skipReason: status === "skipped" ? "Soglia non raggiunta: 1 squadra sotto il 75% dei titolari." : null,
    fixtureCount: 0,
    generatedAt: "2026-11-01T08:00:00.000Z",
    modificationAllowed: status !== "skipped",
    matchStatus: "scheduled",
  };
}

function detail(base: FantasyTurnSummary): FantasyTurnDetail {
  return { ...base, homologationStatus: "provisional", fixtures: [], excludedFixtures: [] };
}

// Il turno 11 (sosta per le nazionali) è saltato ed è quello mostrato all'apertura.
const SKIPPED = summary("turn-11", 11, "skipped");
const OPEN = summary("turn-12", 12, "open");


describe("Turni › Turni europei: il «?» accanto a «Turno saltato» (FAQ 1.4)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const q = <T extends Element>(testId: string, scope: ParentNode = container) =>
    scope.querySelector(`[data-testid="${testId}"]`) as T | null;
  const dialog = () => document.body.querySelector<HTMLElement>('[role="dialog"]');

  async function renderTurni() {
    fetchFantasyTurnsMock.mockResolvedValue([SKIPPED, OPEN]);
    fetchFantasyTurnMock.mockImplementation(async (_token: string, _league: string, turnId: string) =>
      detail(turnId === OPEN.id ? OPEN : SKIPPED),
    );
    await act(async () => {
      root.render(
        createElement(BrowserRouter, {
          children: createElement(ToastProvider, { children: createElement(MatchdayPage) }),
        }),
      );
    });
  }

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    window.history.replaceState(null, "", "/turni?tab=europei");
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnsMock.mockReset();
    fetchFantasyTurnMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
    window.history.replaceState(null, "", "/");
  });

  it("il «?» sta accanto a «Turno saltato» nel dettaglio e accanto al menù dei turni", async () => {
    await renderTurni();
    expect(q<HTMLSelectElement>("matchday-turn-select")?.value).toBe("turn-11");

    const lede = q("matchday-turn-detail")!.querySelector(".fa-matchday-lede")!;
    expect(lede.textContent).toContain("Stato: Turno saltato");
    const detailHelp = lede.querySelector<HTMLButtonElement>('[data-testid="matchday-turn-skipped-help"]');
    expect(detailHelp).not.toBeNull();
    expect(detailHelp?.getAttribute("aria-label")).toBe("Perché un turno è saltato?");
    // Subito dopo la scritta, sulla stessa riga.
    expect(lede.querySelector("strong")?.nextElementSibling).toBe(detailHelp);

    const toolbar = q("matchday-turn-list")!.querySelector(".fa-matchday-toolbar")!;
    expect(toolbar.classList.contains("fa-matchday-toolbar--help")).toBe(true);
    const menuHelp = q<HTMLButtonElement>("matchday-turn-select-help", toolbar);
    expect(menuHelp?.getAttribute("aria-label")).toBe("Perché un turno è saltato?");
    const selectedOption = q<HTMLSelectElement>("matchday-turn-select")!.selectedOptions[0];
    expect(selectedOption?.textContent).toBe("Turno 11 — Turno saltato");
  });

  it("toccando il «?» si apre la risposta «Perché un turno è saltato?» con il link alla pagina", async () => {
    await renderTurni();
    await act(async () => q<HTMLButtonElement>("matchday-turn-skipped-help")!.click());

    const opened = dialog();
    expect(opened).not.toBeNull();
    const title = document.getElementById(opened!.getAttribute("aria-labelledby") ?? "");
    expect(title?.textContent).toBe("Perché un turno è «saltato»?");
    expect(opened!.textContent).toContain(faqHelpItem(FAQ_HELP.skippedTurn).answer[0]);
    expect(opened!.textContent).toContain("la tua lega può averne scelta un'altra, la trovi in «Regolamento»");
    const link = q<HTMLAnchorElement>("matchday-turn-skipped-help-all", opened!)!;
    expect(link.textContent?.replace(/\s/g, " ")).toBe("Tutte le domande frequenti ›");
    expect(link.getAttribute("href")).toBe("/domande-frequenti?domanda=turno-saltato");

    await act(async () => {
      link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
    });
    expect(`${window.location.pathname}${window.location.search}`).toBe("/domande-frequenti?domanda=turno-saltato");
    expect(dialog()).toBeNull();
  });

  it("anche il «?» del menù apre la stessa risposta; «Ho capito» la chiude", async () => {
    await renderTurni();
    await act(async () => q<HTMLButtonElement>("matchday-turn-select-help")!.click());
    expect(dialog()?.textContent).toContain("Perché un turno è «saltato»?");
    await act(async () => q<HTMLButtonElement>("matchday-turn-select-help-close", dialog()!)!.click());
    expect(dialog()).toBeNull();
  });

  it("su un turno che non è saltato il «?» non c'è", async () => {
    await renderTurni();
    const select = q<HTMLSelectElement>("matchday-turn-select")!;
    await act(async () => {
      select.value = "turn-12";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(q("matchday-turn-detail")?.querySelector("h2")?.textContent).toBe("Turno 12");
    expect(q("matchday-turn-skipped-help")).toBeNull();
    expect(q("matchday-turn-select-help")).toBeNull();
    expect(q("matchday-turn-list")!.querySelector(".fa-matchday-toolbar--help")).toBeNull();
  });
});
