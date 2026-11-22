import type { LeagueCalendar, LeagueCalendarRosterCheck, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";

const fetchAdminMock = vi.fn();
const rosterCheckMock = vi.fn();
const generateMock = vi.fn();
const confirmMock = vi.fn();

vi.mock("../api/leagues", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/leagues")>();
  return {
    calendarRosterIssuesFromError: actual.calendarRosterIssuesFromError,
    fetchLeagueCalendarAdmin: (...args: unknown[]) => fetchAdminMock(...args),
    fetchLeagueCalendarRosterCheck: (...args: unknown[]) => rosterCheckMock(...args),
    generateLeagueCalendar: (...args: unknown[]) => generateMock(...args),
    confirmLeagueCalendar: (...args: unknown[]) => confirmMock(...args),
    ensureFantasyTurns: vi.fn(),
  };
});
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { CalendarActionModal, LeagueCalendarPanel } from "./LeagueCalendarPanel";

const USER: SessionUser = { id: "admin-1", displayName: "Rosario", globalRole: "member" };

const DRAFT: LeagueCalendar = {
  id: "cal-1",
  leagueId: "league-1",
  status: "draft",
  format: "single_round_robin",
  algorithmVersion: "adaptive_windows_v2",
  participantCount: 4,
  roundCount: 3,
  matchupCount: 6,
  byeCount: 0,
  generatedAt: "2026-11-22T10:00:00.000Z",
  confirmedAt: null,
  summary: { message: "Anteprima calendario: conferma per associarlo alla lega." },
  rounds: [],
};

const ISSUES: LeagueCalendarRosterCheck = {
  valid: false,
  teams: [
    {
      teamId: "team-x",
      teamName: "Squadra X",
      issues: ["Difensori 10 su 11", "Attaccanti 11 su 10"],
      lineupBlocked: false,
    },
  ],
};

describe("LeagueCalendarPanel — «Genera calendario» con rose non in regola (Rosario 22/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = <T extends HTMLElement = HTMLElement>(testId: string) =>
    container.querySelector<T>(`[data-testid="${testId}"]`);

  async function render() {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/giornata"],
          children: createElement(LeagueCalendarPanel, {
            leagueId: "league-1",
            isDemoMode: false,
            search: "",
          }),
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

  beforeEach(() => {
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    for (const mock of [fetchAdminMock, rosterCheckMock, generateMock, confirmMock]) {
      mock.mockReset();
    }
    fetchAdminMock.mockResolvedValue(null);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("con le rose in regola mostra la conferma normale e genera senza forzare", async () => {
    rosterCheckMock.mockResolvedValue({ valid: true, teams: [] });
    generateMock.mockResolvedValue(DRAFT);
    await render();

    await click("league-calendar-generate");
    expect(byTestId("league-calendar-modal-confirm")?.textContent).toContain(
      "Vuoi generare il calendario?",
    );
    expect(byTestId("league-calendar-modal-warning")).toBeNull();
    expect(byTestId("league-calendar-modal-proceed")?.textContent).toBe("Genera calendario");
    expect(byTestId("league-calendar-modal-cancel")?.textContent).toBe("Annulla");

    await click("league-calendar-modal-proceed");
    expect(generateMock).toHaveBeenCalledWith("access-token", "league-1", { force: false });
    expect(byTestId("league-calendar-modal-proceed")).toBeNull();
    expect(byTestId("league-calendar-success")?.textContent).toContain("6 incontri su 3 giornate");
  });

  it("con le rose non in regola mostra squadre e problemi e «Genera comunque» forza", async () => {
    rosterCheckMock.mockResolvedValue(ISSUES);
    generateMock.mockResolvedValue(DRAFT);
    await render();

    await click("league-calendar-generate");
    const warning = byTestId("league-calendar-modal-warning")?.textContent ?? "";
    expect(byTestId("league-calendar-modal-issues")?.textContent).toContain(
      "Squadra X: Difensori 10 su 11, Attaccanti 11 su 10",
    );
    expect(warning).toContain("Puoi generare comunque il calendario");
    expect(warning).toContain("i calciatori in esubero restano in rosa ma non potranno essere schierati");
    expect(byTestId("league-calendar-modal-blocked")).toBeNull();
    expect(byTestId("league-calendar-modal-proceed")?.textContent).toBe("Genera comunque");

    await click("league-calendar-modal-cancel");
    expect(byTestId("league-calendar-modal-proceed")).toBeNull();
    expect(generateMock).not.toHaveBeenCalled();

    await click("league-calendar-generate");
    await click("league-calendar-modal-proceed");
    expect(generateMock).toHaveBeenCalledWith("access-token", "league-1", { force: true });
  });

  it("se le rose cambiano dopo la verifica, l'errore del server porta all'avviso", async () => {
    rosterCheckMock.mockResolvedValue({ valid: true, teams: [] });
    generateMock
      .mockRejectedValueOnce(
        new ApiError("Alcune rose non sono in regola.", 400, "league_rosters_invalid", {
          teams: ISSUES.teams,
        }),
      )
      .mockResolvedValueOnce(DRAFT);
    await render();

    await click("league-calendar-generate");
    await click("league-calendar-modal-proceed");
    expect(byTestId("league-calendar-modal-issues")?.textContent).toContain("Squadra X");
    expect(byTestId("league-calendar-action-error")).toBeNull();

    await click("league-calendar-modal-proceed");
    expect(generateMock).toHaveBeenLastCalledWith("access-token", "league-1", { force: true });
  });

  it("«Conferma calendario» passa dallo stesso avviso e conferma comunque", async () => {
    fetchAdminMock.mockResolvedValue(DRAFT);
    rosterCheckMock.mockResolvedValue(ISSUES);
    confirmMock.mockResolvedValue({ ...DRAFT, status: "confirmed" });
    await render();

    await click("league-calendar-confirm");
    expect(byTestId("league-calendar-modal-warning")?.textContent).toContain(
      "Puoi confermare comunque il calendario",
    );
    expect(byTestId("league-calendar-modal-proceed")?.textContent).toBe("Conferma comunque");
    await click("league-calendar-modal-proceed");
    expect(confirmMock).toHaveBeenCalledWith("access-token", "league-1", { force: true });
  });
});

describe("CalendarActionModal", () => {
  it("avvisa che una rosa incompleta non può schierare la formazione", () => {
    const html = renderToStaticMarkup(
      createElement(CalendarActionModal, {
        state: {
          action: "generate",
          phase: "ready",
          teams: [
            ...ISSUES.teams,
            {
              teamId: "team-y",
              teamName: "Squadra Y",
              issues: ["Rosa incompleta: 34 su 35"],
              lineupBlocked: true,
            },
          ],
        },
        working: false,
        onCancel: () => undefined,
        onProceed: () => undefined,
      }),
    );
    expect(html).toContain("Squadra Y");
    expect(html).toContain('data-testid="league-calendar-modal-blocked"');
    expect(html).toContain("Squadra Y invece non potrà schierare la formazione");
  });

  it("mostra la verifica in corso con il bottone disattivato", () => {
    const html = renderToStaticMarkup(
      createElement(CalendarActionModal, {
        state: { action: "generate", phase: "checking", teams: [] },
        working: false,
        onCancel: () => undefined,
        onProceed: () => undefined,
      }),
    );
    expect(html).toContain("Verifica delle rose in corso");
    expect(html).toMatch(/data-testid="league-calendar-modal-proceed"[^>]*disabled|disabled[^>]*data-testid="league-calendar-modal-proceed"/);
  });
});
