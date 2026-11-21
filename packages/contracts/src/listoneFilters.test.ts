import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  LISTONE_FILTER_ALL_LABEL,
  LISTONE_FILTER_LABEL,
  LISTONE_RESET_FILTERS_LABEL,
  NO_LISTONE_PLACE_FILTERS,
  compareListoneNames,
  filterListoneEntries,
  hasListonePlaceFilters,
  listoneClubOptions,
  listoneCompetitionOptions,
  listoneFilterChips,
  listoneFilterVisibility,
  listoneNameSortKey,
  listoneOptionAccessibilityLabel,
  listoneOptionLabel,
  listonePlayerCountLabel,
  normalizeListonePlaceFilters,
  removeListoneFilter,
  selectListoneClub,
  selectListoneCompetition,
  type ListoneFilterEntry,
  type ListoneFilters,
} from "./listoneFilters.ts";

const SERIE_A = { id: "c-ita", name: "Serie A" };
const PREMIER = { id: "c-eng", name: "Premier League" };
const LALIGA = { id: "c-esp", name: "La Liga" };

function entry(
  athleteId: string,
  canonicalName: string,
  effectiveRole: ListoneFilterEntry["effectiveRole"],
  club: { id: string; name: string } | null,
  competition: { id: string; name: string } | null,
): ListoneFilterEntry {
  return {
    athleteId,
    canonicalName,
    effectiveRole,
    clubId: club?.id ?? null,
    clubName: club?.name ?? null,
    competitionId: competition?.id ?? null,
    competitionName: competition?.name ?? null,
  };
}

const FIORENTINA = { id: "club-fio", name: "Fiorentina" };
const ATALANTA = { id: "club-ata", name: "Atalanta" };
const ARSENAL = { id: "club-ars", name: "Arsenal" };
const ATLETICO = { id: "club-atm", name: "Atlético Madrid" };
const ATHLETIC = { id: "club-ath", name: "Athletic Club" };

const listone: ListoneFilterEntry[] = [
  entry("1", "Dodô", "D", FIORENTINA, SERIE_A),
  entry("2", "M. Kean", "A", FIORENTINA, SERIE_A),
  entry("3", "D. De Gea", "P", FIORENTINA, SERIE_A),
  entry("4", "A. Lookman", "A", ATALANTA, SERIE_A),
  entry("5", "B. Saka", "A", ARSENAL, PREMIER),
  entry("6", "M. Ødegaard", "C", ARSENAL, PREMIER),
  entry("7", "J. Oblak", "P", ATLETICO, LALIGA),
  entry("8", "N. Williams", "A", ATHLETIC, LALIGA),
  entry("9", "Senza Club", "C", null, null),
];

const fold = listoneNameSortKey;

function filters(overrides: Partial<ListoneFilters> = {}): ListoneFilters {
  return { role: "all", query: "", onlyFree: false, competitionId: null, clubId: null, ...overrides };
}

function ids(rows: readonly ListoneFilterEntry[]): string[] {
  return rows.map((row) => row.athleteId);
}

describe("etichette dei filtri del listone (Rosario, 21/11)", () => {
  it("usa le parole della proposta", () => {
    assert.equal(LISTONE_FILTER_LABEL.competition, "Campionato");
    assert.equal(LISTONE_FILTER_LABEL.club, "Squadra");
    assert.equal(LISTONE_FILTER_ALL_LABEL.competition, "Tutti i campionati");
    assert.equal(LISTONE_FILTER_ALL_LABEL.club, "Tutte le squadre");
    assert.equal(LISTONE_RESET_FILTERS_LABEL, "Azzera filtri");
  });

  it("conta i calciatori al singolare e al plurale", () => {
    assert.equal(listonePlayerCountLabel(0), "0 calciatori");
    assert.equal(listonePlayerCountLabel(1), "1 calciatore");
    assert.equal(listonePlayerCountLabel(28), "28 calciatori");
  });

  it("mostra il conto nelle voci di menu e lo legge per esteso", () => {
    const option = { id: "club-fio", name: "Fiorentina", count: 28 };
    assert.equal(listoneOptionLabel(option), "Fiorentina (28)");
    assert.equal(listoneOptionAccessibilityLabel(option), "Fiorentina, 28 calciatori");
  });
});

describe("ordine alfabetico senza accenti", () => {
  it("mette i nomi con l'accento al loro posto, non in fondo", () => {
    const names = ["Zeta", "Élan", "ac Milan", "Atlético Madrid", "Athletic Club", "Ajax", "Brøndby"];
    assert.deepEqual([...names].sort(compareListoneNames), [
      "ac Milan",
      "Ajax",
      "Athletic Club",
      "Atlético Madrid",
      "Brøndby",
      "Élan",
      "Zeta",
    ]);
  });

  it("a parità di lettere tiene un ordine fisso", () => {
    assert.ok(compareListoneNames("Cadiz", "Cádiz") !== 0);
    assert.equal(compareListoneNames("Cadiz", "Cádiz"), -compareListoneNames("Cádiz", "Cadiz"));
    assert.equal(compareListoneNames("Inter", "Inter"), 0);
  });

  it("toglie accenti e maiuscole dalla chiave", () => {
    assert.equal(listoneNameSortKey("  Atlético  "), "atletico");
    assert.equal(listoneNameSortKey("Ødegaard"), "odegaard");
    assert.equal(listoneNameSortKey("Gießen"), "giessen");
  });
});

