import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { isLeagueDeletable } from "./leagueDeleteHelpers.ts";

describe("isLeagueDeletable", () => {
  it("allows draft and configuring only", () => {
    assert.equal(isLeagueDeletable("draft"), true);
    assert.equal(isLeagueDeletable("configuring"), true);
    assert.equal(isLeagueDeletable("auction"), false);
    assert.equal(isLeagueDeletable("active"), false);
    assert.equal(isLeagueDeletable("concluded"), false);
    assert.equal(isLeagueDeletable("archived"), false);
    assert.equal(isLeagueDeletable(undefined), false);
  });
});
