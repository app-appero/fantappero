import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { italianVarEventText } from "./providerEventText.ts";

describe("eventi VAR in italiano (QA 28/11, N6)", () => {
  it("i testi del fornitore sullo schermo «Partita»", () => {
    const cases: Array<[string, string]> = [
      ["Goal cancelled", "Gol annullato"],
      ["Goal Disallowed - offside", "Gol annullato · fuorigioco"],
      ["Goal Disallowed - handball", "Gol annullato · fallo di mano"],
      ["Goal Disallowed", "Gol annullato"],
      ["Goal confirmed", "Gol confermato"],
      ["Penalty confirmed", "Rigore confermato"],
      ["Penalty cancelled", "Rigore annullato"],
      ["Card upgrade", "Cartellino cambiato"],
      ["Red card cancelled", "Rosso annullato"],
    ];
    for (const [english, italian] of cases) {
      assert.equal(italianVarEventText(english), italian, english);
    }
  });

  it("maiuscole, trattini e spazi diversi non cambiano il risultato", () => {
    assert.equal(italianVarEventText("goal cancelled"), "Gol annullato");
    assert.equal(italianVarEventText("GOAL CANCELLED"), "Gol annullato");
    assert.equal(italianVarEventText("  Goal cancelled  "), "Gol annullato");
    assert.equal(italianVarEventText("Goal cancelled."), "Gol annullato");
    assert.equal(italianVarEventText("Goal Disallowed – offside"), "Gol annullato · fuorigioco");
    assert.equal(italianVarEventText("Goal Disallowed-offside"), "Gol annullato · fuorigioco");
    assert.equal(italianVarEventText("goal_disallowed - Handball"), "Gol annullato · fallo di mano");
    assert.equal(italianVarEventText("Penalty canceled"), "Rigore annullato");
  });

  it("un testo non riconosciuto resta com'è, senza inventare", () => {
    assert.equal(italianVarEventText("Goal Disallowed - foul"), "Goal Disallowed - foul");
    assert.equal(italianVarEventText("Check complete"), "Check complete");
    assert.equal(italianVarEventText("Gol annullato"), "Gol annullato");
  });

  it("senza dettaglio la riga dice «Revisione»", () => {
    assert.equal(italianVarEventText(null), "Revisione");
    assert.equal(italianVarEventText(undefined), "Revisione");
    assert.equal(italianVarEventText(""), "Revisione");
    assert.equal(italianVarEventText("   "), "Revisione");
  });
});
