import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { rosterDepartureNotices, savedStarterSlotIds } from "./savedLineup.ts";

const NOTICE =
  "N. Zortea non è più nella tua rosa: è stato tolto dalla formazione, scegli chi mettere al suo posto.";

describe("rosterDepartureNotices", () => {
  it("prende solo gli avvisi di chi non è più in rosa", () => {
    assert.deepEqual(
      rosterDepartureNotices([
        { code: "lineup_athlete_left_roster", message: NOTICE },
        { code: "bench_incomplete", message: "Tutti i calciatori in rosa devono essere schierati: mancano 1 in panchina." },
      ]),
      [NOTICE],
    );
  });

  it("senza issues non c'è nessun avviso", () => {
    assert.deepEqual(rosterDepartureNotices(undefined), []);
    assert.deepEqual(rosterDepartureNotices([]), []);
  });
});

describe("savedStarterSlotIds", () => {
  it("lascia vuoto il posto del titolare tolto, gli altri restano al loro posto", () => {
    // Il terzo posto (un difensore) era di chi non è più in rosa.
    const starters = ["P1", "D1", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"].map((athleteId, index) => ({
      athleteId,
      sortOrder: index < 2 ? index : index + 1,
    }));
    assert.deepEqual(savedStarterSlotIds(starters, 11), ["P1", "D1", "", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"]);
  });

  it("una formazione completa resta nell'ordine salvato", () => {
    const ids = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
    assert.deepEqual(
      savedStarterSlotIds(ids.map((athleteId, sortOrder) => ({ athleteId, sortOrder })), 11),
      ids,
    );
  });

  it("un sortOrder fuori modulo o doppio va nel primo posto libero", () => {
    assert.deepEqual(
      savedStarterSlotIds(
        [
          { athleteId: "P1", sortOrder: 0 },
          { athleteId: "D1", sortOrder: 0 },
          { athleteId: "D2", sortOrder: 20 },
        ],
        4,
      ),
      ["P1", "D1", "D2", ""],
    );
  });
});
