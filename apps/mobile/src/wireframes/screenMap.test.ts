import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { ROUTE_TO_WIREFRAME, wireframeIdForRoute } from "./screenMap.ts";

describe("wireframe screen map", () => {
  it("maps member and admin routes to catalog ids", () => {
    assert.equal(wireframeIdForRoute("LeagueHome"), "league-dashboard");
    assert.equal(wireframeIdForRoute("Formation"), "formation");
    assert.equal(wireframeIdForRoute("LeagueAdmin"), "league-config");
    assert.equal(wireframeIdForRoute("AdminHome"), "operator-panel");
  });

  it("covers all macro-area routes from EPUI-04", () => {
    const expected = [
      "Auth",
      "LeagueHome",
      "LeagueAdmin",
      "Matchday",
      "Standings",
      "Roster",
      "Formation",
      "Auction",
      "Market",
      "AdminHome",
    ];
    for (const route of expected) {
      assert.ok(ROUTE_TO_WIREFRAME[route], `missing map for ${route}`);
    }
  });
});
