import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { LeagueListoneEntry } from "@fantappero/contracts";
import { filterListone, filterRosterSlots, foldSearchText, repairMojibake } from "./listoneFilter.ts";

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

  it("finds names with broken encoding without accents (QA 20-21/11)", () => {
    const broken = [
      ...listone,
      entry("6", "L. JovanoviÄ\u0087", "D", "Udinese"),
      entry("7", "R. ObriÄ\u0087", "C", "Atalanta"),
      entry("8", "D. PejiÄ\u008diÄ\u0087", "C", "Udinese"),
      entry("9", "N. KovaÄ\u008d", "A", "Lecce"),
      entry("10", "A. DembÃ©lÃ©", "A", "Paris"),
    ];
    assert.deepEqual(filterListone(broken, "all", "jovanovic").map((row) => row.athleteId), ["6"]);
    assert.deepEqual(filterListone(broken, "all", "Obrić").map((row) => row.athleteId), ["7"]);
    assert.deepEqual(filterListone(broken, "all", "pejicic").map((row) => row.athleteId), ["8"]);
    assert.deepEqual(filterListone(broken, "all", "kovac").map((row) => row.athleteId), ["9"]);
    assert.deepEqual(filterListone(broken, "all", "dembele").map((row) => row.athleteId), ["10"]);
  });
});

describe("repairMojibake", () => {
  it("repairs UTF-8 read as Latin-1 or Windows-1252, even twice", () => {
    assert.equal(repairMojibake("L. JovanoviÄ\u0087"), "L. Jovanović");
    assert.equal(repairMojibake("L. JovanoviÄ‡"), "L. Jovanović");
    assert.equal(repairMojibake("A. DembÃƒÂ©lÃƒÂ©"), "A. Dembélé");
    assert.equal(repairMojibake("Y. Nâ€™Dicka"), "Y. N’Dicka");
  });

  it("leaves correct names unchanged", () => {
    for (const name of [
      "A. Dembélé",
      "A. Bayındır",
      "E. İlkhan",
      "Š. Vrsaljko",
      "Ž. Ivanušec",
      "M. Ødegaard",
      "Ç. Söyüncü",
      "João Mário",
      "N’Dicka",
      "Nicolò Barella",
      "Ã Test",
      "",
    ]) {
      assert.equal(repairMojibake(name), name);
    }
    // Decodifica a un controllo (U+0085): resta com'è.
    assert.equal(repairMojibake("AÂ\u0085B"), "AÂ\u0085B");
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
