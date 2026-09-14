import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  LEAGUE_LIFECYCLE_PHASES,
  describeLeagueLifecycleStep,
  leagueLifecyclePhaseIndex,
  orderLeagueSetupBlockers,
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
  it("groups draft, configuring and auction in setup", () => {
    assert.equal(leagueLifecyclePhaseIndex("draft"), 0);
    assert.equal(leagueLifecyclePhaseIndex("configuring"), 0);
    assert.equal(leagueLifecyclePhaseIndex("auction"), 0);
    assert.equal(LEAGUE_LIFECYCLE_PHASES[0]?.key, "setup");
  });

  it("maps active to season and post-season to done", () => {
    assert.equal(leagueLifecyclePhaseIndex("active"), 1);
    assert.equal(LEAGUE_LIFECYCLE_PHASES[1]?.key, "season");
    assert.equal(leagueLifecyclePhaseIndex("concluded"), 2);
    assert.equal(leagueLifecyclePhaseIndex("archived"), 2);
    assert.equal(LEAGUE_LIFECYCLE_PHASES[2]?.key, "done");
  });
});

describe("describeLeagueLifecycleStep", () => {
  it("primary CTA from configuring is Avvia stagione, auction is optional", () => {
    const blocked = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: [] }),
    );
    assert.equal(blocked.forwardTarget, "active");
    assert.equal(blocked.forwardLabel, "Avvia stagione");
    assert.equal(blocked.forwardEnabled, false);
    assert.equal(blocked.optionalAuctionEnabled, false);

    const auctionOnly = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: ["auction"] }),
    );
    assert.equal(auctionOnly.forwardEnabled, false);
    assert.equal(auctionOnly.optionalAuctionEnabled, true);
    assert.equal(auctionOnly.optionalAuctionLabel, "Avvia l'asta");

    const ready = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: ["auction", "active"] }),
    );
    assert.equal(ready.forwardEnabled, true);
    assert.equal(ready.optionalAuctionEnabled, true);
  });

  it("only exposes a rollback CTA from auction back to configuring", () => {
    const fromAuction = describeLeagueLifecycleStep(
      lifecycle({ state: "auction", allowedTransitions: ["configuring", "active"] }),
    );
    assert.equal(fromAuction.rollbackTarget, "configuring");
    assert.equal(fromAuction.rollbackLabel, "Torna in configurazione");
    assert.equal(fromAuction.forwardTarget, "active");
    assert.equal(fromAuction.forwardLabel, "Avvia stagione");
    assert.equal(fromAuction.forwardEnabled, true);

    const fromConfiguring = describeLeagueLifecycleStep(
      lifecycle({ state: "configuring", allowedTransitions: ["auction"] }),
    );
    assert.equal(fromConfiguring.rollbackTarget, null);
  });

  it("has no manual conclude CTA while active", () => {
    const active = describeLeagueLifecycleStep(
      lifecycle({ state: "active", allowedTransitions: [] }),
    );
    assert.equal(active.forwardTarget, null);
    assert.equal(active.forwardEnabled, false);
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

describe("orderLeagueSetupBlockers", () => {
  it("orders members → teams → calendar and locks later steps", () => {
    const ordered = orderLeagueSetupBlockers([
      {
        code: "calendar_not_configured",
        message: "Genera il calendario",
        actionHint: "calendar",
      },
      {
        code: "fantasy_teams_not_configured",
        message: "Completa le rose",
        actionHint: "teams",
      },
      {
        code: "participant_count_mismatch",
        message: "Allinea i partecipanti",
        actionHint: "members",
      },
    ]);
    assert.deepEqual(
      ordered.map((row) => [row.code, row.actionable]),
      [
        ["participant_count_mismatch", true],
        ["fantasy_teams_not_configured", false],
        ["calendar_not_configured", false],
      ],
    );
  });
});
