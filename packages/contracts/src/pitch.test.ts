import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  fantasyBadgesFromBonusMalus,
  layoutFromGrid,
  layoutFromModule,
  pitchRoleFullLabel,
  pitchRoleVariant,
  realMatchBadgesByAthlete,
  resolvePitchRole,
} from "./pitch.ts";

describe("resolvePitchRole", () => {
  it("maps both the provider alphabet (G/D/M/F) and the fantacalcio one (P/D/C/A)", () => {
    assert.equal(resolvePitchRole("G"), "GK");
    assert.equal(resolvePitchRole("P"), "GK");
    assert.equal(resolvePitchRole("D"), "DEF");
    assert.equal(resolvePitchRole("M"), "MID");
    assert.equal(resolvePitchRole("C"), "MID");
    assert.equal(resolvePitchRole("F"), "FWD");
    assert.equal(resolvePitchRole("A"), "FWD");
    assert.equal(resolvePitchRole(null), null);
    assert.equal(resolvePitchRole("?"), null);
  });

  it("is case-insensitive and trims whitespace", () => {
    assert.equal(resolvePitchRole(" d "), "DEF");
    assert.equal(resolvePitchRole("f"), "FWD");
  });

  it("gives every canonical role a distinct color, not just defenders", () => {
    const variants = new Set(["G", "D", "M", "F"].map((code) => pitchRoleVariant(code)));
    assert.equal(variants.size, 4);
    assert.equal(pitchRoleVariant("?"), "neutral");
  });

  it("exposes a full Italian label regardless of source alphabet", () => {
    assert.equal(pitchRoleFullLabel("G"), "Portiere");
    assert.equal(pitchRoleFullLabel("P"), "Portiere");
    assert.equal(pitchRoleFullLabel("F"), "Attaccante");
    assert.equal(pitchRoleFullLabel("A"), "Attaccante");
  });
});

describe("layoutFromGrid", () => {
  it("positions a real 3-4-2-1 lineup using the provider grid, goalkeeper closest to the bottom", () => {
    const entries = [
      { id: "gk", grid: "1:1" },
      { id: "d1", grid: "2:1" },
      { id: "d2", grid: "2:2" },
      { id: "d3", grid: "2:3" },
      { id: "m1", grid: "3:1" },
      { id: "m2", grid: "3:2" },
      { id: "m3", grid: "3:3" },
      { id: "m4", grid: "3:4" },
      { id: "am1", grid: "4:1" },
      { id: "am2", grid: "4:2" },
      { id: "st", grid: "5:1" },
    ];
    const positions = layoutFromGrid(entries);
    assert.equal(positions.length, 11);
    const byId = new Map(positions.map((p) => [p.id, p]));
    // Goalkeeper (row 1) has the highest yPercent (closest to own goal / bottom).
    const gk = byId.get("gk")!;
    const striker = byId.get("st")!;
    assert.ok(gk.yPercent > striker.yPercent);
    // Defenders (row 2) sit between midfielders (row 3) and the goalkeeper.
    const defender = byId.get("d1")!;
    const midfielder = byId.get("m1")!;
    assert.ok(defender.yPercent > midfielder.yPercent);
    // Column order within a row is preserved left to right.
    const d1 = byId.get("d1")!;
    const d2 = byId.get("d2")!;
    const d3 = byId.get("d3")!;
    assert.ok(d1.xPercent < d2.xPercent);
    assert.ok(d2.xPercent < d3.xPercent);
  });

  it("ignores entries without a grid (bench players)", () => {
    const positions = layoutFromGrid([
      { id: "gk", grid: "1:1" },
      { id: "bench1", grid: null },
    ]);
    assert.equal(positions.length, 1);
    assert.equal(positions[0]!.id, "gk");
  });
});

type FantasyPlayer = { id: string; role: string; order: number };

function fantasyPlayers(roles: string[]): FantasyPlayer[] {
  return roles.map((role, index) => ({ id: `${role}-${index}`, role, order: index }));
}

