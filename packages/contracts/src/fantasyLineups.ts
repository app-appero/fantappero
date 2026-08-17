/** Valid modules, substitutions, copy/draft and tactical-move rules shared by API and UI (EP06-02 / EP06-04 / EP06-05 / EP06-06). */

import type { FantasyTurnStatus } from "./fantasyTurns.js";

export type FantasyModule =
  | "3-4-3"
  | "3-5-2"
  | "4-3-3"
  | "4-4-2"
  | "4-5-1"
  | "5-3-2"
  | "5-4-1";

export type LineupRole = "P" | "D" | "C" | "A";

export type LineupSlotKind = "starter" | "bench";

export interface ModuleCounts {
  code: FantasyModule;
  goalkeepers: 1;
  defenders: number;
  midfielders: number;
  forwards: number;
}

export interface LineupIssue {
  code: string;
  message: string;
}

export interface LineupPlayerInput {
  athleteId: string;
  role: LineupRole | null;
}

export interface LineupEvaluation {
  valid: boolean;
  issues: LineupIssue[];
  starterCounts: Record<LineupRole, number>;
}

export interface LineupPlayer {
  athleteId: string;
  athleteName: string;
  role: LineupRole;
  slotKind: LineupSlotKind;
  sortOrder: number;
}

export interface LineupRosterPlayer {
  athleteId: string;
  athleteName: string;
  role: LineupRole | null;
  slotIndex: number;
  locked?: boolean;
  lockLatched?: boolean;
  kickoffAt?: string | null;
  fixtureStatus?: string | null;
}

export interface SavedLineup {
  id: string;
  module: FantasyModule;
  revision: number;
  submittedAt: string;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
}

export interface PreviousLineupSummary {
  roundId: string;
  roundNumber: number;
  module: FantasyModule;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
}

export interface LineupDraft {
  module: FantasyModule;
  starterAthleteIds: string[];
  benchAthleteIds: string[];
  savedAt: string;
  copySourceRoundId?: string | null;
  copySourceRoundNumber?: number | null;
}

export interface LineupSubstitution {
  outAthleteId: string;
  inAthleteId: string;
  role: LineupRole;
  order: number;
}

export interface SubstitutionResolution {
  substitutions: LineupSubstitution[];
  effectiveStarterIds: string[];
  moduleValid: boolean;
}

export type TacticalMoveStatus = "applied";

export interface TacticalMoveSummary {
  sequence: number;
  status: TacticalMoveStatus;
  usedAt: string;
  fromModule: string;
  toModule: string;
}

export interface TacticalMoveEvaluation {
  wouldConsume: boolean;
  remainingAfter: number;
  issues: LineupIssue[];
}

export interface LineupContext {
  leagueId: string;
  roundId: string;
  roundNumber: number;
  kind: string;
  cutoffAt: string | null;
  status: FantasyTurnStatus;
  effectiveStatus: FantasyTurnStatus;
  modificationAllowed: boolean;
  serverNow?: string;
  maxAutomaticSubstitutions?: number;
  maxTacticalMoves?: number;
  tacticalMovesUsed?: number;
  tacticalMovesRemaining?: number;
  tacticalMoves?: TacticalMoveSummary[];
  modules: ModuleCounts[];
  roster: LineupRosterPlayer[];
  lineup: SavedLineup | null;
  previousLineup?: PreviousLineupSummary | null;
  draft?: LineupDraft | null;
  copyAvailable?: boolean;
  copyIssues?: LineupIssue[];
  issues: LineupIssue[];
}

export interface SaveLineupRequest {
  module: FantasyModule;
  starterAthleteIds: string[];
  benchAthleteIds: string[];
}

export interface SaveLineupDraftRequest {
  module: FantasyModule;
  starterAthleteIds: string[];
  benchAthleteIds: string[];
}

export interface CopyLineupResult {
  module: string;
  starterIds: string[];
  benchIds: string[];
  droppedAthleteIds: string[];
  unavailableAthleteIds: string[];
  issues: LineupIssue[];
  blocked: boolean;
  canConfirm: boolean;
}

