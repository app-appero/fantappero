import assert from "node:assert/strict";
import { describe, it } from "node:test";
// L'app usa questi helper da `@fantappero/contracts`; il file non ha import e si carica dal sorgente.
import {
  LISTONE_FILTER_ALL_LABEL,
  LISTONE_FILTER_LABEL,
  filterListoneEntries,
  listoneClubOptions,
  listoneCompetitionOptions,
  listoneFilterVisibility,
  selectListoneCompetition,
  type ListoneFilterEntry,
  type ListoneFilters,
} from "../../../../../packages/contracts/src/listoneFilters.ts";
import { foldSearchText } from "./listoneFilter.ts";
import {
  listoneSheetRows,
  listoneSheetTitle,
  listoneTriggerAccessibilityLabel,
} from "./listoneFilterSheet.ts";

const SERIE_A = { id: "c-ita", name: "Serie A" };
const PREMIER = { id: "c-eng", name: "Premier League" };

function entry(
  athleteId: string,
  canonicalName: string,
  effectiveRole: ListoneFilterEntry["effectiveRole"],
  club: { id: string; name: string },
  competition: { id: string; name: string },
): ListoneFilterEntry {
  return {
    athleteId,
    canonicalName,
    effectiveRole,
    clubId: club.id,
    clubName: club.name,
    competitionId: competition.id,
    competitionName: competition.name,
  };
}

const FIORENTINA = { id: "fio", name: "Fiorentina" };
const ATALANTA = { id: "ata", name: "Atalanta" };
const ARSENAL = { id: "ars", name: "Arsenal" };

const listone: ListoneFilterEntry[] = [
  entry("1", "Dodô", "D", FIORENTINA, SERIE_A),
  entry("2", "L. JovanoviÄ\u0087", "D", FIORENTINA, SERIE_A),
  entry("3", "M. Kean", "A", FIORENTINA, SERIE_A),
  entry("4", "A. Lookman", "A", ATALANTA, SERIE_A),
  entry("5", "M. Ødegaard", "C", ARSENAL, PREMIER),
];

function filters(overrides: Partial<ListoneFilters> = {}): ListoneFilters {
  return { role: "all", query: "", onlyFree: false, competitionId: null, clubId: null, ...overrides };
}

describe("foglio Squadra nella ricerca del listone dell'app (Rosario, 21/11)", () => {
  it("mette «Tutte le squadre» in cima, poi i club del campionato con i calciatori", () => {
    const rows = listoneSheetRows(listoneClubOptions(listone, SERIE_A.id), null, LISTONE_FILTER_ALL_LABEL.club);
    assert.deepEqual(
      rows.map((row) => [row.label, row.count, row.selected]),
      [
        ["Tutte le squadre", 4, true],
        ["Atalanta", 1, false],
        ["Fiorentina", 3, false],
      ],
    );
    assert.equal(rows[2]?.accessibilityLabel, "Fiorentina, 3 calciatori");
    assert.equal(rows[1]?.accessibilityLabel, "Atalanta, 1 calciatore");
  });

  it("segna la scelta, e una scelta che non c'è più vale «tutti»", () => {
    const options = listoneClubOptions(listone, SERIE_A.id);
    assert.deepEqual(
      listoneSheetRows(options, FIORENTINA.id, "Tutte le squadre").filter((row) => row.selected).map((row) => row.value),
      [FIORENTINA.id],
    );
    assert.deepEqual(
      listoneSheetRows(options, ARSENAL.id, "Tutte le squadre").filter((row) => row.selected).map((row) => row.value),
      [null],
    );
  });

  it("il foglio Campionato elenca i campionati della lega", () => {
    const rows = listoneSheetRows(listoneCompetitionOptions(listone), SERIE_A.id, LISTONE_FILTER_ALL_LABEL.competition);
    assert.deepEqual(
      rows.map((row) => row.label),
      ["Tutti i campionati", "Premier League", "Serie A"],
    );
    assert.equal(rows.find((row) => row.selected)?.value, SERIE_A.id);
  });

  it("titolo e lettori di schermo dicono cosa si sceglie", () => {
    assert.equal(listoneSheetTitle(LISTONE_FILTER_LABEL.club, "Serie A"), "Squadra · Serie A");
    assert.equal(listoneSheetTitle(LISTONE_FILTER_LABEL.club, null), "Squadra");
    assert.equal(
      listoneTriggerAccessibilityLabel(LISTONE_FILTER_LABEL.club, "Tutte le squadre"),
      "Squadra: Tutte le squadre. Tocca per cambiare",
    );
  });
});

describe("ricerca nel listone dell'app con i filtri condivisi", () => {
  it("usa la ricerca dell'app: senza accenti e con la codifica riparata, dentro il campionato", () => {
    const fold = foldSearchText;
    const ids = (rows: readonly ListoneFilterEntry[]) => rows.map((row) => row.athleteId);
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, query: "jovanovic" }), { fold })),
      ["2"],
    );
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, query: "dodo" }), { fold })),
      ["1"],
    );
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, query: "odegaard" }), { fold })),
      [],
    );
  });

  it("scegliere un campionato azzera la squadra di un altro campionato", () => {
    assert.deepEqual(selectListoneCompetition(listone, { competitionId: null, clubId: ARSENAL.id }, SERIE_A.id), {
      competitionId: SERIE_A.id,
      clubId: null,
    });
  });

  it("con un campionato solo il foglio Campionato non c'è", () => {
    assert.deepEqual(
      listoneFilterVisibility(listone.filter((row) => row.competitionId === SERIE_A.id)),
      { competition: false, club: true },
    );
  });
});
