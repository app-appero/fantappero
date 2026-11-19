import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { withoutRoleQuotaExcess } from "./roleQuotaExcess.ts";

describe("withoutRoleQuotaExcess (QA 19/11, qa-02)", () => {
  // A. Adams (A11) è in esubero di ruolo: in rosa, ma non schierabile.
  const roster = [
    { athleteId: "A9" },
    { athleteId: "A10", exceedsRoleQuota: false },
    { athleteId: "A11", exceedsRoleQuota: true },
  ];

  it("la panchina della formazione non lo contiene: è uguale a quella salvata dal server", () => {
    const savedBench = ["A9", "A10"];
    // Quella che l'app costruiva con tutta la rosa: lui in coda, in tribuna.
    const fromRoster = ["A9", "A10", "A11"];
    assert.deepEqual(withoutRoleQuotaExcess(fromRoster, roster), savedBench);
  });

  it("toglie solo chi è in esubero e lascia gli altri nel loro ordine", () => {
    assert.deepEqual(withoutRoleQuotaExcess(["A11", "A10", "A9"], roster), ["A10", "A9"]);
    assert.deepEqual(withoutRoleQuotaExcess(["A9", "X1"], roster), ["A9", "X1"]);
  });

  it("senza nessuno in esubero non cambia niente", () => {
    assert.deepEqual(withoutRoleQuotaExcess(["A9", "A11"], []), ["A9", "A11"]);
    assert.deepEqual(withoutRoleQuotaExcess([], roster), []);
  });
});