export const APPROVED_MODULES: readonly FantasyModule[] = [
  "3-4-3",
  "3-5-2",
  "4-3-3",
  "4-4-2",
  "4-5-1",
  "5-3-2",
  "5-4-1",
];

const MODULE_OUTFIELD: Record<FantasyModule, readonly [number, number, number]> = {
  "3-4-3": [3, 4, 3],
  "3-5-2": [3, 5, 2],
  "4-3-3": [4, 3, 3],
  "4-4-2": [4, 4, 2],
  "4-5-1": [4, 5, 1],
  "5-3-2": [5, 3, 2],
  "5-4-1": [5, 4, 1],
};

export function isApprovedModule(value: string): value is FantasyModule {
  return (APPROVED_MODULES as readonly string[]).includes(value);
}

export function moduleCounts(code: FantasyModule): ModuleCounts {
  const [defenders, midfielders, forwards] = MODULE_OUTFIELD[code];
  return { code, goalkeepers: 1, defenders, midfielders, forwards };
}

export function approvedModuleCatalog(): ModuleCounts[] {
  return APPROVED_MODULES.map(moduleCounts);
}

/** Starter slots in P → D → C → A order for the given module. */
export function starterTemplate(code: FantasyModule): LineupRole[] {
  const counts = moduleCounts(code);
  return [
    ...Array.from({ length: counts.goalkeepers }, () => "P" as const),
    ...Array.from({ length: counts.defenders }, () => "D" as const),
    ...Array.from({ length: counts.midfielders }, () => "C" as const),
    ...Array.from({ length: counts.forwards }, () => "A" as const),
  ];
}

function emptyCounts(): Record<LineupRole, number> {
  return { P: 0, D: 0, C: 0, A: 0 };
}

function countRoles(players: readonly LineupPlayerInput[]): Record<LineupRole, number> {
  const counts = emptyCounts();
  for (const player of players) {
    if (player.role === "P" || player.role === "D" || player.role === "C" || player.role === "A") {
      counts[player.role] += 1;
    }
  }
  return counts;
}

function issue(code: string, message: string): LineupIssue {
  return { code, message };
}

