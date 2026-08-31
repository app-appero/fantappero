import type { AiLineupRun, H2HCalendar, H2HMatchupScore } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MatchdayH2HPanel } from "./MatchdayH2HPanel";
import { MemoryRouter } from "../router/simpleRouter";

const SLOT = "slot-1";

function result(overrides: Partial<H2HMatchupScore> = {}): H2HMatchupScore {
  return {
    homeScore: 72.5,
    awayScore: 68,
    homeFantasyGoals: 2,
    awayFantasyGoals: 1,
    outcome: "home",
    resultFinal: true,
    computedAt: "2026-08-20T18:30:00.000Z",
    ...overrides,
  };
}

function calendar(matchResult: H2HMatchupScore | null, matchupLive = false): H2HCalendar {
  return {
    id: "cal-1",
    leagueId: "lega-1",
    status: "confirmed",
    format: "single_round_robin",
    algorithmVersion: "v1",
    participantCount: 2,
    roundCount: 1,
    matchupCount: 1,
    byeCount: 0,
    generatedAt: "2026-08-01T10:00:00.000Z",
    confirmedAt: "2026-08-01T11:00:00.000Z",
    live: false,
    rounds: [
      {
        roundNumber: 1,
        fantasyRoundId: "turn-1",
        homologationStatus: "provisional",
        europeanTurnStatus: "locked",
        beforeLeagueCreation: false,
        matchups: [
          {
            slotId: SLOT,
            slotIndex: 0,
            isBye: false,
            homeUserId: "u1",
            homeDisplayName: "Marco",
            homeTeamName: "Roma FC",
            awayUserId: "u2",
            awayDisplayName: "Giulia",
            awayTeamName: "Milan FC",
            live: matchupLive,
            result: matchResult,
          },
        ],
      },
    ],
    summary: { message: "" },
  };
}

function render(matchResult: H2HMatchupScore | null, matchupLive = false): string {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: ["/turni"],
      children: createElement(MatchdayH2HPanel, {
        calendar: calendar(matchResult, matchupLive),
        loading: false,
        error: null,
        liveDegraded: false,
        canAdmin: false,
        onRetry: () => {},
      }),
    }),
  );
}

function renderAiAdmin(canAdmin: boolean, aiLineupRun: AiLineupRun | null = null): string {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: ["/turni"],
      children: createElement(MatchdayH2HPanel, {
        calendar: calendar(null),
        loading: false,
        error: null,
        liveDegraded: false,
        canAdmin,
        aiLineupRun,
        onGenerateAiLineups: () => {},
        onRetry: () => {},
      }),
    }),
  );
}

/** Testo del blocco punteggio, senza tag. */
function scoreText(html: string): string {
  const start = html.indexOf(`data-testid="h2h-score-${SLOT}"`);
  expect(start).toBeGreaterThan(-1);
  const end = html.indexOf("</dl>", start);
  return html.slice(start, end).replace(/<[^>]+>/g, " ");
}

describe("MatchdayH2HPanel — Punti e Gol fantasy espliciti (EP13-P02)", () => {
  it("nomina entrambe le grandezze invece dei numeri tra parentesi", () => {
    const html = render(result());
    const text = scoreText(html);

    expect(text).toContain("Gol fantasy");
    expect(text).toContain("2 – 1");
    expect(text).toContain("Punti");
    expect(text).toContain("72,5 – 68,0");
    // Il vecchio formato "2–1 (72.5 – 68.0)" non deve più comparire.
    expect(html).not.toContain("(72.5");
    expect(html).not.toContain("72.5");
  });

  it("usa la virgola decimale, non il punto", () => {
    expect(render(result())).toContain("72,5");
  });

  it("non trasforma un risultato assente in 0–0", () => {
    const html = render(null);
    const text = scoreText(html);

    expect(text).toContain("— – —");
    expect(text).not.toContain("0 – 0");
    expect(html).toContain("Risultato non ancora calcolato.");
    expect(html).toContain("In attesa");
  });

  it("non inventa i gol mancanti quando solo i punti sono noti", () => {
    const html = render(
      result({ homeFantasyGoals: null, awayFantasyGoals: null, resultFinal: false }),
    );
    const text = scoreText(html);

    expect(text).toContain("72,5 – 68,0");
    expect(text).toContain("— – —");
    expect(html).toContain("Alcuni valori non sono ancora disponibili per questo scontro.");
  });

  it("distingue provvisorio e finale", () => {
    expect(render(result({ resultFinal: false }))).toContain("Provvisorio / in attesa");
    expect(render(result({ resultFinal: false }), true)).toContain("LIVE / provvisorio");
    expect(render(result())).toContain("Finale");
  });

  it("mostra il pareggio con punti diversi nella stessa fascia gol", () => {
    const text = scoreText(
      render(
        result({
          homeScore: 71.5,
          awayScore: 66,
          homeFantasyGoals: 1,
          awayFantasyGoals: 1,
          outcome: "draw",
        }),
      ),
    );
    expect(text).toContain("1 – 1");
    expect(text).toContain("71,5 – 66,0");
  });

  it("espone un'etichetta accessibile che nomina le grandezze", () => {
    const html = render(result());
    expect(html).toContain("Gol fantasy 2 – 1. Punti 72,5 – 68,0");
  });
});

describe("MatchdayH2HPanel — comando amministrativo formazioni AI", () => {
  it("non espone il comando a un partecipante senza permessi admin", () => {
    const html = renderAiAdmin(false);
    expect(html).not.toContain("h2h-ai-admin");
    expect(html).not.toContain("Genera formazioni AI");
  });

  it("espone all'admin il comando per il turno fantasy selezionato", () => {
    const html = renderAiAdmin(true);
    expect(html).toContain('data-testid="h2h-ai-admin"');
    expect(html).toContain('data-testid="h2h-generate-ai-lineups"');
    expect(html).toContain("Genera formazioni AI");
    expect(html).toContain("Le formazioni umane e quelle già bloccate non vengono modificate");
  });

  it("mostra riepilogo e motivazione per ogni squadra", () => {
    const html = renderAiAdmin(true, {
      roundId: "turn-1",
      algorithmVersion: "ai-lineup-v1",
      dryRun: false,
      summary: "Formazioni AI generate: 1/2. Non generate: 1.",
      teams: [
        {
          fantasyTeamId: "ai-1",
          fantasyTeamName: "Robot Uno",
          outcome: "created",
          message: null,
          starters: 11,
          usedFallback: false,
        },
        {
          fantasyTeamId: "ai-2",
          fantasyTeamName: "Robot Due",
          outcome: "incomplete",
          message: "Rosa senza portiere disponibile.",
          starters: 0,
          usedFallback: true,
        },
      ],
    });

    expect(html).toContain("Formazioni AI generate: 1/2. Non generate: 1.");
    expect(html).toContain("Robot Uno");
    expect(html).toContain("Formazione creata");
    expect(html).toContain("Robot Due");
    expect(html).toContain("Rosa senza portiere disponibile.");
  });
});
