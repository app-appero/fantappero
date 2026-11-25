import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { LineupRole, LineupRosterPlayer } from "./fantasyLineups.ts";
import {
  APPROVED_MODULES,
  lockCountdownIdleLabel,
  copyPreviousLineup,
  blockingLineupSaveIssue,
  evaluateBenchOrderLock,
  planModuleChange,
  evaluateLineup,
  orderBenchForActiveRoles,
  benchActiveShortfall,
  benchQuotaSwapIds,
  formationLineupBench,
  restoreBenchActiveRoles,
  evaluateProgressiveLock,
  evaluateTacticalMove,
  isApprovedModule,
  athleteLockAt,
  earliestAthleteLockAt,
  isAthleteKickoffLocked,
  isLineupModificationAllowed,
  isTacticalWindowActive,
  keepStartersForModule,
  MAX_AUTOMATIC_SUBSTITUTIONS,
  MAX_TACTICAL_MOVES,
  moduleCounts,
  moveBenchItem,
  moveBenchToIndex,
  orderedBenchFromRoster,
  preserveLockedStarters,
  remainingRosterForBench,
  remainingTacticalMoves,
  rosterDepartureNotices,
  savedStarterSlotIds,
  resolveAutomaticSubstitutions,
  slotsFromLineupIds,
  starterTemplate,
  withoutRoleQuotaExcess,
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
  const bench = orderBenchForActiveRoles(remainingRosterForBench(roster, starterIds).map((athleteId) => {
    const role = athleteId.startsWith("p")
      ? "P"
      : athleteId.startsWith("d")
        ? "D"
        : athleteId.startsWith("c")
          ? "C"
          : "A";
    return { athleteId, role: role as "P" | "D" | "C" | "A" };
  }));
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

  it("richiede 1P·3D·3C·3A nei primi 10 della panchina (o quanto disponibile)", () => {
    const { roster, starters, bench } = valid433Roster();
    // Panchina in ordine di rosa: 2 portieri e 8 difensori nei primi 10 → non valida.
    const raw = [...bench].sort((x, y) => x.athleteId.localeCompare(y.athleteId));
    const bad = evaluateLineup({ module: "4-3-3", starters, bench: raw, rosterAthleteIds: roster });
    assert.ok(bad.issues.some((item) => item.code === "bench_roles_invalid"));
    assert.ok(Object.keys(benchActiveShortfall(raw)).length > 0);
    // Riordinata: valida.
    const ok = evaluateLineup({ module: "4-3-3", starters, bench: orderBenchForActiveRoles(raw), rosterAthleteIds: roster });
    assert.equal(ok.valid, true);
    // In bozza non si blocca.
    const draft = evaluateLineup({ module: "4-3-3", starters, bench: raw, rosterAthleteIds: roster, strict: false });
    assert.ok(!draft.issues.some((item) => item.code === "bench_roles_invalid"));
  });

  it("non pretende ruoli che la rosa non ha (solo 2 attaccanti in panchina)", () => {
    const starters = [
      ...players(["p1"], "P"), ...players(ids("d", 4), "D"), ...players(ids("c", 3), "C"), ...players(ids("a", 3), "A"),
    ];
    const bench = orderBenchForActiveRoles([
      ...players(["p2", "p3"], "P"), ...players(ids("dd", 4), "D"), ...players(ids("cc", 4), "C"), ...players(ids("aa", 2), "A"),
    ]);
    assert.deepEqual(benchActiveShortfall(bench), {});
    const first10 = bench.slice(0, 10);
    assert.equal(first10.filter((p) => p.role === "A").length, 2);
    assert.equal(first10.length, 10);
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

  it("anticipates the lock by the league margin (mirrors is_athlete_kickoff_locked)", () => {
    const kickoff = "2026-08-15T16:00:00.000Z";
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:44:59.000Z", kickoff, "NS", false, 15), false);
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:45:00.000Z", kickoff, "NS", false, 15), true);
    assert.equal(athleteLockAt("2026-08-15T15:00:00.000Z", kickoff, "NS", false, 15), "2026-08-15T15:45:00.000Z");
    assert.equal(athleteLockAt("2026-08-15T15:45:00.000Z", kickoff, "NS", false, 15), null);
    assert.equal(
      earliestAthleteLockAt(
        [
          { kickoffAt: "2026-08-15T18:30:00.000Z", fixtureStatus: "NS" },
          { kickoffAt: kickoff, fixtureStatus: "NS" },
        ],
        "2026-08-15T12:00:00.000Z",
        0,
      ),
      kickoff,
    );
    // Default margin (omitted) reproduces the previous exact-kickoff behavior.
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:45:00.000Z", kickoff, "NS"), false);
    // Started/latched/inactive statuses are unaffected by the margin.
    assert.equal(isAthleteKickoffLocked("2026-08-15T15:00:00.000Z", kickoff, "1H", false, 15), true);
    assert.equal(isAthleteKickoffLocked("2026-08-16T16:00:00.000Z", kickoff, "PST", false, 15), false);
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

  it("lets the platform operator past kickoff locks but never past exhausted tactical moves", () => {
    const lockIssues = evaluateProgressiveLock({
      previousSlots: {},
      proposedSlots: slotsFromLineupIds(["locked-a"], []),
      lockedAthleteIds: ["locked-a"],
    });
    const tacticalIssues = [
      { code: "tactical_moves_exhausted", message: "Mosse tattiche esaurite." },
    ];
    const member = blockingLineupSaveIssue({
      isPlatformOperator: false,
      lockIssues,
      tacticalIssues,
    });
    assert.equal(member?.code, "athlete_kickoff_locked");
    assert.equal(
      blockingLineupSaveIssue({
        isPlatformOperator: true,
        lockIssues,
        tacticalIssues,
      })?.code,
      "tactical_moves_exhausted",
    );
    assert.equal(
      blockingLineupSaveIssue({
        isPlatformOperator: true,
        lockIssues,
        tacticalIssues: [],
      }),
      null,
    );
    assert.equal(
      blockingLineupSaveIssue({
        isPlatformOperator: false,
        lockIssues: [],
        tacticalIssues,
      })?.code,
      "tactical_moves_exhausted",
    );
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

  it("never reserves the same locked athlete into two slots of the same role", () => {
    // `currentStarters` può ripetere lo stesso atleta bloccato (bozza in
    // corso + formazione confermata): senza deduplica finiva su due slot
    // difensivi diversi, duplicandolo in campo.
    const next = preserveLockedStarters({
      template: starterTemplate("4-3-3"),
      currentStarters: ["d1", "d1", "d2"],
      roster: [
        { athleteId: "d1", athleteName: "D1", role: "D", slotIndex: 0, locked: true },
        { athleteId: "d2", athleteName: "D2", role: "D", slotIndex: 1, locked: true },
      ],
    });
    const occurrences = next.filter((athleteId) => athleteId === "d1");
    assert.equal(occurrences.length, 1);
    assert.equal(next.filter((athleteId) => athleteId === "d2").length, 1);
  });

  it("RELOCATES a locked starter to the first free slot of its role", () => {
    // Comportamento voluto quando cambia il modulo, ma è anche la trappola
    // che ha duplicato i titolari in campo: il risultato NON va mai unito
    // slot-per-slot con la lista originale (`reserved[i] || original[i]`),
    // perché chi è stato spostato resterebbe anche nella posizione di
    // partenza. A template invariato non va usata affatto.
    const next = preserveLockedStarters({
      template: starterTemplate("4-3-3"), // [P, D, D, D, D, C, C, C, A, A, A]
      currentStarters: ["p1", "d1", "d2", "d3", "d4", "c1", "c2", "c3", "a1", "a2", "a3"],
      roster: [
        { athleteId: "d2", athleteName: "D2", role: "D", slotIndex: 0, locked: true },
      ],
    });
    // d2 stava in posizione 2, viene riservato nel primo slot D libero (1).
    assert.equal(next[1], "d2");
    assert.equal(next[2], "");
    // Unire ingenuamente con l'originale duplicherebbe d2 (slot 1 e slot 2).
    const naiveMerge = next.map((value, index) => value || ["p1", "d1", "d2"][index] || "");
    assert.equal(naiveMerge.filter((id) => id === "d2").length, 2);
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

  it("keeps a locked bench player at its number and same-role priority", () => {
    const roles = { a1: "A", c1: "C", "locked-a": "A", u2: "D", x: "C", a9: "A" };
    const previous = ["a1", "c1", "locked-a", "u2"];
    const check = (proposed: string[]) =>
      evaluateBenchOrderLock({
        previousBench: previous,
        proposedBench: proposed,
        lockedAthleteIds: ["locked-a"],
        roleByAthleteId: roles,
      });
    assert.ok(check(["c1", "locked-a", "u2"]).some((item) => item.code === "bench_order_locked"));
    assert.ok(check(["x", "c1", "locked-a", "u2"]).some((item) => item.code === "bench_order_locked"));
    assert.deepEqual(check(["a9", "c1", "locked-a", "u2"]), []);
  });

  it("allows a same-role one-for-one starter/bench swap before a locked bench player", () => {
    const previous = ["u1", "y", "locked-b", "u2"];
    const proposed = ["u1", "x", "locked-b", "u2"];
    const sameRole = { x: "A", y: "A", u1: "D", u2: "C", "locked-b": "C" };
    assert.deepEqual(
      evaluateBenchOrderLock({
        previousBench: previous,
        proposedBench: proposed,
        lockedAthleteIds: ["locked-b"],
        roleByAthleteId: sameRole,
      }),
      [],
    );
    const sameRoleLockedAfter = evaluateBenchOrderLock({
      previousBench: previous,
      proposedBench: proposed,
      lockedAthleteIds: ["locked-b"],
      roleByAthleteId: { ...sameRole, x: "D", "locked-b": "D" },
    });
    assert.ok(sameRoleLockedAfter.some((item) => item.code === "bench_order_locked"));
    assert.deepEqual(
      evaluateBenchOrderLock({
        previousBench: previous,
        proposedBench: proposed,
        lockedAthleteIds: ["locked-b"],
        roleByAthleteId: { ...sameRole, x: "D" },
      }),
      [],
    );
    const withoutRoles = evaluateBenchOrderLock({
      previousBench: previous,
      proposedBench: proposed,
      lockedAthleteIds: ["locked-b"],
    });
    assert.ok(withoutRoles.some((item) => item.code === "bench_order_locked"));
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

  describe("planModuleChange", () => {
    const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
    const P = ids("P", 3);
    const D = ids("D", 8);
    const C = ids("C", 8);
    const A = ids("A", 6);
    const roster = [...P, ...D, ...C, ...A];
    const roles: Record<string, string> = Object.fromEntries(roster.map((id) => [id, id[0] as string]));
    const starters = [P[0], ...D.slice(0, 4), ...C.slice(0, 3), ...A.slice(0, 3)] as string[];
    // Panchina attiva 1P·3D·3C·3A, poi tribuna.
    const bench = [P[1], D[4], D[5], D[6], C[3], C[4], C[5], A[3], A[4], A[5], P[2], D[7], C[6], C[7]] as string[];
    const base = {
      starterIds: starters,
      benchIds: bench,
      roleByAthleteId: roles,
      rosterAthleteIds: roster,
      previousStarterIds: starters,
      previousBenchIds: bench,
    };

    it("keeps locked players exactly where they are when the module changes", () => {
      const locked = ["D1", "A4", "C7"];
      const plan = planModuleChange({ ...base, module: "4-4-2", lockedAthleteIds: locked });
      assert.ok(plan);
      assert.ok(plan.starterIds.includes("D1"));
      assert.equal(plan.benchIds.indexOf("A4"), bench.indexOf("A4"));
      assert.equal(plan.benchIds.indexOf("C7"), bench.indexOf("C7"));
      assert.equal(plan.starterIds.filter((id) => roles[id] === "C").length, 4);
      assert.equal(plan.starterIds.filter((id) => roles[id] === "A").length, 2);
      const asPlayers = (list: string[]) => list.map((athleteId) => ({ athleteId, role: roles[athleteId] as "P" }));
      assert.ok(
        evaluateLineup({
          module: "4-4-2",
          starters: asPlayers(plan.starterIds),
          bench: asPlayers(plan.benchIds),
          rosterAthleteIds: roster,
        }).valid,
      );
      assert.deepEqual(
        evaluateBenchOrderLock({
          previousBench: bench,
          proposedBench: plan.benchIds,
          lockedAthleteIds: locked,
          roleByAthleteId: roles,
        }),
        [],
      );
    });

    it("refuses a module that would push a locked starter off the pitch", () => {
      const plan = planModuleChange({ ...base, module: "4-4-2", lockedAthleteIds: ["A1", "A2", "A3"] });
      assert.equal(plan, null);
    });

    it("refuses a module that needs a locked bench player on the pitch", () => {
      // 4-4-2 → serve un centrocampista in più, ma tutti quelli in panchina e tribuna sono bloccati.
      const plan = planModuleChange({
        ...base,
        module: "4-4-2",
        lockedAthleteIds: ["C4", "C5", "C6", "C7", "C8"],
      });
      assert.equal(plan, null);
    });
  });

  describe("keepStartersForModule", () => {
    const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
    const P = ids("P", 3);
    const D = ids("D", 8);
    const C = ids("C", 8);
    const A = ids("A", 6);
    const rosterIds = [...P, ...D, ...C, ...A];
    const roster = (overrides: Record<string, Partial<LineupRosterPlayer>> = {}): LineupRosterPlayer[] =>
      rosterIds.map((athleteId, slotIndex) => ({
        athleteId,
        athleteName: athleteId,
        role: athleteId[0] as LineupRole,
        slotIndex,
        locked: false,
        ...overrides[athleteId],
      }));
    // 4-3-3 completo, poi panchina attiva 1P·3D·3C·3A e tribuna.
    const starters433 = [P[0], ...D.slice(0, 4), ...C.slice(0, 3), ...A.slice(0, 3)] as string[];
    const bench = [P[1], D[4], D[5], D[6], C[3], C[4], C[5], A[3], A[4], A[5], P[2], D[7], C[6], C[7]] as string[];

    it("4-3-3 → 4-4-2: tiene 4 D e 3 C, lascia vuoto il quarto C e tiene 2 dei 3 A", () => {
      const plan = keepStartersForModule({
        module: "4-4-2",
        currentStarters: starters433,
        benchIds: bench,
        roster: roster(),
      });
      // Template 4-4-2: [P, D, D, D, D, C, C, C, C, A, A].
      assert.deepEqual(plan.starterIds, ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "", "A1", "A2"]);
      assert.equal(starterTemplate("4-4-2")[8], "C");
      // Il terzo attaccante torna in panchina, in coda: l'ordine di chi c'era già resta.
      assert.deepEqual(plan.benchIds, [...bench, "A3"]);
    });

    it("riserva prima i bloccati (anche con l'anticipo del blocco), poi i titolari nel loro ordine", () => {
      const now = "2026-11-22T13:50:00.000Z";
      const rows = roster({
        D3: { locked: true },
        // Partita alle 14:00: bloccato solo con un anticipo di almeno 10 minuti.
        D4: { kickoffAt: "2026-11-22T14:00:00.000Z" },
      });
      const withMargin = keepStartersForModule({
        module: "3-4-3",
        currentStarters: starters433,
        benchIds: bench,
        roster: rows,
        now,
        lockMarginMinutes: 15,
      });
      // Template 3-4-3: [P, D, D, D, C, C, C, C, A, A, A]. D3 e D4 bloccati passano davanti a D1 e D2.
      assert.deepEqual(withMargin.starterIds, ["P1", "D3", "D4", "D1", "C1", "C2", "C3", "", "A1", "A2", "A3"]);
      assert.deepEqual(withMargin.benchIds, [...bench, "D2"]);

      const withoutMargin = keepStartersForModule({
        module: "3-4-3",
        currentStarters: starters433,
        benchIds: bench,
        roster: rows,
        now,
      });
      assert.deepEqual(withoutMargin.starterIds.slice(1, 4), ["D3", "D1", "D2"]);
      assert.deepEqual(withoutMargin.benchIds, [...bench, "D4"]);
    });

    it("non duplica nessuno, nemmeno se la lista dei titolari ripete un calciatore", () => {
      const plan = keepStartersForModule({
        module: "4-4-2",
        currentStarters: ["D2", "P1", "D1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A1", "A2"],
        benchIds: bench,
        roster: roster({ D2: { locked: true } }),
      });
      const placed = plan.starterIds.filter(Boolean);
      assert.equal(new Set(placed).size, placed.length);
      assert.equal(new Set(plan.benchIds).size, plan.benchIds.length);
      assert.ok(placed.every((athleteId) => !plan.benchIds.includes(athleteId)));
      // Ognuno è in campo o in panchina, una volta sola.
      assert.deepEqual([...placed, ...plan.benchIds].sort(), [...rosterIds].sort());
      assert.deepEqual(plan.starterIds, ["P1", "D2", "D1", "D3", "D4", "C1", "C2", "C3", "", "A1", "A2"]);
    });

    it("chi è in esubero di ruolo non entra nella panchina della formazione (QA 19/11)", () => {
      // A6 in esubero: web e app lo mettevano in coda alla panchina e il server rifiutava tutto.
      const plan = keepStartersForModule({
        module: "4-4-2",
        currentStarters: starters433,
        benchIds: bench,
        roster: roster({ A6: { exceedsRoleQuota: true } }),
      });
      assert.deepEqual(plan.benchIds, [...bench.filter((athleteId) => athleteId !== "A6"), "A3"]);
    });

    it("un bloccato senza posto nel nuovo modulo non prende lo slot di un altro ruolo", () => {
      // 4-5-1 ha un solo attaccante: A2 bloccato resta fuori, chi chiama deve rifiutare il modulo.
      const plan = keepStartersForModule({
        module: "4-5-1",
        currentStarters: starters433,
        benchIds: bench,
        roster: roster({ A1: { locked: true }, A2: { locked: true } }),
      });
      assert.equal(plan.starterIds[10], "A1");
      assert.ok(!plan.starterIds.includes("A2"));
      assert.ok(!plan.starterIds.includes("A3"));
    });
  });
});

describe("formazione con chi non è più in rosa (QA 19/11)", () => {
  it("rosterDepartureNotices prende solo gli avvisi «non è più nella tua rosa»", () => {
    const notice = "N. Zortea non è più nella tua rosa: è stato tolto dalla formazione, scegli chi mettere al suo posto.";
    assert.deepEqual(
      rosterDepartureNotices([
        { code: "lineup_athlete_left_roster", message: notice },
        { code: "bench_incomplete", message: "Tutti i calciatori in rosa devono essere schierati: manca 1 in panchina." },
      ]),
      [notice],
    );
    assert.deepEqual(rosterDepartureNotices(undefined), []);
  });

  it("savedStarterSlotIds lascia vuoto il posto di chi è stato tolto, gli altri non scalano", () => {
    const starters = ["P1", "D1", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"].map((athleteId, index) => ({
      athleteId,
      sortOrder: index < 2 ? index : index + 1,
    }));
    assert.deepEqual(savedStarterSlotIds(starters, 11), [
      "P1", "D1", "", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3",
    ]);
  });

  it("savedStarterSlotIds con una formazione completa resta nell'ordine salvato", () => {
    const ids = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
    assert.deepEqual(savedStarterSlotIds(ids.map((athleteId, sortOrder) => ({ athleteId, sortOrder })), 11), ids);
    assert.deepEqual(savedStarterSlotIds([], 11), Array.from({ length: 11 }, () => ""));
  });

  it("savedStarterSlotIds mette nel primo posto libero un sortOrder fuori modulo o doppio", () => {
    assert.deepEqual(
      savedStarterSlotIds(
        [
          { athleteId: "P1", sortOrder: 0 },
          { athleteId: "D1", sortOrder: 0 },
          { athleteId: "D2", sortOrder: 20 },
        ],
        4,
      ),
      ["P1", "D1", "D2", ""],
    );
  });
});

describe("withoutRoleQuotaExcess (QA 19/11, qa-02)", () => {
  const roster = [
    { athleteId: "A1" },
    { athleteId: "A2", exceedsRoleQuota: true },
    { athleteId: "A3", exceedsRoleQuota: false },
  ];

  it("toglie chi è in esubero di ruolo e lascia gli altri nel loro ordine", () => {
    assert.deepEqual(withoutRoleQuotaExcess(["A3", "A2", "A1"], roster), ["A3", "A1"]);
    // Gli id della rosa per la panchina: con la rosa intera lui finiva in coda alla panchina.
    assert.deepEqual(
      orderedBenchFromRoster(withoutRoleQuotaExcess(["A1", "A2", "A3"], roster), ["A1"], ["A3"]),
      ["A3"],
    );
  });

  it("senza nessuno in esubero, o con chi non è in rosa, non cambia niente", () => {
    assert.deepEqual(withoutRoleQuotaExcess(["A1", "A3", "X9"], roster), ["A1", "A3", "X9"]);
    assert.deepEqual(withoutRoleQuotaExcess(["A1", "A2"], []), ["A1", "A2"]);
    assert.deepEqual(withoutRoleQuotaExcess([], roster), []);
  });
});

describe("panchina con un portiere al posto di un attaccante (Rosario, 20/11)", () => {
  type Role = "P" | "D" | "C" | "A";
  const players = (ids: readonly string[]) => ids.map((athleteId) => ({ athleteId, role: athleteId[0] as Role }));
  const idsOf = (list: readonly { athleteId: string }[]) => list.map((player) => player.athleteId);
  // 4-4-2: l'attaccante 8° in panchina è uscito dalla rosa, P3 (primo della tribuna) è salito al 10°.
  const dirty = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "P3", "D8", "C8", "A5"];

  it("restoreBenchActiveRoles fa salire il primo attaccante della tribuna al posto del portiere in più", () => {
    assert.deepEqual(benchActiveShortfall(players(dirty)), { A: 1 });
    const repair = restoreBenchActiveRoles(players(dirty));
    assert.deepEqual(idsOf(repair.bench), ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "A5", "P3", "D8", "C8"]);
    assert.deepEqual(repair.missing, {});
    assert.equal(repair.message, null);
    // A differenza di orderBenchForActiveRoles (blocchi P→D→C→A) il resto non si muove.
    const mixed = players(["D5", "P2", "D6", "D7", "C5", "C6", "C7", "A3", "D9", "P3", "A4", "A6"]);
    assert.deepEqual(idsOf(restoreBenchActiveRoles(mixed).bench), [
      "D5", "P2", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "A6", "D9", "P3",
    ]);
  });

  it("non sposta né scavalca chi ha la partita già iniziata, e dice quale ruolo manca", () => {
    // P2 (1°) è bloccato: scende P3 dal 10° posto, l'attaccante prende il suo posto.
    const repair = restoreBenchActiveRoles(players(dirty), { lockedAthleteIds: ["P2"] });
    assert.deepEqual(idsOf(repair.bench), ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "A5", "P3", "D8", "C8"]);
    // P3 (10°) è bloccato: per far salire A5 bisognerebbe scavalcarlo.
    const stuck = restoreBenchActiveRoles(players(dirty), { lockedAthleteIds: ["P3"] });
    assert.deepEqual(idsOf(stuck.bench), dirty);
    assert.deepEqual(stuck.moves, []);
    assert.deepEqual(stuck.missing, { A: 1 });
    assert.match(stuck.message ?? "", /mancano: 1 attaccante/);
    assert.match(stuck.message ?? "", /gli attaccanti in tribuna c'è chi ha la partita già iniziata/);
    const none = restoreBenchActiveRoles(players(dirty), { lockedAthleteIds: ["A5"] });
    assert.match(none.message ?? "", /in tribuna non ci sono attaccanti schierabili/);
  });

  it("come sul server, chi di sicuro non prende il voto non alza la quota dei primi 10", () => {
    assert.deepEqual(benchActiveShortfall(players(dirty), ["A5"]), {});
    assert.equal(restoreBenchActiveRoles(players(dirty), { unfieldableAthleteIds: ["A5"] }).moves.length, 0);
    assert.deepEqual(benchQuotaSwapIds(players(dirty), 9, ["A5"]), []);
  });

  it("benchQuotaSwapIds: «Cambia» sul portiere in più propone l'attaccante della tribuna", () => {
    assert.deepEqual(benchQuotaSwapIds(players(dirty), 9), ["A5"]);
    assert.deepEqual(benchQuotaSwapIds(players(dirty), 12), ["P2", "P3"]);
    assert.deepEqual(benchQuotaSwapIds(players(dirty), 3), []);
  });

  it("formationLineupBench rispetta il posto scelto per chi è arrivato dopo e non prende il voto", () => {
    const saved = dirty.slice(0, 12);
    const placed = idsOf(restoreBenchActiveRoles(players(dirty)).bench);
    const isBlocked = (athleteId: string) => athleteId === "A5";
    assert.deepEqual(formationLineupBench({ orderedBench: placed, savedBench: saved, placedBench: placed, isBlocked }), placed);
    // Senza un posto scelto va in coda, come prima.
    assert.deepEqual(
      formationLineupBench({ orderedBench: ["A5", ...saved], savedBench: saved, placedBench: saved, isBlocked }),
      [...saved, "A5"],
    );
  });
});

describe("conto alla rovescia senza blocchi da contare", () => {
  it("un turno di riferimento saltato si legge «Turno saltato» (Rosario, 21/11)", () => {
    assert.equal(lockCountdownIdleLabel("turn_not_open", "skipped"), "Turno saltato");
    assert.equal(lockCountdownIdleLabel("turn_not_open", "scheduled"), "Turno non ancora aperto");
    assert.equal(lockCountdownIdleLabel("turn_not_open"), "Turno non ancora aperto");
    assert.equal(lockCountdownIdleLabel("no_active_turn", "skipped"), "Nessun turno attivo");
    assert.equal(lockCountdownIdleLabel("counting_down"), "");
  });
});