describe("layoutFromModule", () => {
  const roleOf = (p: FantasyPlayer) => p.role;
  const idOf = (p: FantasyPlayer) => p.id;
  const sortKeyOf = (p: FantasyPlayer) => p.order;

  const modules: Array<[string, string[]]> = [
    ["4-4-2", ["P", "D", "D", "D", "D", "C", "C", "C", "C", "A", "A"]],
    ["4-3-3", ["P", "D", "D", "D", "D", "C", "C", "C", "A", "A", "A"]],
    ["5-4-1", ["P", "D", "D", "D", "D", "D", "C", "C", "C", "C", "A"]],
    ["3-5-2", ["P", "D", "D", "D", "C", "C", "C", "C", "C", "A", "A"]],
  ];

  for (const [module, roles] of modules) {
    it(`lays out every player for module ${module} without dropping anyone`, () => {
      const players = fantasyPlayers(roles);
      const positions = layoutFromModule(players, module, roleOf, idOf, sortKeyOf);
      assert.equal(positions.length, players.length);
    });
  }

  it("supports a module with two distinct midfield lines (4-2-3-1) dynamically", () => {
    const players = fantasyPlayers([
      "G",
      "D",
      "D",
      "D",
      "D",
      "M",
      "M",
      "M",
      "M",
      "M",
      "F",
    ]);
    const positions = layoutFromModule(players, "4-2-3-1", roleOf, idOf, sortKeyOf);
    assert.equal(positions.length, players.length);
    const byId = new Map(positions.map((p) => [p.id, p]));
    // The two midfield lines must occupy two different heights.
    const defensiveMid = byId.get("M-5")!; // first two of the five midfielders (row of 2)
    const attackingMid = byId.get("M-7")!; // later midfielders (row of 3, further forward)
    assert.notEqual(defensiveMid.yPercent, attackingMid.yPercent);
  });

  it("supports an arbitrary module not hardcoded anywhere (3-4-3)", () => {
    const players = fantasyPlayers(["P", "D", "D", "D", "C", "C", "C", "C", "A", "A", "A"]);
    const positions = layoutFromModule(players, "3-4-3", roleOf, idOf, sortKeyOf);
    assert.equal(positions.length, players.length);
  });

  it("falls back to role composition when the module string is missing", () => {
    const players = fantasyPlayers(["P", "D", "D", "C", "C", "A"]);
    const positions = layoutFromModule(players, null, roleOf, idOf, sortKeyOf);
    assert.equal(positions.length, players.length);
  });
});

describe("realMatchBadgesByAthlete", () => {
  it("credits a goal to the scorer and an assist to a different player", () => {
    const badges = realMatchBadgesByAthlete([
      {
        scoringKind: null,
        eventType: "Goal",
        eventDetail: "Normal Goal",
        athleteId: "scorer",
        relatedAthleteId: "assister",
      },
    ]);
    assert.deepEqual(badges.get("scorer"), [{ kind: "goal", count: 1 }]);
    assert.deepEqual(badges.get("assister"), [{ kind: "assist", count: 1 }]);
  });

  it("accumulates a double goal on the same player into one badge with count 2", () => {
    const event = {
      scoringKind: null,
      eventType: "Goal",
      eventDetail: "Normal Goal",
      athleteId: "scorer",
      relatedAthleteId: null,
    };
    const badges = realMatchBadgesByAthlete([event, event]);
    assert.deepEqual(badges.get("scorer"), [{ kind: "goal", count: 2 }]);
  });

  it("splits a substitution into an in-badge and an out-badge on two different players", () => {
    const badges = realMatchBadgesByAthlete([
      {
        scoringKind: null,
        eventType: "subst",
        eventDetail: "Substitution 1",
        athleteId: "leaving",
        relatedAthleteId: "entering",
      },
    ]);
    assert.deepEqual(badges.get("leaving"), [{ kind: "substitutionOut", count: 1 }]);
    assert.deepEqual(badges.get("entering"), [{ kind: "substitutionIn", count: 1 }]);
  });

  it("distinguishes yellow and red cards", () => {
    const badges = realMatchBadgesByAthlete([
      {
        scoringKind: null,
        eventType: "Card",
        eventDetail: "Yellow Card",
        athleteId: "p1",
        relatedAthleteId: null,
      },
      {
        scoringKind: null,
        eventType: "Card",
        eventDetail: "Red Card",
        athleteId: "p2",
        relatedAthleteId: null,
      },
    ]);
    assert.deepEqual(badges.get("p1"), [{ kind: "yellowCard", count: 1 }]);
    assert.deepEqual(badges.get("p2"), [{ kind: "redCard", count: 1 }]);
  });

  it("distinguishes an own goal from a normal goal", () => {
    const badges = realMatchBadgesByAthlete([
      {
        scoringKind: null,
        eventType: "Goal",
        eventDetail: "Own Goal",
        athleteId: "p1",
        relatedAthleteId: null,
      },
    ]);
    assert.deepEqual(badges.get("p1"), [{ kind: "ownGoal", count: 1 }]);
  });

  it("prefers the normalized scoringKind over the raw text when both are present", () => {
    const badges = realMatchBadgesByAthlete([
      {
        scoringKind: "penalty_saved",
        eventType: "penalty_saved",
        eventDetail: null,
        athleteId: "keeper",
        relatedAthleteId: null,
      },
    ]);
    assert.deepEqual(badges.get("keeper"), [{ kind: "penaltySaved", count: 1 }]);
  });
});

describe("fantasyBadgesFromBonusMalus", () => {
  it("maps known bonus categories to badges and ignores unknown ones", () => {
    const badges = fantasyBadgesFromBonusMalus([
      { id: "goal", count: 2 },
      { id: "assist", count: 1 },
      { id: "yellow_card", count: 1 },
      { id: "goalkeeper_clean_sheet", count: 1 },
    ]);
    assert.deepEqual(badges, [
      { kind: "goal", count: 2 },
      { kind: "assist", count: 1 },
      { kind: "yellowCard", count: 1 },
    ]);
  });
});