describe("listoneCompetitionOptions", () => {
  it("elenca solo i campionati presenti nel listone, in ordine, con i calciatori", () => {
    assert.deepEqual(listoneCompetitionOptions(listone), [
      { id: "c-esp", name: "La Liga", count: 2 },
      { id: "c-eng", name: "Premier League", count: 2 },
      { id: "c-ita", name: "Serie A", count: 4 },
    ]);
  });

  it("è vuoto con un backend che non manda il campionato", () => {
    const old = listone.map(({ competitionId: _id, competitionName: _name, ...rest }) => rest);
    assert.deepEqual(listoneCompetitionOptions(old), []);
  });
});

describe("listoneClubOptions", () => {
  it("elenca solo le squadre del campionato scelto, in ordine, con i calciatori", () => {
    assert.deepEqual(listoneClubOptions(listone, SERIE_A.id), [
      { id: "club-ata", name: "Atalanta", count: 1 },
      { id: "club-fio", name: "Fiorentina", count: 3 },
    ]);
  });

  it("senza campionato elenca tutte le squadre, accenti compresi al loro posto", () => {
    assert.deepEqual(
      listoneClubOptions(listone, null).map((option) => option.name),
      ["Arsenal", "Atalanta", "Athletic Club", "Atlético Madrid", "Fiorentina"],
    );
  });

  it("il conto non dipende da ruolo o ricerca: è sul listone intero", () => {
    const options = listoneClubOptions(listone, PREMIER.id);
    assert.deepEqual(options, [{ id: "club-ars", name: "Arsenal", count: 2 }]);
  });
});

describe("listoneFilterVisibility", () => {
  it("mostra Campionato e Squadra con più campionati", () => {
    assert.deepEqual(listoneFilterVisibility(listone), { competition: true, club: true });
  });

  it("con un campionato solo nasconde Campionato e mostra solo Squadra", () => {
    const onlySerieA = listone.filter((row) => row.competitionId === SERIE_A.id);
    assert.deepEqual(listoneFilterVisibility(onlySerieA), { competition: false, club: true });
  });

  it("con un backend più vecchio mostra solo Squadra", () => {
    const old = listone.map((row) => ({ ...row, competitionId: undefined, competitionName: undefined }));
    assert.deepEqual(listoneFilterVisibility(old), { competition: false, club: true });
    assert.equal(listoneClubOptions(old, null).length, 5);
  });

  it("senza club non mostra nemmeno Squadra", () => {
    assert.deepEqual(listoneFilterVisibility([entry("9", "Senza Club", "C", null, null)]), {
      competition: false,
      club: false,
    });
  });
});

describe("scelta di campionato e squadra", () => {
  it("scegliere un campionato azzera una squadra che non ci gioca", () => {
    const place = { competitionId: null, clubId: ARSENAL.id };
    assert.deepEqual(selectListoneCompetition(listone, place, SERIE_A.id), {
      competitionId: SERIE_A.id,
      clubId: null,
    });
  });

  it("scegliere il campionato della squadra la tiene", () => {
    const place = { competitionId: null, clubId: FIORENTINA.id };
    assert.deepEqual(selectListoneCompetition(listone, place, SERIE_A.id), {
      competitionId: SERIE_A.id,
      clubId: FIORENTINA.id,
    });
  });

  it("tornare a «Tutti i campionati» tiene la squadra", () => {
    const place = { competitionId: SERIE_A.id, clubId: FIORENTINA.id };
    assert.deepEqual(selectListoneCompetition(listone, place, null), {
      competitionId: null,
      clubId: FIORENTINA.id,
    });
  });

  it("una squadra fuori dal campionato scelto non si può scegliere", () => {
    const place = { competitionId: SERIE_A.id, clubId: null };
    assert.deepEqual(selectListoneClub(listone, place, ARSENAL.id), {
      competitionId: SERIE_A.id,
      clubId: null,
    });
    assert.deepEqual(selectListoneClub(listone, place, ATALANTA.id), {
      competitionId: SERIE_A.id,
      clubId: ATALANTA.id,
    });
  });

  it("riporta a «tutti» valori spariti o nascosti, e lascia uguale una scelta valida", () => {
    const onlySerieA = listone.filter((row) => row.competitionId === SERIE_A.id);
    assert.deepEqual(
      normalizeListonePlaceFilters(onlySerieA, { competitionId: SERIE_A.id, clubId: FIORENTINA.id }),
      { competitionId: null, clubId: FIORENTINA.id },
    );
    assert.deepEqual(normalizeListonePlaceFilters(listone, { competitionId: "c-sparito", clubId: "x" }), {
      competitionId: null,
      clubId: null,
    });
    const valid = { competitionId: PREMIER.id, clubId: ARSENAL.id };
    assert.equal(normalizeListonePlaceFilters(listone, valid), valid);
    assert.equal(normalizeListonePlaceFilters(listone, NO_LISTONE_PLACE_FILTERS), NO_LISTONE_PLACE_FILTERS);
  });
});

