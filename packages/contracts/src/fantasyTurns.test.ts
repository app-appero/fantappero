import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  applyCutoffRecalculation,
  computeCutoff,
  deriveEffectiveStatus,
  isModificationAllowed,
  kickoffCountsForCutoff,
  mapFixtureMatchStatus,
  reconcileFixtureKickoffLock,
} from "./fantasyTurns.ts";

describe("fantasyTurns rules", () => {
  it("computeCutoff uses the earliest kickoff including simultaneous ones", () => {
    const a = "2026-08-15T14:00:00.000Z";
    const b = "2026-08-15T14:00:00.000Z";
    const c = "2026-08-15T18:30:00.000Z";
    assert.equal(computeCutoff([c, a, b]), a);
    assert.equal(computeCutoff([]), null);
  });

  it("deriveEffectiveStatus locks open turns past cutoff across timezones", () => {
    const cutoff = "2026-08-15T16:00:00.000Z"; // 18:00 Europe/Rome (CEST)
    assert.equal(
      deriveEffectiveStatus("open", "2026-08-15T15:59:59.000Z", cutoff),
      "open",
    );
    assert.equal(
      deriveEffectiveStatus("open", "2026-08-15T16:00:00.000Z", cutoff),
      "locked",
    );
    assert.equal(deriveEffectiveStatus("scheduled", "2026-08-15T20:00:00.000Z", cutoff), "scheduled");
  });

  it("isModificationAllowed only while scheduled", () => {
    const cutoff = "2026-08-15T16:00:00.000Z";
    assert.equal(isModificationAllowed("scheduled", "2026-08-15T20:00:00.000Z", cutoff), true);
    assert.equal(isModificationAllowed("open", "2026-08-15T15:00:00.000Z", cutoff), false);
    assert.equal(isModificationAllowed("open", "2026-08-15T17:00:00.000Z", cutoff), false);
  });

  it("does not move cutoff later after it elapsed, including simultaneous kickoffs and timezones", () => {
    const romeKickoff = "2026-08-15T18:00:00+02:00";
    const utcKickoff = "2026-08-15T16:00:00.000Z";
    const later = "2026-08-15T20:00:00.000Z";
    assert.equal(computeCutoff([later, romeKickoff, utcKickoff]), utcKickoff);

    assert.equal(
      applyCutoffRecalculation(romeKickoff, later, "2026-08-15T15:00:00.000Z"),
      later,
    );
    assert.equal(
      applyCutoffRecalculation(romeKickoff, later, "2026-08-15T16:05:00.000Z"),
      utcKickoff,
    );
    assert.equal(
      kickoffCountsForCutoff("2026-08-15T12:00:00.000Z", "PST", "2026-08-15T16:00:00.000Z"),
      false,
    );
    assert.equal(
      kickoffCountsForCutoff("2026-08-16T16:00:00.000Z", "PST", "2026-08-15T16:00:00.000Z"),
      true,
    );
    assert.equal(mapFixtureMatchStatus("PST"), "postponed");
  });

  it("latches fixture lock after the published kickoff, not before a postponement", () => {
    const original = "2026-08-15T18:00:00+02:00";
    const postponed = "2026-08-16T18:00:00+02:00";
    const before = reconcileFixtureKickoffLock({
      now: "2026-08-15T15:00:00.000Z",
      currentKickoffAt: postponed,
      statusShort: "PST",
      observedKickoffAt: original,
      lockLatchedAt: null,
    });
    assert.equal(before.lockLatchedAt, null);
    assert.equal(before.observedKickoffAt, "2026-08-16T16:00:00.000Z");

    const after = reconcileFixtureKickoffLock({
      now: "2026-08-15T16:05:00.000Z",
      currentKickoffAt: postponed,
      statusShort: "PST",
      observedKickoffAt: original,
      lockLatchedAt: null,
    });
    assert.equal(after.lockLatchedAt, "2026-08-15T16:00:00.000Z");
    assert.equal(after.justLatched, true);
  });

  it("latches a later kickoff shift after the original instant, even without PST", () => {
    const original = "2026-08-15T18:00:00+02:00";
    const shifted = "2026-08-15T20:30:00+02:00";
    const after = reconcileFixtureKickoffLock({
      now: "2026-08-15T16:05:00.000Z",
      currentKickoffAt: shifted,
      statusShort: "NS",
      observedKickoffAt: original,
      lockLatchedAt: null,
    });
    assert.equal(after.lockLatchedAt, "2026-08-15T16:00:00.000Z");
    assert.equal(
      applyCutoffRecalculation(original, shifted, "2026-08-15T16:05:00.000Z"),
      "2026-08-15T16:00:00.000Z",
    );
  });
});