/** Pure lineup validation: 7 modules, 1 GK, 11 starters, P–D–C–A and roster membership. */
export function evaluateLineup(input: {
  module: string;
  starters: readonly LineupPlayerInput[];
  bench: readonly LineupPlayerInput[];
  rosterAthleteIds: readonly string[];
  /** Confirmed save is strict; drafts may be incomplete (EP06-06). */
  strict?: boolean;
}): LineupEvaluation {
  const strict = input.strict !== false;
  const issues: LineupIssue[] = [];
  const starterCounts = countRoles(input.starters);

  if (!isApprovedModule(input.module)) {
    issues.push(issue("invalid_module", "Modulo non ammesso. Scegli uno dei sette moduli validi."));
  }

  const starterIds = input.starters.map((player) => player.athleteId);
  const benchIds = input.bench.map((player) => player.athleteId);
  const allIds = [...starterIds, ...benchIds];
  const seen = new Set<string>();
  let missingSlot = false;
  for (const athleteId of allIds) {
    if (!athleteId) {
      missingSlot = true;
      continue;
    }
    if (seen.has(athleteId)) {
      issues.push(
        issue("duplicate_athlete", "Lo stesso calciatore non può comparire più di una volta in formazione."),
      );
    }
    seen.add(athleteId);
  }
  if (strict && missingSlot) {
    issues.push(issue("missing_athlete", "Ogni slot della formazione deve contenere un calciatore."));
  }

  const rosterSet = new Set(input.rosterAthleteIds.filter(Boolean));
  for (const athleteId of allIds) {
    if (athleteId && !rosterSet.has(athleteId)) {
      issues.push(
        issue("athlete_not_in_roster", "Uno o più calciatori schierati non appartengono alla rosa."),
      );
      break;
    }
  }

  const filledStarters = strict ? input.starters : input.starters.filter((player) => player.athleteId);
  const filledBench = strict ? input.bench : input.bench.filter((player) => player.athleteId);
  if (filledStarters.some((player) => player.role == null)) {
    issues.push(
      issue("unresolved_role", "Uno o più titolari non hanno un ruolo listone risolvibile (P–D–C–A)."),
    );
  }
  if (filledBench.some((player) => player.role == null)) {
    issues.push(
      issue("unresolved_role", "Uno o più panchinari non hanno un ruolo listone risolvibile (P–D–C–A)."),
    );
  }

  if (strict && input.starters.length !== 11) {
    issues.push(
      issue(
        "starter_count_invalid",
        `La formazione deve avere esattamente 11 titolari (attuali: ${input.starters.length}).`,
      ),
    );
  }

  if (strict && starterCounts.P !== 1) {
    issues.push(
      issue(
        "goalkeeper_count_invalid",
        `Serve esattamente 1 portiere titolare (attuali: ${starterCounts.P}).`,
      ),
    );
  }

  if (strict && isApprovedModule(input.module)) {
    const expected = moduleCounts(input.module);
    if (
      starterCounts.D !== expected.defenders ||
      starterCounts.C !== expected.midfielders ||
      starterCounts.A !== expected.forwards
    ) {
      issues.push(
        issue(
          "module_role_mismatch",
          `Il modulo ${input.module} richiede ${expected.defenders}D–${expected.midfielders}C–${expected.forwards}A titolari ` +
            `(attuali: ${starterCounts.D}D–${starterCounts.C}C–${starterCounts.A}A).`,
        ),
      );
    }
  }

  const unusedRoster = input.rosterAthleteIds.filter((id) => id && !seen.has(id));
  if (strict && unusedRoster.length > 0) {
    issues.push(
      issue(
        "bench_incomplete",
        `Tutti i calciatori in rosa devono essere schierati: mancano ${unusedRoster.length} in panchina.`,
      ),
    );
  }

  const uniqueIssues = issues.filter(
    (item, index) => issues.findIndex((other) => other.code === item.code && other.message === item.message) === index,
  );

  return {
    valid: uniqueIssues.length === 0,
    issues: uniqueIssues,
    starterCounts,
  };
}

function ensureUtcMs(value: string | Date): number {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.getTime();
}

const STARTED_FIXTURE_STATUSES = new Set([
  "1H",
  "HT",
  "2H",
  "ET",
  "BT",
  "P",
  "LIVE",
  "INT",
  "SUSP",
  "FT",
  "AET",
  "PEN",
]);

const INACTIVE_FIXTURE_STATUSES = new Set(["PST", "CANC", "ABD", "AWD", "WO"]);

/**
 * True when the athlete's real match has started. Server clock is authoritative;
 * simultaneous kickoffs lock together at the same UTC instant.
 */
export function isAthleteKickoffLocked(
  now: string | Date,
  kickoffAt: string | Date | null | undefined,
  statusShort?: string | null,
  lockLatched?: boolean,
): boolean {
  if (lockLatched) {
    return true;
  }
  const status = (statusShort ?? "").trim().toUpperCase();
  if (STARTED_FIXTURE_STATUSES.has(status)) {
    return true;
  }
  if (INACTIVE_FIXTURE_STATUSES.has(status)) {
    return false;
  }
  if (!kickoffAt) {
    return false;
  }
  return ensureUtcMs(now) >= ensureUtcMs(kickoffAt);
}

export function evaluateProgressiveLock(input: {
  previousSlots: Readonly<Record<string, LineupSlotKind>>;
  proposedSlots: Readonly<Record<string, LineupSlotKind>>;
  lockedAthleteIds: readonly string[];
}): LineupIssue[] {
  const issues: LineupIssue[] = [];
  for (const athleteId of input.lockedAthleteIds) {
    const previous = input.previousSlots[athleteId];
    const proposed = input.proposedSlots[athleteId];
    if (previous == null) {
      if (proposed === "starter") {
        issues.push(
          issue(
            "athlete_kickoff_locked",
            "Uno o più calciatori non sono più modificabili: la loro partita è già iniziata.",
          ),
        );
      }
      continue;
    }
    if (proposed !== previous) {
      issues.push(
        issue(
          "athlete_kickoff_locked",
          "Uno o più calciatori non sono più modificabili: la loro partita è già iniziata.",
        ),
      );
    }
  }
  return issues.filter(
    (item, index) => issues.findIndex((other) => other.code === item.code && other.message === item.message) === index,
  );
}

