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
  homeClubLogoUrl: string | null;
  awayClubLogoUrl: string | null;
  competitionName: string | null;
  providerId: number;
  /** Ultimo aggiornamento del dato normalizzato (EP13-P04). */
  updatedAt: string | null;
  feedState: ProviderFeedState;
  feedStateLabel: string;
}

/**
 * Quanto ci si può fidare di ciò che si vede (EP13-P04). Derivato dall'ultimo
 * aggiornamento normalizzato: è un'inferenza, non un fatto registrato.
 */
export type ProviderFeedState =
  | "fresh"
  | "delayed"
  | "stale"
  | "degraded"
  | "unavailable";

export interface FixtureTimelineEvent {
  id: string;
  minuteElapsed: number | null;
  minuteExtra: number | null;
  /** Già formattato: `45+2'`, oppure `—` se il minuto non è noto. */
  minuteLabel: string;
  eventType: string;
  eventDetail: string | null;
  scoringKind: string | null;
  clubId: string | null;
  clubName: string | null;
  /** Id interno del calciatore: usare per collegare l'evento alla formazione, mai il nome. */
  athleteId: string | null;
  athleteName: string | null;
  relatedAthleteId: string | null;
  relatedAthleteName: string | null;
  comments: string | null;
}

export interface FixtureLineupPlayer {
  athleteId: string | null;
  name: string;
  shirtNumber: number | null;
  position: string | null;
  grid: string | null;
  photoUrl: string | null;
}

export interface FixtureLineup {
  clubName: string;
  clubLogoUrl: string | null;
  formation: string | null;
  coachName: string | null;
  starters: FixtureLineupPlayer[];
  bench: FixtureLineupPlayer[];
}

/** Dettaglio partita live: risultato, formazioni ufficiali e cronologia. */
export interface FixtureLiveDetail {
  fixtureId: string;
  turnId: string;
  leagueId: string;
  providerId: number;
  competitionName: string | null;
  homeClubId: string;
  awayClubId: string;
  homeClubName: string;
  awayClubName: string;
  homeClubLogoUrl: string | null;
  awayClubLogoUrl: string | null;
  homeGoals: number | null;
  awayGoals: number | null;
  statusShort: string;
  statusElapsed: number | null;
  venueName: string | null;
  venueCity: string | null;
  referee: string | null;
  kickoffAt: string | null;
  updatedAt: string | null;
  feedState: ProviderFeedState;
  feedStateLabel: string;
  /** `null` quando la formazione ufficiale non è ancora pubblicata. */
  homeLineup: FixtureLineup | null;
  awayLineup: FixtureLineup | null;
  events: FixtureTimelineEvent[];
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
  /** Stato aggregato dalle fixture reali (§23) — distinto dal ciclo di vita fantasy sopra. */
  matchStatus: FantasyTurnAggregateStatus;
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

export interface EnsureFantasyTurnsResponse {
  leagueId: string;
  created: number;
  opened: number;
  upgraded: number;
  duplicates: number;
  waiting: number;
  horizonDays: number;
}

/** Esito del comando unico "Aggiorna calendario" (backfill stagionale). */
export interface FantasyCalendarRefreshResult {
  leagueId: string;
  fixturesCreated: number;
  fixturesUpdated: number;
  fixturesUnchanged: number;
  fixturesNeedingDate: number;
  roundsCreated: number;
  roundsUpdated: number;
  roundsRealigned: number;
  /** Turni "fantasma" (senza nessuna partita reale) rimossi in questo giro. */
  roundsRemoved: number;
  message: string;
}

/** Esito di "Calcola giornata corrente" per singola lega (EP-turni-calcolo). */
export interface RoundCalculationResult {
  roundId: string;
  roundNumber: number;
  fixturesScored: number;
  fallbackResolvedFromDraft: number;
  fallbackResolvedFromPreviousRound: number;
  fallbackResolvedAsZero: number;
  resultFinal: boolean;
  homologated: boolean;
}

export interface FantasyCalendarRefreshJob {
  jobId: string;
  status: string;
  message: string;
}

export interface FantasyCalendarRefreshProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: FantasyCalendarRefreshResult | null;
}

