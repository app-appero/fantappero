import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  APPROVED_MODULES,
  copyPreviousLineup,
  evaluateBenchOrderLock,
  evaluateLineup,
  evaluateProgressiveLock,
  evaluateTacticalMove,
  isApprovedModule,
  isAthleteKickoffLocked,
  isLineupModificationAllowed,
  isTacticalWindowActive,
  MAX_AUTOMATIC_SUBSTITUTIONS,
  MAX_TACTICAL_MOVES,
  moduleCounts,
  moveBenchItem,
  moveBenchToIndex,
  orderedBenchFromRoster,
  preserveLockedStarters,
  remainingRosterForBench,
  remainingTacticalMoves,
  resolveAutomaticSubstitutions,
  slotsFromLineupIds,
  starterTemplate,
} from "./fantasyLineups.ts";

function ids(prefix: string, count: number): string[] {
  return Array.from({ length: count }, (_, index) => `${prefix}-${index + 1}`);
}

function players(
  athleteIds: readonly string[],
  role: "P" | "D" | "C" | "A",
): { athleteId: string; role: "P" | "D" | "C" | "A" }[] {
  return athleteIds.map((athleteId) => ({ athleteId, role }));
}

function valid433Roster() {
  const p = ids("p", 3);
  const d = ids("d", 11);
  const c = ids("c", 11);
  const a = ids("a", 10);
  const roster = [...p, ...d, ...c, ...a];
  const starters = [
    ...players(p.slice(0, 1), "P"),
    ...players(d.slice(0, 4), "D"),
    ...players(c.slice(0, 3), "C"),
    ...players(a.slice(0, 3), "A"),
  ];
  const starterIds = starters.map((item) => item.athleteId);
  const bench = remainingRosterForBench(roster, starterIds).map((athleteId) => {
    const role = athleteId.startsWith("p")
      ? "P"
      : athleteId.startsWith("d")
        ? "D"
        : athleteId.startsWith("c")
          ? "C"
          : "A";
    return { athleteId, role: role as "P" | "D" | "C" | "A" };
  });
  return { roster, starters, bench };
}

