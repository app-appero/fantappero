import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  fantasyBadgesFromBonusMalus,
  layoutFromGrid,
  layoutFromModule,
  layoutFromRoles,
  pitchRoleCodeFromGrid,
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

describe("pitchRoleCodeFromGrid", () => {
  it("derives G/D/M/F from the grid row, ignoring an unreliable provider pos", () => {
    const grids = ["1:1", "2:1", "2:2", "2:3", "2:4", "3:1", "3:2", "3:3", "4:1", "4:2", "4:3"];
    assert.equal(pitchRoleCodeFromGrid("1:1", grids), "G");
    assert.equal(pitchRoleCodeFromGrid("2:1", grids), "D");
    assert.equal(pitchRoleCodeFromGrid("3:1", grids), "M");
    assert.equal(pitchRoleCodeFromGrid("4:1", grids), "F");
  });

  it("treats every row strictly between the back line and the front line as midfield (4-2-3-1)", () => {
    const grids = ["1:1", "2:1", "2:2", "2:3", "2:4", "3:1", "3:2", "4:1", "4:2", "4:3", "5:1"];
    assert.equal(pitchRoleCodeFromGrid("3:1", grids), "M");
    assert.equal(pitchRoleCodeFromGrid("4:1", grids), "M");
    assert.equal(pitchRoleCodeFromGrid("5:1", grids), "F");
  });

  it("returns null without a grid, so callers can fall back to the provider pos", () => {
    assert.equal(pitchRoleCodeFromGrid(null, ["1:1"]), null);
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

  it("keeps all midfielders on one line so different modules stay aligned side by side (4-2-3-1)", () => {
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
    // Reparti sempre alla stessa altezza: tutto il centrocampo su una sola riga.
    const first = byId.get("M-5")!;
    const last = byId.get("M-9")!;
    assert.equal(first.yPercent, last.yPercent);
    // …e identica a quella di un 4-3-3, così due formazioni affiancate si allineano.
    const other = layoutFromModule(
      fantasyPlayers(["G", "D", "D", "D", "D", "M", "M", "M", "F", "F", "F"]),
      "4-3-3",
      roleOf,
      idOf,
      sortKeyOf,
    );
    const otherMid = other.find((p) => p.id === "M-5")!;
    assert.equal(first.yPercent, otherMid.yPercent);
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

describe("layoutFromRoles", () => {
  // Lazio 4-3-3 reale: il pos della partita dà Zaccagni come M (4 M e 2 F),
  // ma il ruolo reale dalla rosa è A: il 4-3-3 richiede 3 attaccanti.
  const lazio = [
    { id: "mandas", position: "G", fantasyRole: "P", grid: "2:4" },
    { id: "tavares", position: "D", fantasyRole: "D", grid: "2:1" },
    { id: "sutalo", position: "D", fantasyRole: "D", grid: "4:1" },
    { id: "provstgaard", position: "D", fantasyRole: "D", grid: "4:2" },
    { id: "mussolini", position: "D", fantasyRole: "D", grid: "3:3" },
    { id: "belahyane", position: "M", fantasyRole: "C", grid: "1:1" },
    { id: "taylor", position: "M", fantasyRole: "C", grid: "2:2" },
    { id: "frattesi", position: "M", fantasyRole: "C", grid: "3:1" },
    { id: "zaccagni", position: "M", fantasyRole: "A", grid: "2:3" },
    { id: "isaksen", position: "F", fantasyRole: "A", grid: "3:2" },
    { id: "noslin", position: "F", fantasyRole: "A", grid: "4:3" },
  ];

  it("uses the real roster role and gets 1-4-3-3 on the pitch", () => {
    const layout = layoutFromRoles(lazio, "4-3-3")!;
    assert.ok(layout);
    const byId = new Map(layout.positions.map((p) => [p.id, p]));
    const y = (id: string) => byId.get(id)!.yPercent;
    assert.equal(layout.roles.get("zaccagni"), "F");
    assert.equal(layout.roles.get("mandas"), "G");
    const count = (role: string) => [...layout.roles.values()].filter((r) => r === role).length;
    assert.deepEqual([count("G"), count("D"), count("M"), count("F")], [1, 4, 3, 3]);
    assert.ok(y("mandas") > y("tavares"));
    assert.equal(y("tavares"), y("mussolini"));
    assert.ok(y("tavares") > y("frattesi"));
    assert.equal(y("zaccagni"), y("noslin"));
    assert.ok(y("frattesi") > y("zaccagni"));
  });

  it("moves, to fit the formation, the player whose match pos already points there", () => {
    // Nessun ruolo reale: 4 M e 2 F dal pos, il 4-3-3 chiede un M in più davanti.
    const noRoster = lazio.map(({ fantasyRole: _ignored, ...rest }) => rest);
    const layout = layoutFromRoles(noRoster, "4-3-3")!;
    const count = (role: string) => [...layout.roles.values()].filter((r) => r === role).length;
    assert.deepEqual([count("G"), count("D"), count("M"), count("F")], [1, 4, 3, 3]);
    assert.equal(layout.roles.get("mandas"), "G");
  });

  it("builds one row per middle digit of the formation (4-2-3-1)", () => {
    const players = [
      { id: "gk", position: "G", grid: null },
      ...["d1", "d2", "d3", "d4"].map((id, i) => ({ id, position: "D", grid: `2:${i + 1}` })),
      { id: "m1", position: "M", grid: "3:1" },
      { id: "m2", position: "M", grid: "3:2" },
      { id: "a1", position: "M", grid: "4:1" },
      { id: "a2", position: "M", grid: "4:2" },
      { id: "a3", position: "M", grid: "4:3" },
      { id: "st", position: "F", grid: "5:1" },
    ];
    const layout = layoutFromRoles(players, "4-2-3-1")!;
    const byId = new Map(layout.positions.map((p) => [p.id, p]));
    assert.equal(byId.get("m1")!.yPercent, byId.get("m2")!.yPercent);
    assert.ok(byId.get("m1")!.yPercent > byId.get("a1")!.yPercent);
    assert.ok(byId.get("a1")!.yPercent > byId.get("st")!.yPercent);
    assert.equal(new Set(layout.positions.map((p) => p.yPercent)).size, 5);
  });

  it("never moves the goalkeeper", () => {
    const layout = layoutFromRoles(lazio, "3-4-3")!;
    assert.equal(layout.roles.get("mandas"), "G");
  });

  it("returns null only when a player has no known role", () => {
    assert.equal(
      layoutFromRoles(lazio.map((p, i) => (i === 0 ? { ...p, position: null, fantasyRole: null } : p)), "4-3-3"),
      null,
    );
  });
});
