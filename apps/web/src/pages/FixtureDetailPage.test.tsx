import type { FixtureLiveDetail } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { FixtureDetailBody, statusLabel } from "./FixtureDetailPage";

function detail(overrides: Partial<FixtureLiveDetail> = {}): FixtureLiveDetail {
  return {
    fixtureId: "fx-1",
    turnId: "turn-1",
    leagueId: "lega-1",
    providerId: 1035055,
    competitionName: "Premier League",
    homeClubName: "Roma FC",
    awayClubName: "Milan FC",
    homeGoals: 2,
    awayGoals: 1,
    statusShort: "2H",
    statusElapsed: 63,
    kickoffAt: "2026-08-15T14:00:00.000Z",
    updatedAt: "2026-08-15T15:03:00.000Z",
    feedState: "fresh",
    feedStateLabel: "Aggiornato",
    homeLineup: {
      clubName: "Roma FC",
      formation: "4-3-3",
      starters: [
        { athleteId: "a1", name: "Marco Rossi", shirtNumber: 10, position: "F", grid: null },
      ],
      bench: [{ athleteId: "a2", name: "Paolo Verdi", shirtNumber: 23, position: "M", grid: null }],
    },
    awayLineup: null,
    events: [
      {
        id: "e1",
        minuteElapsed: 12,
        minuteExtra: null,
        minuteLabel: "12'",
        eventType: "Goal",
        eventDetail: "Normal Goal",
        scoringKind: "goal",
        clubName: "Roma FC",
        athleteName: "Marco Rossi",
        relatedAthleteName: "Luca Bianchi",
        comments: null,
      },
    ],
    ...overrides,
  };
}

function render(value: FixtureLiveDetail): string {
  return renderToStaticMarkup(createElement(FixtureDetailBody, { detail: value }));
}

describe("statusLabel — stati partita in italiano (EP13-P04)", () => {
  it("traduce gli stati principali", () => {
    expect(statusLabel("NS", null)).toBe("Non iniziata");
    expect(statusLabel("HT", null)).toBe("Intervallo");
    expect(statusLabel("PEN", null)).toBe("Finita ai rigori");
    expect(statusLabel("SUSP", null)).toBe("Sospesa");
    expect(statusLabel("PST", null)).toBe("Rinviata");
  });

  it("aggiunge il minuto quando è noto", () => {
    expect(statusLabel("2H", 63)).toBe("Secondo tempo · 63'");
  });

  it("non inventa una traduzione per uno stato sconosciuto", () => {
    expect(statusLabel("XYZ", null)).toBe("XYZ");
  });
});

describe("FixtureDetailBody (EP13-P04)", () => {
  it("mostra risultato, stato partita e stato del feed", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-score"');
    expect(html).toContain("2 – 1");
    // React scrive l'apostrofo come entità HTML.
    expect(html).toContain("Secondo tempo · 63&#x27;");
    expect(html).toContain('data-testid="fixture-feed-state"');
    expect(html).toContain("Aggiornato");
  });

  it("mostra titolari, panchina e modulo", () => {
    const html = render(detail());
    expect(html).toContain("4-3-3");
    expect(html).toContain("10. Marco Rossi (F)");
    expect(html).toContain("23. Paolo Verdi");
  });

  it("dichiara assente la formazione non pubblicata invece di mostrarla vuota", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-lineup-empty-away"');
    expect(html).toContain("non è ancora stata pubblicata");
  });

  it("rende la cronologia con minuto, marcatore e assist", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-timeline"');
    expect(html).toContain("12&#x27;");
    expect(html).toContain("Marco Rossi");
    expect(html).toContain("assist Luca Bianchi");
  });

  it("non inventa eventi quando il provider non ne ha pubblicati", () => {
    const html = render(detail({ events: [] }));
    expect(html).toContain('data-testid="fixture-timeline-empty"');
    expect(html).not.toContain('data-testid="fixture-timeline"');
  });

  it("segnala un feed fermo senza nascondere il risultato noto", () => {
    const html = render(detail({ feedState: "stale", feedStateLabel: "Dati fermi" }));
    expect(html).toContain("Dati fermi");
    expect(html).toContain("2 – 1");
  });

  it("non trasforma un punteggio assente in zero", () => {
    const html = render(detail({ homeGoals: null, awayGoals: null, statusShort: "NS" }));
    expect(html).toContain("— – —");
    expect(html).not.toContain("0 – 0");
  });
});
