import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { AdminListoneEntry } from "@fantappero/contracts";
import {
  VALUE_DETAIL_MAX_RESULTS,
  parseValueDetailBudget,
  valueDetailCandidates,
} from "./marketValueDetail.ts";

function entry(id: string, name: string, club: string | null): AdminListoneEntry {
  return {
    athleteId: id,
    canonicalName: name,
    seasonYear: 2026,
    officialRole: "P",
    providerPositionRaw: "Goalkeeper",
    mappingVersion: "v1.0.0",
    clubId: null,
    clubName: club,
  };
}

/** Come `foldSearchText` del listone, per quello che serve qui. */
const fold = (text: string): string =>
  text.toLocaleLowerCase("it-IT").normalize("NFD").replace(/[\u0300-\u036f]/g, "");

const LISTONE = [
  entry("1", "G. Donnarumma", "Manchester City"),
  entry("2", "J. Oblak", "Atletico Madrid"),
  entry("3", "P. Cuñat", "Levante"),
];

describe("Dettaglio del Valore: ricerca nel listone", () => {
  it("cerca per nome o club, senza accenti, da 2 lettere", () => {
    assert.deepEqual(valueDetailCandidates(LISTONE, "d", fold), []);
    assert.deepEqual(
      valueDetailCandidates(LISTONE, "cunat", fold).map((item) => item.athleteId),
      ["3"],
    );
    assert.deepEqual(
      valueDetailCandidates(LISTONE, " MANCHESTER ", fold).map((item) => item.athleteId),
      ["1"],
    );
    assert.deepEqual(valueDetailCandidates(LISTONE, "zz", fold), []);
  });

  it("propone al massimo pochi calciatori", () => {
    const many = Array.from({ length: 20 }, (_, index) => entry(String(index), `Rossi ${index}`, null));
    assert.equal(valueDetailCandidates(many, "rossi", fold).length, VALUE_DETAIL_MAX_RESULTS);
  });

  it("budget della lega: intero positivo", () => {
    assert.equal(parseValueDetailBudget("500"), 500);
    assert.equal(parseValueDetailBudget(" 1000 "), 1000);
    assert.equal(parseValueDetailBudget("0"), null);
    assert.equal(parseValueDetailBudget("12.5"), null);
    assert.equal(parseValueDetailBudget(""), null);
  });
});
