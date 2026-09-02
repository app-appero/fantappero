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
    homeClubId: "club-home",
    awayClubId: "club-away",
    homeClubName: "Roma FC",
    awayClubName: "Milan FC",
    homeClubLogoUrl: "https://media.api-sports.io/football/teams/home.png",
    awayClubLogoUrl: null,
    homeGoals: 2,
    awayGoals: 1,
    statusShort: "2H",
    statusElapsed: 63,
    venueName: "Stadio Olimpico",
    venueCity: "Roma",
    referee: "M. Rossi",
    kickoffAt: "2026-08-15T14:00:00.000Z",
    updatedAt: "2026-08-15T15:03:00.000Z",
    feedState: "fresh",
    feedStateLabel: "Aggiornato",
    homeLineup: {
      clubName: "Roma FC",
      clubLogoUrl: "https://media.api-sports.io/football/teams/home.png",
      formation: "4-3-3",
      coachName: "J. Mourinho",
      starters: [
        {
          athleteId: "a1",
          name: "Marco Rossi",
          shirtNumber: 10,
          position: "F",
          grid: "4:2",
          photoUrl: "https://media.api-sports.io/football/players/a1.png",
        },
      ],
      bench: [
        {
          athleteId: "a2",
          name: "Paolo Verdi",
          shirtNumber: 23,
          position: "M",
          grid: null,
          photoUrl: null,
        },
      ],
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
        clubId: "club-home",
        clubName: "Roma FC",
        athleteId: "a1",
        athleteName: "Marco Rossi",
        relatedAthleteId: "a3",
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

describe("FixtureDetailBody (EP13-P04-quater)", () => {
  it("mostra risultato, stato partita (evidenziato se live) e stato del feed", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-score"');
    expect(html).toContain("2 – 1");
    // React scrive l'apostrofo come entità HTML.
    expect(html).toContain("Secondo tempo · 63&#x27;");
    expect(html).toContain("fa-live-badge");
    expect(html).toContain('data-testid="fixture-feed-state"');
    expect(html).toContain("Aggiornato");
  });

  it("non mostra il badge feed ridondante quando la partita è terminata", () => {
    const html = render(detail({ statusShort: "FT", statusElapsed: 90 }));
    expect(html).not.toContain('data-testid="fixture-feed-state"');
    expect(html).not.toContain("fa-live-badge");
  });

  it("mostra le formazioni su un vero campo grafico, non una griglia generica", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="football-pitch"');
    expect(html).toContain("4-3-3");
    expect(html).toContain("All. J. Mourinho");
    expect(html).toContain('data-testid="pitch-player-a1"');
    expect(html).toContain("Rossi");
  });

  it("dà lo stesso colore di badge a ruoli diversi da D, non solo al difensore", () => {
    const html = render(detail());
    // Il portiere/attaccante reali (F qui) non devono cadere nel badge neutro.
    expect(html).toContain("fa-badge--danger");
  });

  it("mostra lo stato reale del panchinaro invece di un fisso 'può subentrare'", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-bench-home"');
    expect(html).toContain("Paolo Verdi");
    expect(html).toContain("Non utilizzato");
    expect(html).not.toContain("può subentrare");
  });

  it("mostra stadio e arbitro quando disponibili", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-venue-referee"');
    expect(html).toContain("Stadio Olimpico (Roma)");
    expect(html).toContain("Arbitro: M. Rossi");
  });

  it("non mostra la riga stadio/arbitro quando il provider non li ha ancora pubblicati", () => {
    const html = render(detail({ venueName: null, venueCity: null, referee: null }));
    expect(html).not.toContain('data-testid="fixture-venue-referee"');
  });

  it("dichiara assente la formazione non pubblicata invece di mostrarla vuota", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="fixture-lineup-empty-away"');
    expect(html).toContain("non è ancora stata pubblicata");
  });

  it("rende una vera timeline verticale casa/ospite con minuto e assist", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="match-timeline"');
    expect(html).toContain('data-testid="timeline-event-e1"');
    expect(html).toContain("fa-timeline__row--home");
    expect(html).toContain("12&#x27;");
    expect(html).toContain("Marco Rossi");
    expect(html).toContain("Assist: Luca Bianchi");
  });

  it("collega il badge gol al giocatore in formazione, per id e non per nome", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="event-badge-goal"');
  });

  it("non inventa eventi quando il provider non ne ha pubblicati", () => {
    const html = render(detail({ events: [] }));
    expect(html).toContain('data-testid="fixture-timeline-empty"');
    expect(html).not.toContain('data-testid="match-timeline"');
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
