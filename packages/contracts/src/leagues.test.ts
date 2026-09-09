import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  LEAGUE_LIFECYCLE_PHASES,
  describeLeagueLifecycleStep,
  leagueLifecyclePhaseIndex,
  type LeagueLifecycle,
} from "./leagues.ts";

function lifecycle(overrides: Partial<LeagueLifecycle>): LeagueLifecycle {
  return {
    state: "draft",
    allowedTransitions: [],
    blockers: [],
    ...overrides,
  };
}

describe("leagueLifecyclePhaseIndex", () => {
  it("groups draft and configuring in the same setup phase", () => {
    assert.equal(leagueLifecyclePhaseIndex("draft"), 0);
    assert.equal(leagueLifecyclePhaseIndex("configuring"), 0);
    assert.equal(LEAGUE_LIFECYCLE_PHASES[0]?.key, "setup");
  });

  it("maps auction and the post-season states to their own phases", () => {
    assert.equal(leagueLifecyclePhaseIndex("auction"), 1);
    assert.equal(leagueLifecyclePhaseIndex("active"), 2);
    assert.equal(leagueLifecyclePhaseIndex("concluded"), 2);
    assert.equal(leagueLifecyclePhaseIndex("archived"), 2);
  });
});

describe("describeLeagueLifecycleStep", () => {
  it("exposes a single forward CTA per state, disabled while blocked", () => {
    const blocked = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: [] }),
    );
    assert.equal(blocked.forwardTarget, "auction");
    assert.equal(blocked.forwardLabel, "Avvia l'asta");
    assert.equal(blocked.forwardEnabled, false);

    const unblocked = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: ["auction"] }),
    );
    assert.equal(unblocked.forwardEnabled, true);
  });

  it("only exposes a rollback CTA from auction back to configuring", () => {
    const fromAuction = describeLeagueLifecycleStep(
      lifecycle({ state: "auction", allowedTransitions: ["configuring", "active"] }),
    );
    assert.equal(fromAuction.rollbackTarget, "configuring");
    assert.equal(fromAuction.rollbackLabel, "Torna in configurazione");
    assert.equal(fromAuction.forwardTarget, "active");
    assert.equal(fromAuction.forwardEnabled, true);

    const fromConfiguring = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: ["auction"] }),
    );
    assert.equal(fromConfiguring.rollbackTarget, null);
  });

  it("has no forward CTA once the league is archived", () => {
    const archived = describeLeagueLifecycleStep(
      lifecycle({ state: "archived", allowedTransitions: [] }),
    );
    assert.equal(archived.forwardTarget, null);
    assert.equal(archived.forwardLabel, null);
    assert.equal(archived.forwardEnabled, false);
  });
});

