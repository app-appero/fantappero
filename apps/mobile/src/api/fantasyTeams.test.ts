import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const leaguesSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "leagues.ts"),
  "utf8",
);

describe("EP05-01/06 fantasy team API client", () => {
  it("exports roster client helpers", () => {
    assert.match(leaguesSource, /export function fetchMyFantasyTeam\(/);
    assert.match(leaguesSource, /export function ensureFantasyTeams\(/);
  });

  it("exports roster history and snapshot helpers", () => {
    assert.match(leaguesSource, /export function fetchMyRosterHistory\(/);
    assert.match(leaguesSource, /export function fetchRosterTurnSnapshots\(/);
    assert.match(leaguesSource, /export function createRosterTurnSnapshot\(/);
  });

  it("exports lineup client helpers", () => {
    assert.match(leaguesSource, /export function fetchMyLineup\(/);
    assert.match(leaguesSource, /export function saveMyLineup\(/);
    assert.match(leaguesSource, /export function copyPreviousLineupToDraft\(/);
    assert.match(leaguesSource, /export function saveLineupDraft\(/);
  });
});
