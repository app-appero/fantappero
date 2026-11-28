import assert from "node:assert/strict";
import { describe, it } from "node:test";
// Lo stesso testo che l'app prende da `@fantappero/contracts` (qui dal sorgente).
import {
  lockCountdownIdleLabel,
  type LineupLockCountdownState,
} from "../../../../packages/contracts/src/fantasyLineups.ts";
import { showsPageLockNote } from "./pageLockNote.ts";

// 28/11, decisione di Rosario: con il conto alla rovescia in corso la riga «Prossimo blocco»
// è una sola (la fascia sotto l'intestazione) e Formazione e Turni non la ripetono; senza
// conto resta il testo di stato della schermata, come prima.

type Countdown = { roundId: string | null; state: LineupLockCountdownState };

function countdown(state: LineupLockCountdownState, roundId: string | null = "turn-12"): Countdown {
  return { roundId, state };
}

describe("Formazione e Turni, app: il testo di stato del blocco (28/11)", () => {
  it("con il conto alla rovescia in corso la schermata non ripete la riga: c'è solo la fascia", () => {
    assert.equal(showsPageLockNote(countdown("counting_down"), "turn-12"), false);
  });

  it("senza conto, nel turno del conto, il testo di stato resta: «Turno non ancora aperto»", () => {
    const state = countdown("turn_not_open");
    assert.equal(showsPageLockNote(state, "turn-12"), true);
    assert.equal(lockCountdownIdleLabel(state.state, "scheduled"), "Turno non ancora aperto");
  });

  it("senza conto, nel turno del conto, il testo di stato resta: «Turno saltato»", () => {
    const state = countdown("turn_not_open");
    assert.equal(showsPageLockNote(state, "turn-12"), true);
    assert.equal(lockCountdownIdleLabel(state.state, "skipped"), "Turno saltato");
  });

  it("senza conto, nel turno del conto, il testo di stato resta: «Formazione confermata»", () => {
    const state = countdown("no_pending_lock");
    assert.equal(showsPageLockNote(state, "turn-12"), true);
    assert.equal(lockCountdownIdleLabel(state.state, "open"), "Formazione confermata");
  });

  it("anche «Rosa non ancora assegnata» resta come prima", () => {
    const state = countdown("no_roster");
    assert.equal(showsPageLockNote(state, "turn-12"), true);
    assert.equal(lockCountdownIdleLabel(state.state, "open"), "Rosa non ancora assegnata");
  });

  it("come prima, il testo sta solo nel turno a cui il conto si riferisce", () => {
    assert.equal(showsPageLockNote(countdown("turn_not_open"), "turn-13"), false);
    // «Nessun turno attivo» non ha un turno: nessuna schermata di turno lo mostrava.
    assert.equal(showsPageLockNote(countdown("no_active_turn", null), "turn-12"), false);
    assert.equal(showsPageLockNote(null, "turn-12"), false);
  });
});
