import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { HALO_COLOR, NO_INFO_LABEL, PITCH_HALO_LEGEND, pitchHalo } from "./pitchHalo.ts";

describe("pitchHalo (Rosario, 27/11)", () => {
  it("senza dato della formazione probabile l'alone è neutro, non assente", () => {
    assert.equal(pitchHalo(null), "none");
    assert.equal(pitchHalo(undefined), "none");
  });

  it("con il dato resta il colore di sempre", () => {
    for (const tone of ["starter", "bench", "expelled", "unavailable"] as const) {
      assert.equal(pitchHalo(tone), tone);
    }
  });

  it("l'alone neutro ha un colore suo, diverso dal grigio dell'indisponibile", () => {
    assert.notEqual(HALO_COLOR.none, HALO_COLOR.unavailable);
  });

  it("la legenda ha la voce «Nessuna informazione», come sul sito", () => {
    assert.deepEqual(
      PITCH_HALO_LEGEND.map((item) => item.halo),
      ["starter", "bench", "expelled", "unavailable", "none"],
    );
    assert.equal(PITCH_HALO_LEGEND.at(-1)?.label, NO_INFO_LABEL);
    assert.equal(NO_INFO_LABEL, "Nessuna informazione");
  });
});
