import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { DOUBT_LABEL, NO_INFO_LABEL, PITCH_HALO_LEGEND, isProbableDoubt, pitchHaloOf, probableToneOf } from "./probableTone.ts";

describe("alone in campo (Rosario, 27/11)", () => {
  it("senza dato della formazione probabile l'alone è neutro, non assente", () => {
    // Cissè, De Winter, Norton-Cuffy, Gabriel: nessun indizio dal server.
    assert.equal(probableToneOf({ probableHint: null }), null);
    assert.equal(pitchHaloOf({ probableHint: null }), "none");
    assert.equal(pitchHaloOf({}), "none");
  });

  it("con il dato resta il colore di sempre", () => {
    assert.equal(pitchHaloOf({ probableHint: "starter" }), "starter");
    assert.equal(pitchHaloOf({ probableHint: "bench" }), "bench");
    assert.equal(pitchHaloOf({ probableHint: "unavailable", probableAbsence: "injured" }), "unavailable");
    assert.equal(pitchHaloOf({ probableHint: "unavailable", probableAbsence: "suspended" }), "expelled");
    // Senza voto sicuro (es. nessuna partita) è grigio anche senza formazione probabile.
    assert.equal(pitchHaloOf({ probableHint: null, selectionBlocked: true }), "unavailable");
  });

  it("la legenda ha una voce per ogni alone, «Nessuna informazione» compresa", () => {
    assert.deepEqual(
      PITCH_HALO_LEGEND.map((item) => item.halo),
      ["starter", "bench", "expelled", "unavailable", "doubt", "none"],
    );
    assert.equal(PITCH_HALO_LEGEND.at(-1)?.label, NO_INFO_LABEL);
    assert.equal(NO_INFO_LABEL, "Nessuna informazione");
  });
});

describe("alone «In dubbio» (Rosario, 28/11)", () => {
  it("l'«in dubbio» del server diventa arancione, non più grigio", () => {
    const row = { probableHint: "unavailable", probableAbsence: "injured", probableDoubt: true } as const;
    assert.equal(isProbableDoubt(row), true);
    assert.equal(probableToneOf(row), "doubt");
    assert.equal(pitchHaloOf(row), "doubt");
  });

  it("senza il campo nuovo (backend vecchio) resta grigio come prima", () => {
    assert.equal(pitchHaloOf({ probableHint: "unavailable", probableAbsence: "other" }), "unavailable");
    assert.equal(pitchHaloOf({ probableHint: "unavailable", probableDoubt: false }), "unavailable");
  });

  it("un assente certo non diventa mai arancione", () => {
    // Bloccato (nessun voto sicuro) o squalificato: vince l'assenza certa.
    assert.equal(
      pitchHaloOf({ probableHint: "unavailable", probableDoubt: true, selectionBlocked: true }),
      "unavailable",
    );
    assert.equal(
      pitchHaloOf({ probableHint: "unavailable", probableAbsence: "suspended", probableDoubt: true }),
      "expelled",
    );
    // Il dubbio vale solo per un assente: un titolare probabile resta verde.
    assert.equal(pitchHaloOf({ probableHint: "starter", probableDoubt: true }), "starter");
  });

  it("la legenda ha la voce «In dubbio» dopo «Indisponibile»", () => {
    const labels = PITCH_HALO_LEGEND.map((item) => item.label);
    assert.equal(DOUBT_LABEL, "In dubbio");
    assert.equal(labels.indexOf("In dubbio"), labels.indexOf("Indisponibile") + 1);
    assert.equal(PITCH_HALO_LEGEND.length, 6);
  });
});
