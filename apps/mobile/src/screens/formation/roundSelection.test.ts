import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { resolveDefaultEuropeanTurn } from "../../../../../packages/contracts/src/fantasyTurns.ts";
import { formationRoundToLoad } from "./roundSelection.ts";

const turns = [
  { id: "t1", matchStatus: "completed" },
  { id: "t2", matchStatus: "completed" },
  { id: "t3", matchStatus: "scheduled" },
  { id: "t4", matchStatus: "scheduled" },
] as const;

describe("Formazione: tirando per aggiornare resta il turno scelto (corsa M3, 22/11)", () => {
  it("senza una scelta apre il turno di default di Turni", () => {
    assert.equal(formationRoundToLoad(turns, "", resolveDefaultEuropeanTurn(turns))?.id, "t3");
    assert.equal(formationRoundToLoad(turns, null, resolveDefaultEuropeanTurn(turns))?.id, "t3");
  });

  it("il turno scelto da «Cambia turno» resta dopo l'aggiornamento", () => {
    assert.equal(formationRoundToLoad(turns, "t1", resolveDefaultEuropeanTurn(turns))?.id, "t1");
    assert.equal(formationRoundToLoad(turns, "t4", resolveDefaultEuropeanTurn(turns))?.id, "t4");
  });

  it("se il turno scelto non c'è più torna al default", () => {
    assert.equal(formationRoundToLoad(turns, "altra-lega", resolveDefaultEuropeanTurn(turns))?.id, "t3");
    assert.equal(formationRoundToLoad([], "t1", resolveDefaultEuropeanTurn([])), null);
  });

  it("la Formazione ricorda la scelta e la azzera al cambio di lega", () => {
    const source = readFileSync(new URL("../FormationScreen.tsx", import.meta.url), "utf8");
    assert.match(source, /formationRoundToLoad\(\s*list,\s*pickedRoundIdRef\.current,\s*resolveDefaultEuropeanTurn\(list\),?\s*\)/);
    assert.match(source, /async function selectRound\(roundId: string\) \{\n\s*pickedRoundIdRef\.current = roundId;/);
    assert.match(source, /setTargetTeamId\(""\);\n(?:\s*\/\/.*\n)?\s*pickedRoundIdRef\.current = "";\n\s*\}, \[activeLeagueId\]\);/);
  });
});
