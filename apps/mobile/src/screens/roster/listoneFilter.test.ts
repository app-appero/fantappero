import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { LeagueListoneEntry } from "@fantappero/contracts";
import { filterListone, filterRosterSlots, foldSearchText } from "./listoneFilter.ts";

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

  it("ignores accents and case in the search (QA 18/11)", () => {
    const accented = [...listone, entry("4", "A. Dembélé", "A", "Paris"), entry("5", "M. Ødegaard", "C", "Arsenal")];
    assert.deepEqual(
      filterListone(accented, "all", "dembele").map((row) => row.athleteId),
      ["4"],
    );
    assert.deepEqual(
      filterListone(accented, "all", "ODEGAARD").map((row) => row.athleteId),
      ["5"],
    );
    assert.deepEqual(
      filterListone(accented, "all", "Dembélé").map((row) => row.athleteId),
      ["4"],
    );
  });

  it("folds accents, case and spaces", () => {
    assert.equal(foldSearchText("  Çalhanoğlu "), "calhanoglu");
    assert.equal(foldSearchText("Müller"), "muller");
  });
});

describe("filterRosterSlots", () => {
  const slots = [
    { athleteId: "1", athleteName: "K. Lomónaco", clubName: "Independiente" },
    { athleteId: "2", athleteName: "A. Simón", clubName: "Bilbao" },
    { athleteId: "3", athleteName: "H. Bellerín", clubName: "Betis" },
    { athleteId: "4", athleteName: "G. Donnarumma", clubName: "Paris" },
    { athleteId: "5", athleteName: null, clubName: null },
  ];

  it("ignores accents and case in the roster search (QA 19/11)", () => {
    assert.deepEqual(filterRosterSlots(slots, "lomonaco").map((slot) => slot.athleteId), ["1"]);
    assert.deepEqual(filterRosterSlots(slots, "simon").map((slot) => slot.athleteId), ["2"]);
    assert.deepEqual(filterRosterSlots(slots, "BELLERIN").map((slot) => slot.athleteId), ["3"]);
    assert.deepEqual(filterRosterSlots(slots, "Bellerín").map((slot) => slot.athleteId), ["3"]);
  });

  it("matches the club too", () => {
    assert.deepEqual(filterRosterSlots(slots, "betis").map((slot) => slot.athleteId), ["3"]);
  });

  it("keeps every slot when the search is empty or blank", () => {
    assert.equal(filterRosterSlots(slots, "").length, slots.length);
    assert.equal(filterRosterSlots(slots, "   ").length, slots.length);
  });
});
