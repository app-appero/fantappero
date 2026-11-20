import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { leagueNextStepRoute } from "./leagueNextStep.ts";

describe("leagueNextStepRoute", () => {
  it("in configurazione l'admin va all'amministrazione della lega, non alla formazione", () => {
    assert.deepEqual(leagueNextStepRoute("admin"), { kind: "admin" });
  });

  it("le altre fasi aprono la scheda giusta", () => {
    assert.deepEqual(leagueNextStepRoute("roster"), { kind: "tab", screen: "Roster" });
    assert.deepEqual(leagueNextStepRoute("auction"), { kind: "tab", screen: "Auction" });
    assert.deepEqual(leagueNextStepRoute("formation"), { kind: "tab", screen: "Formation" });
    assert.deepEqual(leagueNextStepRoute("standings"), { kind: "tab", screen: "Standings" });
  });
});
