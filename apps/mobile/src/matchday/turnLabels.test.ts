import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  TURN_DISPLAY_LABEL,
  resolveTurnDisplayStates,
} from "../../../../packages/contracts/src/fantasyTurns.ts";
import { europeanTurnOptionLabel, formationTurnOptionLabel, turnSkipReason } from "./turnLabels.ts";

const REASON = "Soglia non raggiunta: 20 partite eleggibili su 25";

const skipped = { number: 12, status: "skipped", effectiveStatus: "skipped", matchStatus: "scheduled", skipReason: REASON } as const;
const upcoming = { number: 13, status: "scheduled", effectiveStatus: "scheduled", matchStatus: "scheduled", skipReason: null } as const;

const readScreen = (name: string) => readFileSync(new URL(`../screens/${name}`, import.meta.url), "utf8");

describe("Turni europei: motivo del turno saltato (corsa M3, 22/11)", () => {
  it("il turno saltato porta il motivo dell'API", () => {
    const [state] = resolveTurnDisplayStates([skipped]);
    assert.equal(state, "skipped");
    assert.equal(turnSkipReason(skipped, "skipped"), REASON);
  });

  it("nessun motivo per un turno non saltato o senza motivo", () => {
    assert.equal(turnSkipReason(upcoming, "next"), null);
    // Un motivo rimasto su un turno che non è saltato non si mostra.
    assert.equal(turnSkipReason({ skipReason: REASON }, "completed"), null);
    assert.equal(turnSkipReason({ skipReason: "  " }, "skipped"), null);
    assert.equal(turnSkipReason({ skipReason: null }, "skipped"), null);
  });

  it("nel menù dei turni il motivo segue lo stato", () => {
    assert.equal(
      europeanTurnOptionLabel(skipped, "skipped", TURN_DISPLAY_LABEL),
      `Turno 12 — Turno saltato (${REASON})`,
    );
    assert.equal(europeanTurnOptionLabel(upcoming, "next", TURN_DISPLAY_LABEL), "Turno 13 — Prossimo");
  });

  it("la schermata Turni usa il motivo nel menù e nel dettaglio", () => {
    const source = readScreen("MatchdayScreen.tsx");
    assert.match(source, /europeanTurnOptionLabel\(turn, turnDisplayStates\[index\] \?\? "upcoming", TURN_DISPLAY_LABEL\)/);
    assert.match(source, /turnSkipReason\(selected, selectedDisplayState\)/);
    assert.match(source, /testID="matchday-turn-skip-reason"/);
  });
});

describe("Formazione › Strumenti › Cambia turno (corsa M3, 22/11)", () => {
  // Come l'API sui turni 1-10 della lega di prova: ciclo di vita ancora `scheduled`
  // (turni nati dopo le loro partite), ma partite tutte finite.
  const played = (number: number) =>
    ({ number, status: "scheduled", effectiveStatus: "scheduled", matchStatus: "completed", skipReason: null }) as const;
  const turns = [played(1), played(2), played(10), { ...upcoming, number: 11 }, { ...upcoming, number: 12 }];

  it("i turni già giocati si leggono «Completato», non «Programmato»", () => {
    const states = resolveTurnDisplayStates(turns, new Date("2026-11-22T12:00:00Z"));
    const labels = turns.map((turn, index) =>
      formationTurnOptionLabel(turn, states[index] ?? "upcoming", TURN_DISPLAY_LABEL),
    );
    assert.deepEqual(labels, [
      "Turno 1 (Completato)",
      "Turno 2 (Completato)",
      "Turno 10 (Completato)",
      "Turno 11 (Prossimo)",
      "Turno 12 (Da disputare)",
    ]);
    assert.ok(labels.every((label) => !label.includes("Programmato")));
  });

  it("la Formazione usa lo stato mostrato in Turni, non effectiveStatus", () => {
    const source = readScreen("FormationScreen.tsx");
    assert.match(source, /formationTurnOptionLabel\(turn, turnDisplayStates\[index\] \?\? "upcoming", TURN_DISPLAY_LABEL\)/);
    assert.match(source, /resolveTurnDisplayStates\(turns, lockNow\)/);
    assert.doesNotMatch(source, /labelFantasyTurnStatus\(turn\.effectiveStatus\)/);
  });
});
