import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DOUBT_LABEL,
  DOUBT_LABEL_BG,
  HALO_COLOR,
  NO_INFO_LABEL,
  PITCH_HALO_LEGEND,
  haloToneOf,
  isProbableDoubt,
  pitchHalo,
} from "./pitchHalo.ts";

describe("pitchHalo (Rosario, 27/11)", () => {
  it("senza dato della formazione probabile l'alone è neutro, non assente", () => {
    assert.equal(pitchHalo(null), "none");
    assert.equal(pitchHalo(undefined), "none");
  });

  it("con il dato resta il colore di sempre", () => {
    for (const tone of ["starter", "bench", "expelled", "unavailable", "doubt"] as const) {
      assert.equal(pitchHalo(tone), tone);
    }
  });

  it("l'alone neutro ha un colore suo, diverso dal grigio dell'indisponibile", () => {
    assert.notEqual(HALO_COLOR.none, HALO_COLOR.unavailable);
  });

  it("la legenda ha la voce «Nessuna informazione», come sul sito", () => {
    assert.deepEqual(
      PITCH_HALO_LEGEND.map((item) => item.halo),
      ["starter", "bench", "expelled", "unavailable", "doubt", "none"],
    );
    assert.equal(PITCH_HALO_LEGEND.at(-1)?.label, NO_INFO_LABEL);
    assert.equal(NO_INFO_LABEL, "Nessuna informazione");
  });
});

/** Contrasto WCAG, come `packages/ui/src/accessibility/contrast.ts`. */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

describe("alone «In dubbio» (Rosario, 28/11)", () => {
  it("l'«in dubbio» del server è arancione, gli assenti certi no", () => {
    assert.equal(haloToneOf({ probableHint: "unavailable", probableAbsence: "injured", probableDoubt: true }), "doubt");
    assert.equal(haloToneOf({ probableHint: "unavailable", probableAbsence: "injured" }), "unavailable");
    assert.equal(
      haloToneOf({ probableHint: "unavailable", probableAbsence: "suspended", probableDoubt: true }),
      "expelled",
    );
    assert.equal(haloToneOf({ probableHint: "unavailable", probableDoubt: true, selectionBlocked: true }), "unavailable");
    assert.equal(isProbableDoubt({ probableHint: "starter", probableDoubt: true }), false);
  });

  it("stesso arancione e stessa voce del sito", () => {
    assert.equal(HALO_COLOR.doubt, "#ea580c");
    assert.equal(DOUBT_LABEL, "In dubbio");
    const labels = PITCH_HALO_LEGEND.map((item) => item.label);
    assert.equal(labels.indexOf("In dubbio"), labels.indexOf("Indisponibile") + 1);
  });

  it("si vede sugli sfondi chiari e scuri dell'app e si distingue dal giallo", () => {
    // Sfondi dell'app: tema scuro (pitch800/900/700) e chiaro (cloud50/100, bianco).
    for (const background of ["#0a0f22", "#080c1c", "#141a36", "#f2f6f8", "#e8eef2", "#ffffff"]) {
      assert.ok(contrast(HALO_COLOR.doubt, background) >= 3, `arancione su ${background}`);
    }
    assert.ok(contrast(HALO_COLOR.doubt, HALO_COLOR.bench) >= 2, "arancione e giallo distinti");
    assert.ok(contrast("#ffffff", DOUBT_LABEL_BG) >= 4.5, "nome bianco sull'arancione");
  });
});