export function slotsFromLineupIds(
  starterAthleteIds: readonly string[],
  benchAthleteIds: readonly string[],
): Record<string, LineupSlotKind> {
  const slots: Record<string, LineupSlotKind> = {};
  for (const athleteId of starterAthleteIds) {
    if (athleteId) {
      slots[athleteId] = "starter";
    }
  }
  for (const athleteId of benchAthleteIds) {
    if (athleteId) {
      slots[athleteId] = "bench";
    }
  }
  return slots;
}

/** Keep locked starters in the new module template (same role slots first). */
export function preserveLockedStarters(input: {
  template: readonly LineupRole[];
  currentStarters: readonly string[];
  roster: readonly LineupRosterPlayer[];
  now?: string | Date;
}): string[] {
  const next = input.template.map(() => "");
  const rosterById = new Map(input.roster.map((row) => [row.athleteId, row]));
  for (const athleteId of input.currentStarters) {
    const player = rosterById.get(athleteId);
    if (!player?.role) {
      continue;
    }
    const locked =
      player.locked === true ||
      (input.now != null &&
        isAthleteKickoffLocked(input.now, player.kickoffAt, player.fixtureStatus, player.lockLatched));
    if (!locked) {
      continue;
    }
    const slot = next.findIndex((value, index) => !value && input.template[index] === player.role);
    if (slot >= 0) {
      next[slot] = athleteId;
    }
  }
  return next;
}

/**
 * Turn-level gate: progressive per-player lock stays available on open/locked turns.
 * Kickoff cutoff no longer freezes the whole lineup (EP06-03).
 */
export function isLineupModificationAllowed(stored: FantasyTurnStatus): boolean {
  return stored === "open" || stored === "locked";
}

export function remainingRosterForBench(
  rosterAthleteIds: readonly string[],
  starterAthleteIds: readonly string[],
): string[] {
  const used = new Set(starterAthleteIds.filter(Boolean));
  return rosterAthleteIds.filter((id) => id && !used.has(id));
}

/** Maximum automatic substitutions applied from the ordered bench (EP06-04 / FR-SUB-01). */
export const MAX_AUTOMATIC_SUBSTITUTIONS = 5;

/** Maximum tactical moves per european turn (EP06-05 / FR-FOR-02). */
export const MAX_TACTICAL_MOVES = 3;

const TACTICAL_MOVES_EXHAUSTED_MESSAGE =
  "Hai già usato le 3 mosse tattiche di questo turno. Non puoi più modificare i calciatori ancora sbloccati.";

const BENCH_ORDER_LOCKED_MESSAGE =
  "Non puoi cambiare l'ordine di panchina di un calciatore la cui partita è già iniziata.";

/**
 * Keep the saved bench order for players still on the bench; append newcomers at the end.
 */
export function orderedBenchFromRoster(
  rosterAthleteIds: readonly string[],
  starterAthleteIds: readonly string[],
  previousBenchOrder: readonly string[] = [],
): string[] {
  const remaining = remainingRosterForBench(rosterAthleteIds, starterAthleteIds);
  const remainingSet = new Set(remaining);
  const ordered: string[] = [];
  for (const athleteId of previousBenchOrder) {
    if (remainingSet.has(athleteId)) {
      ordered.push(athleteId);
      remainingSet.delete(athleteId);
    }
  }
  for (const athleteId of remaining) {
    if (remainingSet.has(athleteId)) {
      ordered.push(athleteId);
    }
  }
  return ordered;
}