describe("etichette dei filtri attivi", () => {
  it("non ne mostra senza filtri", () => {
    assert.equal(hasListonePlaceFilters(NO_LISTONE_PLACE_FILTERS), false);
    assert.deepEqual(listoneFilterChips(listone, NO_LISTONE_PLACE_FILTERS), []);
  });

  it("mostra campionato e squadra, ognuno da togliere da solo", () => {
    const place = { competitionId: SERIE_A.id, clubId: FIORENTINA.id };
    assert.equal(hasListonePlaceFilters(place), true);
    assert.deepEqual(listoneFilterChips(listone, place), [
      { kind: "competition", label: "Serie A", removeLabel: "Togli il filtro Campionato: Serie A" },
      { kind: "club", label: "Fiorentina", removeLabel: "Togli il filtro Squadra: Fiorentina" },
    ]);
    assert.deepEqual(removeListoneFilter(place, "competition"), {
      competitionId: null,
      clubId: FIORENTINA.id,
    });
    assert.deepEqual(removeListoneFilter(place, "club"), { competitionId: SERIE_A.id, clubId: null });
  });

  it("mostra solo la squadra quando il campionato è «tutti»", () => {
    assert.deepEqual(
      listoneFilterChips(listone, { competitionId: null, clubId: ATLETICO.id }).map((chip) => chip.label),
      ["Atlético Madrid"],
    );
  });
});

describe("filterListoneEntries", () => {
  it("senza filtri tiene tutto il listone, anche chi non ha club", () => {
    assert.deepEqual(ids(filterListoneEntries(listone, filters(), { fold })), [
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
    ]);
  });

  it("filtra per campionato", () => {
    assert.deepEqual(ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id }), { fold })), [
      "1",
      "2",
      "3",
      "4",
    ]);
  });

  it("filtra per squadra", () => {
    assert.deepEqual(ids(filterListoneEntries(listone, filters({ clubId: ARSENAL.id }), { fold })), ["5", "6"]);
  });

  it("combina campionato, squadra e ruolo", () => {
    assert.deepEqual(
      ids(
        filterListoneEntries(
          listone,
          filters({ competitionId: SERIE_A.id, clubId: FIORENTINA.id, role: "A" }),
          { fold },
        ),
      ),
      ["2"],
    );
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, role: "P" }), { fold })),
      ["3"],
    );
  });

  it("combina la ricerca senza accenti con campionato e squadra", () => {
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: PREMIER.id, query: "odegaard" }), { fold })),
      ["6"],
    );
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, query: "odegaard" }), { fold })),
      [],
    );
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, query: "FIORENTINA" }), { fold })),
      ["1", "2", "3"],
    );
  });

  it("con «Solo disponibili» nasconde chi è in rosa, ma non durante una ricerca", () => {
    const ownedAthleteIds = new Set(["1", "5"]);
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, onlyFree: true }), { fold, ownedAthleteIds })),
      ["2", "3", "4"],
    );
    assert.deepEqual(
      ids(
        filterListoneEntries(listone, filters({ competitionId: SERIE_A.id, onlyFree: true, query: "dodo" }), {
          fold,
          ownedAthleteIds,
        }),
      ),
      ["1"],
    );
    assert.deepEqual(
      ids(filterListoneEntries(listone, filters({ clubId: ARSENAL.id, onlyFree: false }), { fold, ownedAthleteIds })),
      ["5", "6"],
    );
  });

  it("confronta il testo con la ripiegatura della piattaforma", () => {
    // Le app passano il loro `foldSearchText`, che ripara anche la codifica rovinata.
    const broken = [entry("10", "L. JovanoviÄ\u0087", "D", FIORENTINA, SERIE_A)];
    const repairingFold = (value: string) => listoneNameSortKey(value.replace("Ä\u0087", "ć"));
    assert.deepEqual(ids(filterListoneEntries(broken, filters({ query: "jovanovic" }), { fold })), []);
    assert.deepEqual(
      ids(filterListoneEntries(broken, filters({ query: "jovanovic" }), { fold: repairingFold })),
      ["10"],
    );
  });

  it("tiene il tipo delle voci passate", () => {
    const full = listone.map((row) => ({ ...row, photoUrl: null as string | null }));
    const rows = filterListoneEntries(full, filters({ clubId: ATALANTA.id }), { fold });
    assert.equal(rows[0]?.photoUrl, null);
    assert.equal(rows[0]?.canonicalName, "A. Lookman");
  });
});
