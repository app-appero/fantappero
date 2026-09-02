import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  H2H_VALUE_UNAVAILABLE,
  describeH2HResult,
  formatFantasyGoals,
  formatFantasyPoints,
  h2hResultAriaLabel,
} from "./h2hScore.ts";
import type { H2HMatchupScore } from "./leagues.ts";

function score(overrides: Partial<H2HMatchupScore> = {}): H2HMatchupScore {
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

describe("formattazione punti e gol fantasy (EP13-P02)", () => {
  it("usa la virgola decimale italiana e una cifra fissa", () => {
    assert.equal(formatFantasyPoints(72.5), "72,5");
    assert.equal(formatFantasyPoints(68), "68,0");
    assert.equal(formatFantasyPoints(0), "0,0");
  });

  it("arrotonda alla prima cifra decimale senza perdere precisione visibile", () => {
    assert.equal(formatFantasyPoints(65.5), "65,5");
    assert.equal(formatFantasyPoints(71.94), "71,9");
  });

  it("mostra i gol fantasy come interi", () => {
    assert.equal(formatFantasyGoals(0), "0");
    assert.equal(formatFantasyGoals(3), "3");
  });

  it("non trasforma null in zero", () => {
    assert.equal(formatFantasyPoints(null), H2H_VALUE_UNAVAILABLE);
    assert.equal(formatFantasyGoals(null), H2H_VALUE_UNAVAILABLE);
    assert.equal(formatFantasyPoints(undefined), H2H_VALUE_UNAVAILABLE);
    assert.equal(formatFantasyGoals(Number.NaN), H2H_VALUE_UNAVAILABLE);
  });
});

describe("describeH2HResult (EP13-P02)", () => {
  it("espone entrambe le grandezze su una partita finalizzata", () => {
    const display = describeH2HResult(score());
    assert.equal(display.status, "final");
    assert.equal(display.statusLabel, "Finale");
    assert.equal(display.pointsLine, "72,5 – 68,0");
    assert.equal(display.goalsLine, "2 – 1");
    assert.equal(display.pointsAvailable, true);
    assert.equal(display.goalsAvailable, true);
    assert.equal(display.unavailableHint, null);
  });

  it("distingue il provvisorio dal finale", () => {
    const display = describeH2HResult(score({ resultFinal: false }));
    assert.equal(display.status, "provisional");
    assert.equal(display.statusLabel, "Provvisorio");
    // I numeri restano visibili anche se il risultato non è definitivo.
    assert.equal(display.pointsLine, "72,5 – 68,0");
  });

  it("gestisce il pareggio senza alterare i valori", () => {
    const display = describeH2HResult(
      score({
        homeScore: 70,
        awayScore: 70,
        homeFantasyGoals: 1,
        awayFantasyGoals: 1,
        outcome: "draw",
      }),
    );
    assert.equal(display.pointsLine, "70,0 – 70,0");
    assert.equal(display.goalsLine, "1 – 1");
  });

  it("mostra il pareggio in gol anche con punti diversi nella stessa fascia", () => {
    // Soglia 66–71,5 ⇒ 1 gol: punti diversi, stesso gol fantasy (league_scoring.md).
    const display = describeH2HResult(
      score({
        homeScore: 71.5,
        awayScore: 66,
        homeFantasyGoals: 1,
        awayFantasyGoals: 1,
        outcome: "draw",
      }),
    );
    assert.equal(display.pointsLine, "71,5 – 66,0");
    assert.equal(display.goalsLine, "1 – 1");
  });

  it("rende il confine esatto di fascia senza reinterpretarlo", () => {
    // 65,5 ⇒ 0 gol, 72 ⇒ 2 gol: il client mostra ciò che il backend ha calcolato.
    const display = describeH2HResult(
      score({
        homeScore: 65.5,
        awayScore: 72,
        homeFantasyGoals: 0,
        awayFantasyGoals: 2,
        outcome: "away",
      }),
    );
    assert.equal(display.pointsLine, "65,5 – 72,0");
    assert.equal(display.goalsLine, "0 – 2");
  });

  it("segnala l'assenza di risultato senza inventare uno 0–0", () => {
    const display = describeH2HResult(null);
    assert.equal(display.status, "pending");
    assert.equal(display.statusLabel, "In attesa");
    assert.equal(display.pointsAvailable, false);
    assert.equal(display.goalsAvailable, false);
    assert.equal(display.pointsLine, "— – —");
    assert.equal(display.goalsLine, "— – —");
    assert.equal(display.unavailableHint, "Risultato non ancora calcolato.");
  });

  it("gestisce un risultato parziale con un solo lato calcolato", () => {
    const display = describeH2HResult(
      score({ awayScore: null, awayFantasyGoals: null, resultFinal: false }),
    );
    assert.equal(display.pointsAvailable, false);
    assert.equal(display.goalsAvailable, false);
    assert.equal(display.pointsLine, "72,5 – —");
    assert.equal(display.goalsLine, "2 – —");
    assert.equal(
      display.unavailableHint,
      "Alcuni valori non sono ancora disponibili per questo scontro.",
    );
  });

  it("distingue punti noti da gol non ancora convertiti", () => {
    const display = describeH2HResult(
      score({ homeFantasyGoals: null, awayFantasyGoals: null, resultFinal: false }),
    );
    assert.equal(display.pointsAvailable, true);
    assert.equal(display.goalsAvailable, false);
    assert.equal(display.pointsLine, "72,5 – 68,0");
    assert.equal(display.goalsLine, "— – —");
  });

  it("costruisce un'etichetta accessibile che nomina le due grandezze", () => {
    const label = h2hResultAriaLabel(describeH2HResult(score()), "Roma FC", "Milan FC");
    assert.equal(
      label,
      "Roma FC contro Milan FC. Gol fantasy 2 – 1. Punti 72,5 – 68,0. Finale",
    );
  });
});