export function moveBenchToIndex(
  benchAthleteIds: readonly string[],
  fromIndex: number,
  toIndex: number,
): string[] {
  const next = [...benchAthleteIds];
  if (
    fromIndex === toIndex ||
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= next.length ||
    toIndex >= next.length
  ) {
    return next;
  }
  const [moved] = next.splice(fromIndex, 1);
  if (moved === undefined) {
    return [...benchAthleteIds];
  }
  next.splice(toIndex, 0, moved);
  return next;
}

export function moveBenchItem(
  benchAthleteIds: readonly string[],
  index: number,
  direction: -1 | 1,
): string[] {
  return moveBenchToIndex(benchAthleteIds, index, index + direction);
}

/**
 * Locked bench players are fences: remaining players cannot cross them, and
 * newcomers must stay after every locked player still on the bench.
 */
export function evaluateBenchOrderLock(input: {
  previousBench: readonly string[];
  proposedBench: readonly string[];
  lockedAthleteIds: readonly string[];
}): LineupIssue[] {
  const locked = new Set(input.lockedAthleteIds.filter(Boolean));
  const previous = input.previousBench.filter(Boolean);
  const proposed = input.proposedBench.filter(Boolean);
  if (locked.size === 0 || previous.length === 0) {
    return [];
  }

  const previousSet = new Set(previous);
  const proposedSet = new Set(proposed);
  const common: string[] = [];
  for (const athleteId of previous) {
    if (proposedSet.has(athleteId)) {
      common.push(athleteId);
    }
  }
  const lockedRemaining = previous.filter((athleteId) => locked.has(athleteId) && proposedSet.has(athleteId));
  const issues: LineupIssue[] = [];

  for (const lockedId of lockedRemaining) {
    const previousIndex = previous.indexOf(lockedId);
    const proposedIndex = proposed.indexOf(lockedId);
    for (const other of common) {
      if (other === lockedId) {
        continue;
      }
      const wasBefore = previous.indexOf(other) < previousIndex;
      const nowBefore = proposed.indexOf(other) < proposedIndex;
      if (wasBefore !== nowBefore) {
        issues.push(issue("bench_order_locked", BENCH_ORDER_LOCKED_MESSAGE));
        break;
      }
    }
    if (issues.length > 0) {
      break;
    }
  }

  if (lockedRemaining.length > 0 && issues.length === 0) {
    const lastLockedProposed = Math.max(...lockedRemaining.map((athleteId) => proposed.indexOf(athleteId)));
    for (const athleteId of proposed) {
      if (!previousSet.has(athleteId) && proposed.indexOf(athleteId) < lastLockedProposed) {
        issues.push(issue("bench_order_locked", BENCH_ORDER_LOCKED_MESSAGE));
        break;
      }
    }
  }

  return issues.filter(
    (item, index) => issues.findIndex((other) => other.code === item.code && other.message === item.message) === index,
  );
}

/**
 * Walk the ordered bench: a player with a vote replaces the first same-role
 * starter without a vote. Stops at {@link MAX_AUTOMATIC_SUBSTITUTIONS}.
 * Same-role replacements keep the module valid. Match minutes/votes are an
 * input (EP07-04 applies them after final data); this engine is pure.
 */
