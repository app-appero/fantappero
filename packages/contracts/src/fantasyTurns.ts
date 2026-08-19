/** European fantasy turn contracts and shared cutoff rules (EP06-01 / EP06-07). */

export type FantasyTurnStatus = "scheduled" | "open" | "locked" | "skipped";

export type FantasyTurnKind = "weekend" | "midweek";

export type FantasyRoundFixtureReason = "window" | "admin_include";

export type FantasyRoundHomologationStatus = "provisional" | "homologated";

export interface FantasyTurnFixture {
  id: string;
  fixtureId: string;
  includedReason: FantasyRoundFixtureReason;
  excludedAt: string | null;
  kickoffAt: string | null;
  observedKickoffAt: string | null;
  lockLatchedAt: string | null;
  statusShort: string;
  statusElapsed: number | null;
  homeGoals: number | null;
  awayGoals: number | null;
  homeClubName: string;
  awayClubName: string;
  competitionName: string | null;
  providerId: number;
}

export interface FantasyTurnSummary {
  id: string;
  leagueId: string;
  number: number;
  kind: FantasyTurnKind;
  windowStartAt: string;
  windowEndAt: string;
  opensAt: string | null;
  closesAt: string | null;
  cutoffAt: string | null;
  status: FantasyTurnStatus;
  effectiveStatus: FantasyTurnStatus;
  skipReason: string | null;
  fixtureCount: number;
  generatedAt: string;
  modificationAllowed: boolean;
}

export interface FantasyTurnDetail extends FantasyTurnSummary {
  homologationStatus: FantasyRoundHomologationStatus;
  fixtures: FantasyTurnFixture[];
}

export interface FantasyTurnPreview {
  kind: FantasyTurnKind;
  windowStartAt: string;
  windowEndAt: string;
  timezone: string;
  eligibleCount: number;
  minRequired: number;
  thresholdOk: boolean;
  skipReason: string | null;
  cutoffAt: string | null;
  fixtures: FantasyTurnFixture[];
}

export interface GenerateFantasyTurnRequest {
  kind: FantasyTurnKind;
  /** ISO date (YYYY-MM-DD) used to resolve the weekend/midweek window. */
  anchorDate: string;
}

export interface ExcludeFantasyTurnFixtureRequest {
  fixtureId: string;
}

export type FantasyFixtureMatchStatus = "scheduled" | "live" | "finished" | "postponed";

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

const CUTOFF_EXCLUDED_STATUSES = new Set(["CANC", "ABD", "AWD", "WO"]);
const POSTPONED_FIXTURE_STATUSES = new Set(["PST"]);
const INACTIVE_FIXTURE_STATUSES = new Set(["PST", "CANC", "ABD", "AWD", "WO"]);

function ensureUtcMs(value: string | Date): number {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.getTime();
}

function optionalUtcMs(value: string | Date | null | undefined): number | null {
  if (value == null) {
    return null;
  }
  const ms = ensureUtcMs(value);
  return Number.isNaN(ms) ? null : ms;
}

/** Earliest kickoff among included fixtures; simultaneous kickoffs share the same cutoff. */
export function computeCutoff(kickoffs: ReadonlyArray<string | Date>): string | null {
  if (kickoffs.length === 0) {
    return null;
  }
  let minMs = Number.POSITIVE_INFINITY;
  for (const kickoff of kickoffs) {
    const ms = ensureUtcMs(kickoff);
    if (Number.isNaN(ms)) {
      continue;
    }
    if (ms < minMs) {
      minMs = ms;
    }
  }
  if (!Number.isFinite(minMs)) {
    return null;
  }
  return new Date(minMs).toISOString();
}

export function deriveEffectiveStatus(
  stored: FantasyTurnStatus,
  now: string | Date,
  cutoffAt: string | Date | null | undefined,
): FantasyTurnStatus {
  if (stored === "skipped" || stored === "locked" || stored === "scheduled") {
    return stored;
  }
  if (stored === "open" && cutoffAt) {
    if (ensureUtcMs(now) >= ensureUtcMs(cutoffAt)) {
      return "locked";
    }
  }
  return stored;
}

