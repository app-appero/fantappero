import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { AdminWatch } from "../../../../packages/contracts/src/admin.ts";
import { buildOperatorWatchItems } from "../../../../packages/contracts/src/operatorSummary.ts";
import {
  ADMIN_NAV_ID_BY_ROUTE,
  ADMIN_SCREEN_BY_ID,
  adminScreenForWatchTarget,
} from "./adminScreens.ts";
import { MOBILE_ADMIN_NAV_ITEMS } from "./navConfig.ts";

const EMPTY_WATCH: AdminWatch = {
  generatedAt: "2026-11-22T09:00:00Z",
  testerRequestsPending: 0,
  oldestTesterRequestAt: null,
  feedbackNew: 0,
  latestFeedbackAt: null,
  jobsDisabled: [],
  jobFailuresSince: "2026-11-21T09:00:00Z",
  jobFailures: [],
  listoneLastUpdate: null,
  currentRounds: { activeLeagues: 0, leaguesInProgress: 0, roundNumbers: [] },
  nextLineupLock: null,
  androidAppVersion: null,
};

describe("pannello operatore nell'app: menù e Riepilogo (1.4)", () => {
  it("ogni voce del menù apre una schermata, e la schermata accende la sua voce", () => {
    for (const item of MOBILE_ADMIN_NAV_ITEMS) {
      const screen = ADMIN_SCREEN_BY_ID[item.id];
      assert.ok(screen, `manca la schermata di ${item.id}`);
      assert.equal(ADMIN_NAV_ID_BY_ROUTE[screen], item.id);
    }
    assert.equal(ADMIN_SCREEN_BY_ID["admin-app-version"], "AdminAppVersion");
  });

  it("ogni riga di «Da guardare» porta alla sezione giusta del menù", () => {
    const rows = buildOperatorWatchItems(EMPTY_WATCH, new Date("2026-11-22T09:00:00Z"));
    assert.deepEqual(
      rows.map((row) => adminScreenForWatchTarget(row.target)),
      ["AdminUsers", "AdminFeedback", "AdminJobs", "AdminListone", "AdminTurni", "AdminAppVersion"],
    );
    for (const row of rows) {
      assert.ok(
        MOBILE_ADMIN_NAV_ITEMS.some((item) => item.id === row.target),
        `${row.target} non è nel menù`,
      );
    }
  });
});