export function resolveAutomaticSubstitutions(input: {
  module: string;
  starters: readonly LineupPlayerInput[];
  bench: readonly LineupPlayerInput[];
  playedAthleteIds: readonly string[];
}): SubstitutionResolution {
  const played = new Set(input.playedAthleteIds.filter(Boolean));
  const substitutions: LineupSubstitution[] = [];
  const replaced = new Set<string>();
  const effectiveStarterIds = input.starters.map((player) => player.athleteId);
  const roleByAthlete = new Map<string, LineupRole | null>();
  for (const player of [...input.starters, ...input.bench]) {
    if (player.athleteId) {
      roleByAthlete.set(player.athleteId, player.role);
    }
  }

  for (const benchPlayer of input.bench) {
    if (substitutions.length >= MAX_AUTOMATIC_SUBSTITUTIONS) {
      break;
    }
    if (!benchPlayer.athleteId || !played.has(benchPlayer.athleteId) || benchPlayer.role == null) {
      continue;
    }
    const starterIndex = input.starters.findIndex((starter) => {
      if (!starter.athleteId || replaced.has(starter.athleteId) || starter.role !== benchPlayer.role) {
        return false;
      }
      return !played.has(starter.athleteId);
    });
    if (starterIndex < 0) {
      continue;
    }
    const outgoing = input.starters[starterIndex];
    if (!outgoing?.athleteId) {
      continue;
    }
    replaced.add(outgoing.athleteId);
    effectiveStarterIds[starterIndex] = benchPlayer.athleteId;
    substitutions.push({
      outAthleteId: outgoing.athleteId,
      inAthleteId: benchPlayer.athleteId,
      role: benchPlayer.role,
      order: substitutions.length + 1,
    });
  }

  let moduleValid = false;
  if (isApprovedModule(input.module)) {
    const expected = moduleCounts(input.module);
    const counts = emptyCounts();
    for (const athleteId of effectiveStarterIds) {
      const role = roleByAthlete.get(athleteId);
      if (role) {
        counts[role] += 1;
      }
    }
    moduleValid =
      counts.P === expected.goalkeepers &&
      counts.D === expected.defenders &&
      counts.C === expected.midfielders &&
      counts.A === expected.forwards;
  }

  return { substitutions, effectiveStarterIds, moduleValid };
}

export function lineupSignature(input: {
  module: string;
  starterIds: readonly string[];
  benchIds: readonly string[];
}): string {
  return [
    input.module,
    input.starterIds.filter(Boolean).join(","),
    input.benchIds.filter(Boolean).join(","),
  ].join("|");
}

export function isTacticalWindowActive(anyAthleteLocked: boolean): boolean {
  return Boolean(anyAthleteLocked);
}

export function remainingTacticalMoves(used: number, maximum = MAX_TACTICAL_MOVES): number {
  return Math.max(0, maximum - Math.max(0, used));
}

/**
 * One confirmed save in the progressive window consumes one of three moves.
 * Initial formation and identical re-saves do not consume. Automatic
 * substitutions are out of this engine and never consume a move.
 */
export function evaluateTacticalMove(input: {
  hasSavedLineup: boolean;
  anyAthleteLocked: boolean;
  movesUsed: number;
  proposedModule: string;
  proposedStarterIds: readonly string[];
  proposedBenchIds: readonly string[];
  previousModule?: string | null;
  previousStarterIds?: readonly string[];
  previousBenchIds?: readonly string[];
  maximum?: number;
}): TacticalMoveEvaluation {
  const maximum = input.maximum ?? MAX_TACTICAL_MOVES;
  const changed =
    input.hasSavedLineup &&
    lineupSignature({
      module: input.proposedModule,
      starterIds: input.proposedStarterIds,
      benchIds: input.proposedBenchIds,
    }) !==
      lineupSignature({
        module: input.previousModule ?? "",
        starterIds: input.previousStarterIds ?? [],
        benchIds: input.previousBenchIds ?? [],
      });
  const wouldConsume = Boolean(
    input.hasSavedLineup && isTacticalWindowActive(input.anyAthleteLocked) && changed,
  );
  const issues: LineupIssue[] = [];
  if (wouldConsume && input.movesUsed >= maximum) {
    issues.push(issue("tactical_moves_exhausted", TACTICAL_MOVES_EXHAUSTED_MESSAGE));
  }
  return {
    wouldConsume,
    remainingAfter: remainingTacticalMoves(input.movesUsed + (wouldConsume ? 1 : 0), maximum),
    issues,
  };
}

const COPIED_NOT_IN_ROSTER_MESSAGE =
  "Uno o più calciatori della formazione precedente non sono più in rosa e sono stati esclusi.";

const COPIED_UNAVAILABLE_MESSAGE =
  "Uno o più calciatori non sono disponibili: la loro partita è già iniziata.";