/** Fixture nota (competizione/squadre/round) ma senza data/ora dal provider. */
export interface PendingFixtureSummary {
  fixtureId: string;
  competitionName: string | null;
  roundLabel: string | null;
  homeClubName: string;
  awayClubName: string;
  statusShort: string;
}

export interface GenerateFantasyTurnRequest {
  kind: FantasyTurnKind;
  /** ISO date (YYYY-MM-DD) used to resolve the weekend/midweek window. */
  anchorDate: string;
}

export interface ExcludeFantasyTurnFixtureRequest {
  fixtureId: string;
}

export type FantasyFixtureMatchStatus =
  | "scheduled"
  | "live"
  | "finished"
  | "postponed"
  | "needs_update";

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

export function mapFixtureMatchStatus(
  statusShort: string | null | undefined,
  kickoffAt?: string | Date | null,
): FantasyFixtureMatchStatus {
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
  // Nota fin qui dal provider (competizione/squadre/round) ma senza data/ora
  // definitiva: non può ancora appartenere a nessuna finestra di turno.
  if (kickoffAt === null || (kickoffAt === undefined && status === "TBD")) {
    return "needs_update";
  }
  return "scheduled";
}

/** Aggregato di stato per un turno con più partite (§23 numerazione turni). */
export type FantasyTurnAggregateStatus = "completed" | "live" | "scheduled" | "needs_update";

export function aggregateTurnStatus(
  fixtures: ReadonlyArray<{ statusShort: string | null | undefined; kickoffAt: string | null }>,
): FantasyTurnAggregateStatus {
  if (fixtures.length === 0) {
    return "needs_update";
  }
  const statuses = fixtures.map((fixture) =>
    mapFixtureMatchStatus(fixture.statusShort, fixture.kickoffAt),
  );
  if (statuses.some((status) => status === "live")) {
    return "live";
  }
  if (statuses.some((status) => status === "needs_update")) {
    return "needs_update";
  }
  if (statuses.every((status) => status === "finished" || status === "postponed")) {
    return "completed";
  }
  return "scheduled";
}

/**
 * Stato mostrato all'utente per un turno. Deliberatamente ridotto a quattro
 * voci: gli stati interni (`scheduled`/`open`/`locked`/`skipped`,
 * `provisional`/`homologated`) servono al backend per il ciclo di vita delle
 * formazioni, ma esporli produceva un elenco incomprensibile in cui turni
 * futuri identici fra loro apparivano "Programmato" o "Aperto" a seconda del
 * momento in cui erano stati generati.
 */
export type TurnDisplayState = "completed" | "live" | "next" | "upcoming";

export const TURN_DISPLAY_LABEL: Record<TurnDisplayState, string> = {
  completed: "Completato",
  live: "In corso",
  next: "Prossimo",
  upcoming: "Da disputare",
};

/**
 * Colloca ogni turno rispetto ad *adesso*, non rispetto al suo stato interno:
 * concluso, in corso, il primo ancora da giocare, tutti gli altri. `turns`
 * deve essere ordinato per numero crescente.
 */
export function resolveTurnDisplayStates<
  T extends { matchStatus: FantasyTurnAggregateStatus },
>(turns: readonly T[]): TurnDisplayState[] {
  let nextAssigned = false;
  return turns.map((turn) => {
    if (turn.matchStatus === "live") {
      // Un turno in corso è già "adesso": non c'è un prossimo prima di lui.
      nextAssigned = true;
      return "live";
    }
    if (turn.matchStatus === "completed") {
      return "completed";
    }
    if (!nextAssigned) {
      nextAssigned = true;
      return "next";
    }
    return "upcoming";
  });
}

/**
 * Turno di default da mostrare all'apertura di Turni Europei: il primo non
 * ancora concluso (i turni arrivano già ordinati per numero/cronologia); se
 * sono tutti conclusi, l'ultimo. Il backfill copre l'intera stagione, quindi
 * "il primo della lista" sarebbe sempre l'inizio stagione — questo riporta
 * la vista di default a "adesso", come già fa `resolveDefaultH2HRound`.
 */
export function resolveDefaultEuropeanTurn<
  T extends { matchStatus: FantasyTurnAggregateStatus },
>(turns: readonly T[]): T | null {
  for (const turn of turns) {
    if (turn.matchStatus !== "completed") {
      return turn;
    }
  }
  return turns[turns.length - 1] ?? null;
}
