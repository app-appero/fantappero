import type { CalendarWindow, LeagueCalendarPlan } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CalendarWindowsPanel } from "./LeagueCalendarPanel";

function window(overrides: Partial<CalendarWindow> = {}): CalendarWindow {
  return {
    startAt: "2026-08-07T00:00:00.000Z",
    endAt: "2026-08-11T00:00:00.000Z",
    kind: "weekend",
    timezone: "Europe/Rome",
    fixtureCount: 28,
    minRequired: 25,
    eligible: true,
    reason: null,
    ...overrides,
  };
}

function plan(overrides: Partial<LeagueCalendarPlan> = {}): LeagueCalendarPlan {
  return {
    algorithmVersion: "adaptive_windows_v2",
    participantCount: 8,
    cycleLength: 7,
    cycleCount: 2,
    roundCount: 14,
    matchupCount: 56,
    byeCount: 0,
    eligibleWindowCount: 15,
    windowsFingerprint: "abc123",
    generatable: true,
    stale: false,
    rounds: [],
    windowsUsed: [window()],
    windowsDiscarded: [],
    summary: "2 cicli completi da 7 giornate su 15 finestre eleggibili.",
    ...overrides,
  };
}

function render(value: LeagueCalendarPlan): string {
  return renderToStaticMarkup(createElement(CalendarWindowsPanel, { plan: value }));
}

describe("CalendarWindowsPanel — diagnostica finestre (EP13-P03)", () => {
  it("mostra cicli, finestre eleggibili e versione algoritmo", () => {
    const html = render(plan());
    expect(html).toContain('data-testid="calendar-windows"');
    expect(html).toContain("2 cicli completi da 7 giornate");
    expect(html).toContain("adaptive_windows_v2");
    expect(html).toContain("Cicli completi");
  });

  it("elenca le finestre scartate con il motivo", () => {
    const html = render(
      plan({
        windowsDiscarded: [
          window({
            startAt: "2026-08-14T00:00:00.000Z",
            endAt: "2026-08-18T00:00:00.000Z",
            fixtureCount: 3,
            eligible: false,
            reason: "Soglia non raggiunta: 3 partite eleggibili su 25 richieste.",
          }),
        ],
      }),
    );
    expect(html).toContain('data-testid="calendar-windows-discarded"');
    expect(html).toContain("Soglia non raggiunta");
    expect(html).toContain("3/25 partite");
  });

  it("distingue una finestra avanzata da una sotto soglia", () => {
    const html = render(
      plan({
        windowsDiscarded: [
          window({
            startAt: "2026-09-04T00:00:00.000Z",
            endAt: "2026-09-08T00:00:00.000Z",
            eligible: true,
            reason:
              "Finestra eleggibile non utilizzata: le giornate rimaste non bastano a completare un altro ciclo.",
          }),
        ],
      }),
    );
    expect(html).toContain("non bastano a completare un altro ciclo");
    expect(html).toContain("28/25 partite");
  });

  it("segnala la preview non aggiornata", () => {
    expect(render(plan({ stale: true }))).toContain('data-testid="calendar-windows-stale"');
    expect(render(plan())).not.toContain('data-testid="calendar-windows-stale"');
  });

  it("spiega perché il calendario non è generabile", () => {
    const html = render(
      plan({
        generatable: false,
        cycleCount: 0,
        summary:
          "Finestre eleggibili insufficienti: ne servono almeno 7 per un ciclo completo, ne risultano 3.",
      }),
    );
    expect(html).toContain("ne servono almeno 7 per un ciclo completo");
  });

  it("usa il formato data italiano", () => {
    const html = render(
      plan({ windowsDiscarded: [window({ eligible: false, reason: "Soglia non raggiunta." })] }),
    );
    expect(html).toContain("07/08/2026");
  });
});