/**
 * Copy a previous-turn lineup onto the current roster and kickoff availability.
 * Locked athletes cannot become new starters; lock violations against the
 * current confirmed lineup block the copy (server remains decisive).
 */
export function copyPreviousLineup(input: {
  previousModule: string;
  previousStarterIds: readonly string[];
  previousBenchIds: readonly string[];
  rosterAthleteIds: readonly string[];
  lockedAthleteIds?: readonly string[];
  currentConfirmedSlots?: Readonly<Record<string, LineupSlotKind>>;
  currentConfirmedBench?: readonly string[];
  roleByAthleteId?: Readonly<Record<string, LineupRole | null>>;
}): CopyLineupResult {
  const rosterSet = new Set(input.rosterAthleteIds.filter(Boolean));
  const locked = new Set((input.lockedAthleteIds ?? []).filter(Boolean));
  const confirmed = input.currentConfirmedSlots ?? {};
  const dropped: string[] = [];
  const unavailable: string[] = [];
  const starters: string[] = [];

  for (const athleteId of input.previousStarterIds) {
    if (!athleteId) {
      starters.push("");
      continue;
    }
    if (!rosterSet.has(athleteId)) {
      dropped.push(athleteId);
      starters.push("");
      continue;
    }
    if (locked.has(athleteId) && confirmed[athleteId] !== "starter") {
      unavailable.push(athleteId);
      starters.push("");
      continue;
    }
    starters.push(athleteId);
  }
  while (starters.length < 11) {
    starters.push("");
  }
  const starterIds = starters.slice(0, 11);

  for (const athleteId of input.previousBenchIds) {
    if (athleteId && !rosterSet.has(athleteId) && !dropped.includes(athleteId)) {
      dropped.push(athleteId);
    }
  }

  const previousBenchKept = input.previousBenchIds.filter(
    (athleteId) => athleteId && rosterSet.has(athleteId) && !starterIds.includes(athleteId),
  );
  const displaced = unavailable.filter(
    (athleteId) => rosterSet.has(athleteId) && !starterIds.includes(athleteId),
  );
  const benchIds = orderedBenchFromRoster(input.rosterAthleteIds, starterIds, [
    ...previousBenchKept,
    ...displaced,
  ]);

  const lockIssues = [
    ...evaluateProgressiveLock({
      previousSlots: confirmed,
      proposedSlots: slotsFromLineupIds(starterIds, benchIds),
      lockedAthleteIds: [...locked],
    }),
    ...evaluateBenchOrderLock({
      previousBench: input.currentConfirmedBench ?? [],
      proposedBench: benchIds,
      lockedAthleteIds: [...locked],
    }),
  ];

  const issues: LineupIssue[] = [];
  if (dropped.length > 0) {
    issues.push(issue("copied_athlete_not_in_roster", COPIED_NOT_IN_ROSTER_MESSAGE));
  }
  if (unavailable.length > 0) {
    issues.push(issue("copied_athlete_unavailable", COPIED_UNAVAILABLE_MESSAGE));
  }
  issues.push(...lockIssues);

  const roleOf = (athleteId: string): LineupRole | null => input.roleByAthleteId?.[athleteId] ?? null;
  const confirmation = evaluateLineup({
    module: input.previousModule,
    starters: starterIds.map((athleteId) => ({ athleteId, role: athleteId ? roleOf(athleteId) : null })),
    bench: benchIds.map((athleteId) => ({ athleteId, role: athleteId ? roleOf(athleteId) : null })),
    rosterAthleteIds: input.rosterAthleteIds,
  });

  return {
    module: input.previousModule,
    starterIds,
    benchIds,
    droppedAthleteIds: dropped,
    unavailableAthleteIds: unavailable,
    issues: issues.filter(
      (item, index) => issues.findIndex((other) => other.code === item.code && other.message === item.message) === index,
    ),
    blocked: lockIssues.length > 0,
    canConfirm: confirmation.valid && lockIssues.length === 0,
  };
}
