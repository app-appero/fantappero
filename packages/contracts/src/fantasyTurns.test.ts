import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  aggregateTurnStatus,
  applyCutoffRecalculation,
  computeCutoff,
  deriveEffectiveStatus,
  isModificationAllowed,
  kickoffCountsForCutoff,
  mapFixtureMatchStatus,
  reconcileFixtureKickoffLock,
  resolveDefaultEuropeanTurn,
  resolveTurnDisplayStates,
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

  it("mapFixtureMatchStatus flags fixtures without a confirmed kickoff as needs_update", () => {
    assert.equal(mapFixtureMatchStatus("TBD", null), "needs_update");
    assert.equal(mapFixtureMatchStatus("NS", "2026-08-15T14:00:00.000Z"), "scheduled");
  });

  it("aggregateTurnStatus: any live fixture wins over everything else", () => {
    assert.equal(
      aggregateTurnStatus([
        { statusShort: "FT", kickoffAt: "2026-08-15T14:00:00.000Z" },
        { statusShort: "1H", kickoffAt: "2026-08-15T14:00:00.000Z" },
      ]),
      "live",
    );
  });

  it("aggregateTurnStatus: needs_update when a fixture has no confirmed date", () => {
    assert.equal(
      aggregateTurnStatus([
        { statusShort: "NS", kickoffAt: "2026-08-15T14:00:00.000Z" },
        { statusShort: "TBD", kickoffAt: null },
      ]),
      "needs_update",
    );
  });

  it("aggregateTurnStatus: completed only when every fixture is finished/postponed", () => {
    assert.equal(
      aggregateTurnStatus([
        { statusShort: "FT", kickoffAt: "2026-08-15T14:00:00.000Z" },
        { statusShort: "AET", kickoffAt: "2026-08-15T16:00:00.000Z" },
      ]),
      "completed",
    );
    assert.equal(
      aggregateTurnStatus([
        { statusShort: "FT", kickoffAt: "2026-08-15T14:00:00.000Z" },
        { statusShort: "NS", kickoffAt: "2026-08-16T14:00:00.000Z" },
      ]),
      "scheduled",
    );
  });

  it("aggregateTurnStatus: an empty turn is treated as needs_update", () => {
    assert.equal(aggregateTurnStatus([]), "needs_update");
  });

  it("resolveDefaultEuropeanTurn: skips completed turns from the start of the season", () => {
    const turns = [
      { id: "1", matchStatus: "completed" as const },
      { id: "2", matchStatus: "completed" as const },
      { id: "3", matchStatus: "scheduled" as const },
      { id: "4", matchStatus: "needs_update" as const },
    ];
    assert.equal(resolveDefaultEuropeanTurn(turns)?.id, "3");
  });

  it("resolveDefaultEuropeanTurn: falls back to the last turn when all are completed", () => {
    const turns = [
      { id: "1", matchStatus: "completed" as const },
      { id: "2", matchStatus: "completed" as const },
    ];
    assert.equal(resolveDefaultEuropeanTurn(turns)?.id, "2");
  });

  it("resolveDefaultEuropeanTurn: null for an empty list", () => {
    assert.equal(resolveDefaultEuropeanTurn([]), null);
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

  it("resolveTurnDisplayStates: concluso / prossimo / da disputare", () => {
    const turns = [
      { matchStatus: "completed" as const },
      { matchStatus: "scheduled" as const },
      { matchStatus: "scheduled" as const },
      { matchStatus: "needs_update" as const },
    ];
    assert.deepEqual(resolveTurnDisplayStates(turns), [
      "completed",
      "next",
      "upcoming",
      "upcoming",
    ]);
  });

  it("resolveTurnDisplayStates: un turno in corso occupa il posto del prossimo", () => {
    const turns = [
      { matchStatus: "completed" as const },
      { matchStatus: "live" as const },
      { matchStatus: "scheduled" as const },
    ];
    assert.deepEqual(resolveTurnDisplayStates(turns), ["completed", "live", "upcoming"]);
  });

  it("resolveTurnDisplayStates: stagione finita, nessun prossimo", () => {
    const turns = [{ matchStatus: "completed" as const }, { matchStatus: "completed" as const }];
    assert.deepEqual(resolveTurnDisplayStates(turns), ["completed", "completed"]);
  });
});
