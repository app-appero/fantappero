import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { computeMinimumNextBid, secondsRemaining, shouldTriggerSoftClose } from "./liveAuction.ts";

describe("computeMinimumNextBid", () => {
  it("is the increment itself when the lot has no leader yet", () => {
    assert.equal(computeMinimumNextBid(0, false, 10), 10);
  });

  it("is the current amount plus the increment once someone leads", () => {
    assert.equal(computeMinimumNextBid(50, true, 10), 60);
  });
});

describe("secondsRemaining", () => {
  it("counts down to zero, never negative", () => {
    const now = "2026-09-03T10:00:00.000Z";
    assert.equal(secondsRemaining("2026-09-03T10:00:30.000Z", now), 30);
    assert.equal(secondsRemaining("2026-09-03T09:59:00.000Z", now), 0);
  });
});

describe("shouldTriggerSoftClose", () => {
  it("is true once the remaining time drops to the soft-close window", () => {
    const now = "2026-09-03T10:00:00.000Z";
    assert.equal(shouldTriggerSoftClose("2026-09-03T10:00:03.000Z", now, 5), true);
    assert.equal(shouldTriggerSoftClose("2026-09-03T10:00:10.000Z", now, 5), false);
  });
});
