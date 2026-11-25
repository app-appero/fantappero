import type { H2HPlayerScore, H2HSideLineup } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SideBlock } from "./MatchupDetailPage";
import { RosterVersus } from "./MatchupSideParts";

function player(overrides: Partial<H2HPlayerScore> & Pick<H2HPlayerScore, "athleteId" | "name">): H2HPlayerScore {
  return {
    role: "D",
    fantasyScore: null,
    fixtureStatusLabel: "Terminata",
    scoreFinal: true,
    isEffectiveStarter: true,
    isBench: false,
    ...overrides,
  };
}

function side(overrides: Partial<H2HSideLineup> = {}): H2HSideLineup {
  return {
    fantasyTeamId: "team-a",
    teamName: "Casa FC",
    displayName: "Marco",
    module: "4-3-3",
    lineupSource: "effective",
    totalScore: 13.5,
    fantasyGoals: 0,
    starters: [
      player({
        athleteId: "out",
        name: "Bastoni",
        isEffectiveStarter: false,
        replacedByAthleteId: "in",
        replacedByName: "Darmian",
      }),
      player({ athleteId: "s2", name: "Acerbi", fantasyScore: 6 }),
    ],
    bench: [
      player({
        athleteId: "in",
        name: "Darmian",
        fantasyScore: 7.5,
        isBench: true,
        enteredForAthleteId: "out",
        enteredForName: "Bastoni",
      }),
      player({ athleteId: "unused", name: "De Vrij", fantasyScore: 9, isBench: true, isEffectiveStarter: false }),
    ],
    ...overrides,
  };
}

describe("Scontro: sostituzioni automatiche a turno concluso (QA 24-25/11)", () => {
  it("sotto il campo mostra chi è entrato e per chi, col suo voto", () => {
    const html = renderToStaticMarkup(createElement(SideBlock, { side: side(), title: "home" }));
    expect(html).toContain("Entrati dalla panchina");
    expect(html).toContain('data-testid="matchup-auto-subs-home"');
    expect(html).toContain('data-testid="matchup-auto-sub-in"');
    expect(html).toContain("Entrato per Bastoni");
    expect(html).toContain('data-testid="matchup-auto-sub-score-in">7,5<');
    // Il panchinaro non entrato non finisce fra i subentrati.
    expect(html).not.toContain('data-testid="matchup-auto-sub-unused"');
  });

  it("senza sostituzioni non aggiunge la sezione", () => {
    const plain = side({
      starters: [player({ athleteId: "s2", name: "Acerbi", fantasyScore: 6 })],
      bench: [player({ athleteId: "b1", name: "De Vrij", isBench: true, isEffectiveStarter: false })],
    });
    const html = renderToStaticMarkup(createElement(SideBlock, { side: plain, title: "home" }));
    expect(html).not.toContain("Entrati dalla panchina");
    expect(html).not.toContain("Entrato per");
  });

  it("squadra senza formazione: niente modulo, e a turno concluso 0 punti", () => {
    const empty = side({ module: "4-3-3", starters: [], bench: [], totalScore: null, lineupSource: "submitted" });
    const concluded = renderToStaticMarkup(createElement(SideBlock, { side: empty, title: "away", roundConcluded: true }));
    expect(concluded).not.toContain("4-3-3");
    expect(concluded).toContain("Nessuna formazione schierata: 0 punti.");
    expect(concluded).not.toContain("non ha ancora una formazione");

    const open = renderToStaticMarkup(createElement(SideBlock, { side: empty, title: "away" }));
    expect(open).toContain("Questa squadra non ha ancora una formazione per il turno.");

    const versus = renderToStaticMarkup(createElement(RosterVersus, { home: side(), away: empty }));
    expect(versus).toContain("4-3-3"); // il modulo di chi ha schierato resta
    expect(versus.match(/4-3-3/g)).toHaveLength(1);
  });

  it("nella vista affiancata il titolare resta S.V. «uscito» e il panchinaro «entrato per»", () => {
    const html = renderToStaticMarkup(createElement(RosterVersus, { home: side(), away: side({ teamName: "Ospiti" }) }));
    expect(html).toContain("Uscito (S.V.) · entra Darmian");
    expect(html).toContain("Entrato per Bastoni");
  });
});
