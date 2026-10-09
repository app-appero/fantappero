import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { LeagueListoneEntry } from "@fantappero/contracts";
import { filterListone } from "./listoneFilter.ts";

function entry(
  athleteId: string,
  canonicalName: string,
  effectiveRole: LeagueListoneEntry["effectiveRole"],
  clubName: string | null,
): LeagueListoneEntry {
  return {
    athleteId,
    canonicalName,
    effectiveRole,
    clubName,
  } as LeagueListoneEntry;
}

const listone = [
  entry("1", "A. Abdi", "D", "Nice"),
  entry("2", "A. Adams", "A", "Venezia"),
  entry("3", "G. Donnarumma", "P", "Paris"),
];

describe("filterListone", () => {
  it("keeps every player on the Tutti tab", () => {
    assert.deepEqual(
      filterListone(listone, "all", "").map((row) => row.athleteId),
      ["1", "2", "3"],
    );
  });

  it("filters by role tab", () => {
    assert.deepEqual(
      filterListone(listone, "A", "").map((row) => row.canonicalName),
      ["A. Adams"],
    );
  });

  it("matches name or club without case", () => {
    assert.deepEqual(
      filterListone(listone, "all", "nice").map((row) => row.athleteId),
      ["1"],
    );
    assert.deepEqual(
      filterListone(listone, "D", "abdi").map((row) => row.athleteId),
      ["1"],
    );
    assert.deepEqual(filterListone(listone, "P", "venezia"), []);
  });

  it("hides owned players only when the free filter is on and the search is empty", () => {
    const owned = new Set(["2"]);
    assert.deepEqual(
      filterListone(listone, "all", "", true, owned).map((row) => row.athleteId),
      ["1", "3"],
    );
    assert.deepEqual(
      filterListone(listone, "A", "adams", true, owned).map((row) => row.athleteId),
      ["2"],
    );
  });
});
