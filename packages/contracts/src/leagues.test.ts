import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  LEAGUE_LIFECYCLE_PHASES,
  canConfirmRosterImport,
  describeLeagueLifecycleStep,
  describeRosterImportCandidate,
  leagueLifecyclePhaseIndex,
  orderLeagueSetupBlockers,
  rosterImportAmbiguousCount,
  type LeagueLifecycle,
  type RosterImportPreview,
  type RosterImportRow,
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

function importRow(overrides: Partial<RosterImportRow>): RosterImportRow {
  return {
    rowNumber: 2,
    squadra: "Squadra",
    providerId: null,
    nome: "toni fernandez",
    crediti: 5,
    status: "ok",
    fantasyTeamId: "team-1",
    fantasyTeamName: "Squadra",
    athleteId: "a-1",
    athleteName: "Toni Fernández",
    slotIndex: 0,
    issues: [],
    candidates: [],
    ...overrides,
  };
}

function importPreview(rows: RosterImportRow[], overrides: Partial<RosterImportPreview> = {}) {
  return {
    importId: "import-1",
    status: "draft",
    fileSha256: "sha",
    originalFilename: "rose.xlsx",
    canConfirm: false,
    rowCount: rows.length,
    errorCount: 0,
    ambiguousCount: rows.filter((row) => row.status === "ambiguous").length,
    warningCount: 0,
    rows,
    confirmedAt: null,
    ...overrides,
  } satisfies RosterImportPreview;
}

const homonyms = importRow({
  rowNumber: 3,
  status: "ambiguous",
  athleteId: null,
  athleteName: null,
  slotIndex: null,
  candidates: [
    {
      athleteId: "barca",
      providerId: 1,
      canonicalName: "Toni Fernández",
      role: "C",
      clubName: "Barcelona",
      competitionName: "La Liga",
    },
    {
      athleteId: "venezia",
      providerId: 2,
      canonicalName: "Toni Fernández",
      role: "A",
      clubName: "Venezia",
      competitionName: "Serie B",
    },
  ],
});

describe("describeRosterImportCandidate", () => {
  it("shows role, club and competition to tell homonyms apart", () => {
    assert.deepEqual(
      homonyms.candidates.map(describeRosterImportCandidate),
      ["Centrocampista · Barcelona · La Liga", "Attaccante · Venezia · Serie B"],
    );
  });

  it("skips missing details and falls back to the provider id", () => {
    assert.equal(
      describeRosterImportCandidate({
        athleteId: "x",
        providerId: 7,
        canonicalName: "X",
        role: "D",
        clubName: null,
      }),
      "Difensore",
    );
    assert.equal(
      describeRosterImportCandidate({ athleteId: "y", providerId: 9, canonicalName: "Y" }),
      "#9",
    );
  });
});

describe("roster import ambiguities", () => {
  it("counts ambiguous rows apart from errors, also without ambiguousCount", () => {
    const preview = importPreview([importRow({}), homonyms]);
    assert.equal(rosterImportAmbiguousCount(preview), 1);
    assert.equal(rosterImportAmbiguousCount({ ...preview, ambiguousCount: undefined }), 1);
  });

  it("confirms only once every ambiguous name has a valid choice", () => {
    const preview = importPreview([importRow({}), homonyms]);
    assert.equal(canConfirmRosterImport(preview, {}), false);
    assert.equal(canConfirmRosterImport(preview, { 3: "someone-else" }), false);
    assert.equal(canConfirmRosterImport(preview, { 3: "venezia" }), true);
    assert.equal(canConfirmRosterImport(importPreview([homonyms]), { 3: "barca" }), true);
  });

  it("stays blocked with errors, nothing to import or an already confirmed import", () => {
    const withError = importPreview([importRow({}), importRow({ rowNumber: 4, status: "error" })], {
      errorCount: 1,
    });
    assert.equal(canConfirmRosterImport(withError, {}), false);
    const onlySkipped = importPreview([importRow({ status: "skipped", athleteId: null })]);
    assert.equal(canConfirmRosterImport(onlySkipped, {}), false);
    const okAndSkipped = importPreview([
      importRow({}),
      importRow({ rowNumber: 5, status: "skipped" }),
    ]);
    assert.equal(canConfirmRosterImport(okAndSkipped, {}), true);
    assert.equal(canConfirmRosterImport({ ...okAndSkipped, status: "confirmed" }, {}), false);
    assert.equal(canConfirmRosterImport(null, {}), false);
  });
});
