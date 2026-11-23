import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { leagueHomeCompetitionsHint, leagueHomeStatHintLines } from "./leagueHomeStats.ts";

const FIVE = [
  { name: "La Liga" },
  { name: "Premier League" },
  { name: "Serie A" },
  { name: "Bundesliga" },
  { name: "Ligue 1" },
];

describe("Home lega, scheda «Campionati» (QA notte 21→22/11)", () => {
  it("elenca tutti i campionati, uno per riga", () => {
    const hint = leagueHomeCompetitionsHint(FIVE);
    assert.deepEqual(hint.split("\n"), ["La Liga", "Premier League", "Serie A", "Bundesliga", "Ligue 1"]);
    assert.ok(!hint.includes("…"));
  });

  it("senza campionati mostra il trattino", () => {
    assert.equal(leagueHomeCompetitionsHint([]), "—");
    assert.equal(leagueHomeCompetitionsHint([{ name: "  " }]), "—");
  });

  it("solo la scheda Campionati va a capo, le altre restano su una riga", () => {
    assert.equal(leagueHomeStatHintLines("Campionati"), undefined);
    for (const label of ["Partecipanti", "Crediti", "Rosa"]) {
      assert.equal(leagueHomeStatHintLines(label), 1, label);
    }
  });

  it("la Home lega usa l'elenco intero e non tronca più il suggerimento", () => {
    const source = readFileSync(new URL("../screens/LeagueHomeScreen.tsx", import.meta.url), "utf8");
    assert.match(source, /leagueHomeCompetitionsHint\(league\.competitions\)/);
    assert.match(source, /numberOfLines=\{leagueHomeStatHintLines\(label \?\? ""\)\}/);
    assert.doesNotMatch(source, /competitions\.map\(\(row\) => row\.name\)\.join\(" · "\)/);
  });
});