export function isModificationAllowed(
  stored: FantasyTurnStatus,
  now: string | Date,
  cutoffAt: string | Date | null | undefined,
): boolean {
  return deriveEffectiveStatus(stored, now, cutoffAt) === "scheduled";
}

export function kickoffCountsForCutoff(
  kickoffAt: string | Date | null | undefined,
  statusShort: string | null | undefined,
  now: string | Date,
): boolean {
  const kickoffMs = optionalUtcMs(kickoffAt);
  if (kickoffMs == null) {
    return false;
  }
  const status = (statusShort ?? "").trim().toUpperCase();
  if (CUTOFF_EXCLUDED_STATUSES.has(status)) {
    return false;
  }
  if (POSTPONED_FIXTURE_STATUSES.has(status)) {
    return kickoffMs > ensureUtcMs(now);
  }
  return true;
}

/**
 * Recalculate cutoff from current live kickoffs without moving it later after
 * the previously published instant has elapsed (no retroactive unlock).
 */
export function applyCutoffRecalculation(
  previousCutoff: string | Date | null | undefined,
  candidateCutoff: string | Date | null | undefined,
  now: string | Date,
): string | null {
  const previousMs = optionalUtcMs(previousCutoff);
  const candidateMs = optionalUtcMs(candidateCutoff);
  const nowMs = ensureUtcMs(now);
  if (previousMs != null && nowMs >= previousMs) {
    if (candidateMs == null || candidateMs > previousMs) {
      return new Date(previousMs).toISOString();
    }
    return new Date(candidateMs).toISOString();
  }
  return candidateMs == null ? null : new Date(candidateMs).toISOString();
}

export interface KickoffLockState {
  observedKickoffAt: string | null;
  lockLatchedAt: string | null;
  justLatched: boolean;
}

/** Latch lock when a published kickoff elapses; later PST/time shifts cannot unlock. */
export function reconcileFixtureKickoffLock(input: {
  now: string | Date;
  currentKickoffAt: string | Date | null | undefined;
  statusShort?: string | null;
  observedKickoffAt: string | Date | null | undefined;
  lockLatchedAt: string | Date | null | undefined;
}): KickoffLockState {
  const nowMs = ensureUtcMs(input.now);
  const observedMs = optionalUtcMs(input.observedKickoffAt);
  const currentMs = optionalUtcMs(input.currentKickoffAt);
  let latchedMs = optionalUtcMs(input.lockLatchedAt);
  const status = (input.statusShort ?? "").trim().toUpperCase();
  let justLatched = false;

  if (latchedMs == null) {
    const publishedElapsed = observedMs != null && nowMs >= observedMs;
    const currentElapsed =
      currentMs != null && !INACTIVE_FIXTURE_STATUSES.has(status) && nowMs >= currentMs;
    const started = STARTED_FIXTURE_STATUSES.has(status);
    if (publishedElapsed || currentElapsed || started) {
      latchedMs = observedMs ?? currentMs ?? nowMs;
      justLatched = true;
    }
  }

  const newObservedMs = currentMs ?? observedMs;
  return {
    observedKickoffAt: newObservedMs == null ? null : new Date(newObservedMs).toISOString(),
    lockLatchedAt: latchedMs == null ? null : new Date(latchedMs).toISOString(),
    justLatched,
  };
}

export function mapFixtureMatchStatus(statusShort: string | null | undefined): FantasyFixtureMatchStatus {
  const status = (statusShort ?? "").trim().toUpperCase();
  if (POSTPONED_FIXTURE_STATUSES.has(status) || CUTOFF_EXCLUDED_STATUSES.has(status)) {
    return "postponed";
  }
  if (status === "FT" || status === "AET" || status === "PEN") {
    return "finished";
  }
  if (STARTED_FIXTURE_STATUSES.has(status)) {
    return "live";
  }
  return "scheduled";
}