describe("fantasyLineups rules", () => {
  it("exposes the seven approved modules with P–D–C–A counts", () => {
    assert.equal(APPROVED_MODULES.length, 7);
    assert.deepEqual(
      APPROVED_MODULES.map((code) => {
        const counts = moduleCounts(code);
        return [code, counts.goalkeepers, counts.defenders, counts.midfielders, counts.forwards];
      }),
      [
        ["3-4-3", 1, 3, 4, 3],
        ["3-5-2", 1, 3, 5, 2],
        ["4-3-3", 1, 4, 3, 3],
        ["4-4-2", 1, 4, 4, 2],
        ["4-5-1", 1, 4, 5, 1],
        ["5-3-2", 1, 5, 3, 2],
        ["5-4-1", 1, 5, 4, 1],
      ],
    );
    assert.equal(starterTemplate("4-3-3").length, 11);
    assert.equal(starterTemplate("4-3-3").filter((role) => role === "D").length, 4);
    assert.equal(isApprovedModule("4-2-3-1"), false);
  });

  it("accepts a compatible 4-3-3 with the full remaining bench", () => {
    const { roster, starters, bench } = valid433Roster();
    const result = evaluateLineup({
      module: "4-3-3",
      starters,
      bench,
      rosterAthleteIds: roster,
    });
    assert.equal(result.valid, true);
    assert.deepEqual(result.issues, []);
    assert.deepEqual(result.starterCounts, { P: 1, D: 4, C: 3, A: 3 });
  });

  it("rejects an incompatible module with a motivation", () => {
    const { roster, starters, bench } = valid433Roster();
    const result = evaluateLineup({
      module: "3-5-2",
      starters,
      bench,
      rosterAthleteIds: roster,
    });
    assert.equal(result.valid, false);
    assert.ok(result.issues.some((item) => item.code === "module_role_mismatch"));
    assert.ok(result.issues.some((item) => item.message.includes("3-5-2")));
  });

  it("rejects unknown modules and missing goalkeeper", () => {
    const result = evaluateLineup({
      module: "4-2-3-1",
      starters: players(ids("d", 11), "D"),
      bench: [],
      rosterAthleteIds: ids("d", 11),
    });
    assert.equal(result.valid, false);
    assert.ok(result.issues.some((item) => item.code === "invalid_module"));
    assert.ok(result.issues.some((item) => item.code === "goalkeeper_count_invalid"));
  });

  it("allows turn-level lineup edits on open and locked turns", () => {
    assert.equal(isLineupModificationAllowed("open"), true);
    assert.equal(isLineupModificationAllowed("locked"), true);
    assert.equal(isLineupModificationAllowed("scheduled"), false);
    assert.equal(isLineupModificationAllowed("skipped"), false);
  });

  it("locks athletes at kickoff including simultaneous times and timezones", () => {
    const kickoff = "2026-08-15T16:00:00.000Z"; // 18:00 Europe/Rome CEST
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:59:59.000Z", kickoff, "NS"), false);
    assert.equal(isAthleteKickoffLocked("2026-08-15T16:00:00.000Z", kickoff, "NS"), true);
    assert.equal(isAthleteKickoffLocked("2026-08-15T16:00:00.000Z", "2026-08-15T16:00:00.000Z", "NS"), true);
    assert.equal(isAthleteKickoffLocked("2026-08-15T16:00:00.000Z", "2026-08-15T18:30:00.000Z", "NS"), false);
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:59:59.000Z", "2026-08-15T18:00:00+02:00", "NS"), false);
    assert.equal(isAthleteKickoffLocked("2026-08-15T16:00:00.000Z", "2026-08-15T18:00:00+02:00", "NS"), true);
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:00:00.000Z", kickoff, "1H"), true);
    assert.equal(isAthleteKickoffLocked("2026-08-15T16:00:00.000Z", "2026-08-15T12:00:00.000Z", "PST"), false);
    assert.equal(
      isAthleteKickoffLocked("2026-08-15T16:05:00.000Z", "2026-08-16T16:00:00.000Z", "PST", true),
      true,
    );
    const nyKickoff = "2026-08-15T12:00:00-04:00";
    assert.equal(isAthleteKickoffLocked("2026-08-15T16:00:00.000Z", nyKickoff, "NS"), true);
  });

  it("keeps future players editable and rejects locked slot changes", () => {
    const previous = slotsFromLineupIds(["locked-a"], ["future-b"]);
    const ok = evaluateProgressiveLock({
      previousSlots: previous,
      proposedSlots: slotsFromLineupIds(["locked-a", "future-b"], []),
      lockedAthleteIds: ["locked-a"],
    });
    assert.deepEqual(ok, []);

    const moved = evaluateProgressiveLock({
      previousSlots: previous,
      proposedSlots: slotsFromLineupIds(["future-b"], ["locked-a"]),
      lockedAthleteIds: ["locked-a"],
    });
    assert.ok(moved.some((item) => item.code === "athlete_kickoff_locked"));

    const firstSaveStarter = evaluateProgressiveLock({
      previousSlots: {},
      proposedSlots: slotsFromLineupIds(["locked-a"], ["future-b"]),
      lockedAthleteIds: ["locked-a"],
    });
    assert.ok(firstSaveStarter.some((item) => item.code === "athlete_kickoff_locked"));
  });

  it("preserves locked starters when the module changes", () => {
    const next = preserveLockedStarters({
      template: starterTemplate("3-5-2"),
      currentStarters: ["p1", "d1", "d2", "d3", "d4", "c1", "c2", "c3", "a1", "a2", "a3"],
      roster: [
        { athleteId: "p1", athleteName: "P", role: "P", slotIndex: 0, locked: true },
        { athleteId: "d1", athleteName: "D", role: "D", slotIndex: 1, locked: true },
        { athleteId: "d2", athleteName: "D2", role: "D", slotIndex: 2, locked: false },
        { athleteId: "c1", athleteName: "C", role: "C", slotIndex: 3, locked: false },
        { athleteId: "a1", athleteName: "A", role: "A", slotIndex: 4, locked: false },
      ],
    });
    assert.equal(next[0], "p1");
    assert.equal(next[1], "d1");
    assert.equal(next.filter(Boolean).length, 2);
  });

  it("keeps saved bench order and appends newcomers", () => {
    const ordered = orderedBenchFromRoster(
      ["p1", "d1", "d2", "c1"],
      ["p1", "d1"],
      ["c1", "d2"],
    );
    assert.deepEqual(ordered, ["c1", "d2"]);
    const withNew = orderedBenchFromRoster(["p1", "d1", "d2", "c1", "a1"], ["p1", "d1"], ["c1"]);
    assert.deepEqual(withNew, ["c1", "d2", "a1"]);
    assert.deepEqual(moveBenchItem(["a", "b", "c"], 2, -1), ["a", "c", "b"]);
    assert.deepEqual(moveBenchToIndex(["a", "b", "c", "d"], 0, 3), ["b", "c", "d", "a"]);
    assert.deepEqual(moveBenchToIndex(["a", "b", "c", "d"], 3, 0), ["d", "a", "b", "c"]);
    assert.deepEqual(moveBenchToIndex(["a", "b", "c"], 1, 1), ["a", "b", "c"]);
  });

  it("locks bench order around players whose kickoff has started", () => {
    const previous = ["u1", "locked-b", "u2"];
    const crossed = evaluateBenchOrderLock({
      previousBench: previous,
      proposedBench: ["u1", "u2", "locked-b"],
      lockedAthleteIds: ["locked-b"],
    });
    assert.ok(crossed.some((item) => item.code === "bench_order_locked"));

    const insertedBefore = evaluateBenchOrderLock({
      previousBench: previous,
      proposedBench: ["u1", "new-d", "locked-b", "u2"],
      lockedAthleteIds: ["locked-b"],
    });
    assert.ok(insertedBefore.some((item) => item.code === "bench_order_locked"));

    const okSwapUnlocked = evaluateBenchOrderLock({
      previousBench: ["u1", "u2", "locked-b"],
      proposedBench: ["u2", "u1", "locked-b"],
      lockedAthleteIds: ["locked-b"],
    });
    assert.deepEqual(okSwapUnlocked, []);

    const afterLastLocked = evaluateBenchOrderLock({
      previousBench: previous,
      proposedBench: ["u1", "locked-b", "u2", "new-d"],
      lockedAthleteIds: ["locked-b"],
    });
    assert.deepEqual(afterLastLocked, []);

    const now = "2026-08-15T16:00:00.000Z";
    const simultaneousLocked = ["b-rome", "b-utc"].filter((athleteId) =>
      isAthleteKickoffLocked(
        now,
        athleteId === "b-rome" ? "2026-08-15T18:00:00+02:00" : "2026-08-15T16:00:00.000Z",
        "NS",
      ),
    );
    assert.deepEqual(simultaneousLocked, ["b-rome", "b-utc"]);
    const swappedSimultaneous = evaluateBenchOrderLock({
      previousBench: ["b-rome", "b-utc", "future"],
      proposedBench: ["b-utc", "b-rome", "future"],
      lockedAthleteIds: simultaneousLocked,
    });
    assert.ok(swappedSimultaneous.some((item) => item.code === "bench_order_locked"));
  });

  it("applies up to 5 same-role substitutions in bench order and keeps the module", () => {
    assert.equal(MAX_AUTOMATIC_SUBSTITUTIONS, 5);
    const { roster, starters, bench } = valid433Roster();
    const starterIds = starters.map((item) => item.athleteId);
    const firstDefender = starters.find((item) => item.role === "D")?.athleteId ?? "";
    const benchDefender = bench.find((item) => item.role === "D")?.athleteId ?? "";
    const laterDefender = bench.filter((item) => item.role === "D")[1]?.athleteId ?? "";
    const benchKeeper = bench.find((item) => item.role === "P")?.athleteId ?? "";

    const played = new Set(roster);
    played.delete(firstDefender);
    played.add(benchDefender);
    played.add(laterDefender);
    played.add(benchKeeper);

    const reorderedBench = [
      ...bench.filter((item) => item.athleteId === laterDefender),
      ...bench.filter((item) => item.athleteId !== laterDefender),
    ];
    const resolved = resolveAutomaticSubstitutions({
      module: "4-3-3",
      starters,
      bench: reorderedBench,
      playedAthleteIds: [...played],
    });
    assert.equal(resolved.moduleValid, true);
    assert.equal(resolved.substitutions.length, 1);
    assert.equal(resolved.substitutions[0]?.role, "D");
    assert.equal(resolved.substitutions[0]?.outAthleteId, firstDefender);
    assert.equal(resolved.substitutions[0]?.inAthleteId, laterDefender);
    assert.equal(resolved.effectiveStarterIds[starterIds.indexOf(firstDefender)], laterDefender);

    const gkTried = resolveAutomaticSubstitutions({
      module: "4-3-3",
      starters,
      bench,
      playedAthleteIds: roster.filter((id) => id !== firstDefender).concat([benchKeeper]),
    });
    assert.equal(
      gkTried.substitutions.some((item) => item.inAthleteId === benchKeeper),
      false,
    );

    const sixHoles = starters.map((item) => item.athleteId);
    const sixPlayed = new Set(roster);
    for (const athleteId of sixHoles.slice(0, 6)) {
      sixPlayed.delete(athleteId);
    }
    const matchingBench = bench.filter((item) =>
      ["P", "D", "C", "A"].includes(item.role ?? ""),
    );
    for (const item of matchingBench) {
      sixPlayed.add(item.athleteId);
    }
    const capped = resolveAutomaticSubstitutions({
      module: "4-3-3",
      starters,
      bench,
      playedAthleteIds: [...sixPlayed],
    });
    assert.equal(capped.substitutions.length, 5);
    assert.equal(capped.substitutions[0]?.order, 1);
    assert.equal(capped.moduleValid, true);
  });

  it("consumes at most 3 tactical moves after kickoff and never on locked players", () => {
    assert.equal(MAX_TACTICAL_MOVES, 3);
    assert.equal(remainingTacticalMoves(0), 3);
    assert.equal(isTacticalWindowActive(false), false);

    const initial = evaluateTacticalMove({
      hasSavedLineup: false,
      anyAthleteLocked: true,
      movesUsed: 0,
      proposedModule: "4-3-3",
      proposedStarterIds: ["p1", "d1"],
      proposedBenchIds: ["d2"],
    });
    assert.equal(initial.wouldConsume, false);

    const beforeKickoff = evaluateTacticalMove({
      hasSavedLineup: true,
      anyAthleteLocked: false,
      movesUsed: 0,
      proposedModule: "4-3-3",
      proposedStarterIds: ["p1", "d2"],
      proposedBenchIds: ["d1"],
      previousModule: "4-3-3",
      previousStarterIds: ["p1", "d1"],
      previousBenchIds: ["d2"],
    });
    assert.equal(beforeKickoff.wouldConsume, false);

    const unchanged = evaluateTacticalMove({
      hasSavedLineup: true,
      anyAthleteLocked: true,
      movesUsed: 2,
      proposedModule: "4-3-3",
      proposedStarterIds: ["p1", "d1"],
      proposedBenchIds: ["d2"],
      previousModule: "4-3-3",
      previousStarterIds: ["p1", "d1"],
      previousBenchIds: ["d2"],
    });
    assert.equal(unchanged.wouldConsume, false);

    const consume = evaluateTacticalMove({
      hasSavedLineup: true,
      anyAthleteLocked: true,
      movesUsed: 0,
      proposedModule: "4-3-3",
      proposedStarterIds: ["p1", "d2"],
      proposedBenchIds: ["d1"],
      previousModule: "4-3-3",
      previousStarterIds: ["p1", "d1"],
      previousBenchIds: ["d2"],
    });
    assert.equal(consume.wouldConsume, true);
    assert.equal(consume.remainingAfter, 2);
    assert.deepEqual(consume.issues, []);

    const fourth = evaluateTacticalMove({
      hasSavedLineup: true,
      anyAthleteLocked: true,
      movesUsed: 3,
      proposedModule: "4-4-2",
      proposedStarterIds: ["p1", "d2"],
      proposedBenchIds: ["d1"],
      previousModule: "4-3-3",
      previousStarterIds: ["p1", "d1"],
      previousBenchIds: ["d2"],
    });
    assert.equal(fourth.wouldConsume, true);
    assert.ok(fourth.issues.some((item) => item.code === "tactical_moves_exhausted"));
  });

  it("counts one move after simultaneous kickoffs expressed in different timezones", () => {
    const now = "2026-08-15T16:00:00.000Z";
    const locked = ["locked-rome", "locked-utc"].filter((athleteId) =>
      isAthleteKickoffLocked(
        now,
        athleteId === "locked-rome" ? "2026-08-15T18:00:00+02:00" : "2026-08-15T16:00:00.000Z",
        "NS",
      ),
    );
    assert.deepEqual(locked, ["locked-rome", "locked-utc"]);
    const retroactive = evaluateProgressiveLock({
      previousSlots: slotsFromLineupIds(["locked-rome", "locked-utc"], ["future"]),
      proposedSlots: slotsFromLineupIds(["future", "locked-utc"], ["locked-rome"]),
      lockedAthleteIds: locked,
    });
    assert.ok(retroactive.some((item) => item.code === "athlete_kickoff_locked"));

    const allowed = evaluateTacticalMove({
      hasSavedLineup: true,
      anyAthleteLocked: true,
      movesUsed: 2,
      proposedModule: "4-3-3",
      proposedStarterIds: ["locked-rome", "locked-utc", "future-b"],
      proposedBenchIds: ["future-a"],
      previousModule: "4-3-3",
      previousStarterIds: ["locked-rome", "locked-utc", "future-a"],
      previousBenchIds: ["future-b"],
    });
    assert.equal(allowed.wouldConsume, true);
    assert.equal(allowed.remainingAfter, 0);
    assert.deepEqual(allowed.issues, []);
  });

  it("allows incomplete drafts but still rejects duplicates and foreign athletes", () => {
    const draft = evaluateLineup({
      module: "4-3-3",
      starters: [{ athleteId: "p-1", role: "P" }, { athleteId: "", role: null }],
      bench: [{ athleteId: "d-1", role: "D" }],
      rosterAthleteIds: ["p-1", "d-1", "c-1"],
      strict: false,
    });
    assert.equal(draft.valid, true);
    assert.equal(draft.issues.length, 0);

    const duplicate = evaluateLineup({
      module: "4-3-3",
      starters: [
        { athleteId: "p-1", role: "P" },
        { athleteId: "p-1", role: "P" },
      ],
      bench: [],
      rosterAthleteIds: ["p-1"],
      strict: false,
    });
    assert.equal(duplicate.valid, false);
    assert.ok(duplicate.issues.some((item) => item.code === "duplicate_athlete"));

    const foreign = evaluateLineup({
      module: "4-3-3",
      starters: [{ athleteId: "x-1", role: "P" }],
      bench: [],
      rosterAthleteIds: ["p-1"],
      strict: false,
    });
    assert.equal(foreign.valid, false);
    assert.ok(foreign.issues.some((item) => item.code === "athlete_not_in_roster"));
  });

  it("revalidates a copied lineup against current roster and kickoff availability", () => {
    const { roster, starters, bench } = valid433Roster();
    const starterIds = starters.map((item) => item.athleteId);
    const benchIds = bench.map((item) => item.athleteId);
    const droppedId = starterIds[4] ?? "";
    const currentRoster = roster.filter((id) => id !== droppedId);
    const roleByAthleteId: Record<string, "P" | "D" | "C" | "A"> = {};
    for (const player of [...starters, ...bench]) {
      if (player.role) {
        roleByAthleteId[player.athleteId] = player.role;
      }
    }

    const copied = copyPreviousLineup({
      previousModule: "4-3-3",
      previousStarterIds: starterIds,
      previousBenchIds: benchIds,
      rosterAthleteIds: currentRoster,
      roleByAthleteId,
    });
    assert.equal(copied.blocked, false);
    assert.equal(copied.canConfirm, false);
    assert.ok(copied.droppedAthleteIds.includes(droppedId));
    assert.ok(copied.issues.some((item) => item.code === "copied_athlete_not_in_roster"));
    assert.equal(copied.starterIds[4], "");
    assert.equal(copied.starterIds.includes(droppedId), false);
    assert.equal(copied.benchIds.includes(droppedId), false);
    assert.ok(currentRoster.every((id) => copied.starterIds.includes(id) || copied.benchIds.includes(id)));
  });

  it("does not copy locked athletes as new starters across simultaneous timezone kickoffs", () => {
    const now = "2026-08-15T16:00:00.000Z";
    const locked = ["locked-rome", "locked-utc"].filter((athleteId) =>
      isAthleteKickoffLocked(
        now,
        athleteId === "locked-rome" ? "2026-08-15T18:00:00+02:00" : "2026-08-15T16:00:00.000Z",
        "NS",
      ),
    );
    assert.deepEqual(locked, ["locked-rome", "locked-utc"]);

    const copied = copyPreviousLineup({
      previousModule: "4-3-3",
      previousStarterIds: ["locked-rome", "locked-utc", "p1", "d1", "d2", "d3", "c1", "c2", "a1", "a2", "a3"],
      previousBenchIds: ["bench-1"],
      rosterAthleteIds: [
        "locked-rome",
        "locked-utc",
        "p1",
        "d1",
        "d2",
        "d3",
        "c1",
        "c2",
        "a1",
        "a2",
        "a3",
        "bench-1",
      ],
      lockedAthleteIds: locked,
    });
    assert.equal(copied.starterIds[0], "");
    assert.equal(copied.starterIds[1], "");
    assert.ok(copied.unavailableAthleteIds.includes("locked-rome"));
    assert.ok(copied.unavailableAthleteIds.includes("locked-utc"));
    assert.ok(copied.benchIds.includes("locked-rome"));
    assert.ok(copied.benchIds.includes("locked-utc"));
    assert.ok(copied.issues.some((item) => item.code === "copied_athlete_unavailable"));
    assert.equal(copied.blocked, false);

    const blocked = copyPreviousLineup({
      previousModule: "4-3-3",
      previousStarterIds: ["future", "p1", "d1", "d2", "d3", "c1", "c2", "a1", "a2", "a3", "bench-1"],
      previousBenchIds: ["locked-rome"],
      rosterAthleteIds: [
        "future",
        "locked-rome",
        "p1",
        "d1",
        "d2",
        "d3",
        "c1",
        "c2",
        "a1",
        "a2",
        "a3",
        "bench-1",
      ],
      lockedAthleteIds: locked,
      currentConfirmedSlots: slotsFromLineupIds(
        ["locked-rome", "p1", "d1", "d2", "d3", "c1", "c2", "a1", "a2", "a3", "bench-1"],
        ["future"],
      ),
      currentConfirmedBench: ["future"],
    });
    assert.equal(blocked.blocked, true);
    assert.ok(blocked.issues.some((item) => item.code === "athlete_kickoff_locked"));
  });
});
