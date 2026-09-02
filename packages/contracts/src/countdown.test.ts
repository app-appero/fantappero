import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { computeCountdown, formatCountdown } from "./countdown.ts";

describe("computeCountdown", () => {
  it("is null when there is no target", () => {
    assert.equal(computeCountdown(null, "2026-08-15T16:00:00.000Z"), null);
    assert.equal(computeCountdown(undefined, "2026-08-15T16:00:00.000Z"), null);
  });

  it("splits the remaining time into days/hours/minutes/seconds", () => {
    const parts = computeCountdown("2026-08-16T18:03:05.000Z", "2026-08-15T16:00:00.000Z");
    assert.ok(parts);
    assert.equal(parts?.days, 1);
    assert.equal(parts?.hours, 2);
    assert.equal(parts?.minutes, 3);
    assert.equal(parts?.seconds, 5);
    assert.equal(parts?.expired, false);
  });

  it("clamps at zero once the target is reached or passed", () => {
    const atTarget = computeCountdown("2026-08-15T16:00:00.000Z", "2026-08-15T16:00:00.000Z");
    assert.equal(atTarget?.totalMs, 0);
    assert.equal(atTarget?.expired, true);

    const past = computeCountdown("2026-08-15T15:00:00.000Z", "2026-08-15T16:00:00.000Z");
    assert.equal(past?.totalMs, 0);
    assert.equal(past?.expired, true);
    assert.equal(past?.days, 0);
    assert.equal(past?.hours, 0);
    assert.equal(past?.minutes, 0);
    assert.equal(past?.seconds, 0);
  });

  it("accepts Date instances for both arguments", () => {
    const target = new Date("2026-08-15T16:01:00.000Z");
    const now = new Date("2026-08-15T16:00:00.000Z");
    const parts = computeCountdown(target, now);
    assert.equal(parts?.minutes, 1);
    assert.equal(parts?.seconds, 0);
  });
});

describe("formatCountdown", () => {
  it("is an empty string when there are no parts", () => {
    assert.equal(formatCountdown(null), "");
  });

  it("formats under a day as HH:MM:SS", () => {
    const parts = computeCountdown("2026-08-15T18:03:05.000Z", "2026-08-15T16:00:00.000Z");
    assert.equal(formatCountdown(parts), "02:03:05");
  });

  it("formats a day or more as 'Ng HH:MM:SS', seconds always visible", () => {
    const parts = computeCountdown("2026-08-17T18:04:07.000Z", "2026-08-15T16:00:00.000Z");
    assert.equal(formatCountdown(parts), "2g 02:04:07");
  });

  it("formats an expired countdown as zero", () => {
    const parts = computeCountdown("2026-08-15T15:00:00.000Z", "2026-08-15T16:00:00.000Z");
    assert.equal(formatCountdown(parts), "00:00:00");
  });
});
