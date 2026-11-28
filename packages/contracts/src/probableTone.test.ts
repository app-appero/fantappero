import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { NO_INFO_LABEL, PITCH_HALO_LEGEND, pitchHaloOf, probableToneOf } from "./probableTone.ts";

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
      ["starter", "bench", "expelled", "unavailable", "none"],
    );
    assert.equal(PITCH_HALO_LEGEND.at(-1)?.label, NO_INFO_LABEL);
    assert.equal(NO_INFO_LABEL, "Nessuna informazione");
  });
});
