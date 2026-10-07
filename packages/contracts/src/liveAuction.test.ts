import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  computeMinimumNextBid,
  liveSeatCueLabel,
  resolveLiveLotCallerTeamId,
  resolveLiveSeatCue,
  secondsRemaining,
  shouldTriggerSoftClose,
} from "./liveAuction.ts";

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

const TURN_ORDER = [
  { fantasyTeamId: "alpha", position: 0 },
  { fantasyTeamId: "beta", position: 1 },
  { fantasyTeamId: "gamma", position: 2 },
];

describe("resolveLiveLotCallerTeamId", () => {
  it("maps sequence 1 to the first drawn seat and wraps", () => {
    assert.equal(resolveLiveLotCallerTeamId(TURN_ORDER, 1), "alpha");
    assert.equal(resolveLiveLotCallerTeamId(TURN_ORDER, 2), "beta");
    assert.equal(resolveLiveLotCallerTeamId(TURN_ORDER, 4), "alpha");
  });

  it("ignores an empty order", () => {
    assert.equal(resolveLiveLotCallerTeamId([], 1), null);
  });
});

describe("resolveLiveSeatCue", () => {
  it("marks whose turn it is while waiting for the next call", () => {
    assert.equal(
      resolveLiveSeatCue({
        teamId: "beta",
        currentTurnTeamId: "beta",
        currentLot: null,
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      "turn",
    );
    assert.equal(
      resolveLiveSeatCue({
        teamId: "alpha",
        currentTurnTeamId: "beta",
        currentLot: null,
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      null,
    );
  });

  it("marks the caller of the open lot, not the next turn already advanced by the server", () => {
    const lot = { sequenceNumber: 1, currentLeaderTeamId: null };
    assert.equal(
      resolveLiveSeatCue({
        teamId: "alpha",
        currentTurnTeamId: "beta",
        currentLot: lot,
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      "caller",
    );
    assert.equal(
      resolveLiveSeatCue({
        teamId: "beta",
        currentTurnTeamId: "beta",
        currentLot: lot,
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      null,
    );
  });

  it("marks the leader when someone else is in testa, and prefers that over the caller", () => {
    const lot = { sequenceNumber: 1, currentLeaderTeamId: "gamma" };
    assert.equal(
      resolveLiveSeatCue({
        teamId: "gamma",
        currentTurnTeamId: "beta",
        currentLot: lot,
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      "leader",
    );
    assert.equal(
      resolveLiveSeatCue({
        teamId: "alpha",
        currentTurnTeamId: "beta",
        currentLot: lot,
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      "caller",
    );
  });

  it("uses the leader cue when the caller is still in testa", () => {
    assert.equal(
      resolveLiveSeatCue({
        teamId: "alpha",
        currentLot: { sequenceNumber: 1, currentLeaderTeamId: "alpha" },
        nominationMode: "turn_based",
        turnOrder: TURN_ORDER,
      }),
      "leader",
    );
    assert.equal(liveSeatCueLabel("leader", true), "In testa");
    assert.equal(liveSeatCueLabel("turn", true), "Tocca a te");
    assert.equal(liveSeatCueLabel("turn", false), "Tocca a lui");
  });
});
