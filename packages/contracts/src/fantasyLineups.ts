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
  photoUrl?: string | null;
  /** Squadra reale del calciatore (per la maglia dell'avatar). */
  realTeamName?: string | null;
  /** Voto fantacalcistico del turno corrente, se già disponibile (EP-formazione-voti). */
  fantasyScore?: number | null;
  /** Voto statistico prima dei bonus/malus. */
  baseScore?: number | null;
  bonusTotal?: number;
  malusTotal?: number;
  bonusMalus?: Array<{
    id: string;
    count: number;
    unit_value: number;
    contribution: number;
  }>;
  fixtureStatusLabel?: string | null;
  /** Titolare o panchinaro nella formazione probabile, oppure indisponibile. */
  probableHint?: "starter" | "bench" | "unavailable" | null;
  probableNote?: string | null;
  /** Solo se indisponibile: espulso/squalificato, infortunato o altro motivo. */
  probableAbsence?: "suspended" | "injured" | "other" | null;
  /**
   * 1.5: assente «in dubbio» per il fornitore (Doubtful, Questionable, Day to day…). Resta
   * selezionabile; alone arancione «In dubbio». `probableHint` resta "unavailable" per l'app 1.4.
   * Assente da un backend più vecchio.
   */
  probableDoubt?: boolean;
  /** Non può essere aggiunto tra i titolari. Chi è già schierato resta finché non lo si toglie. */
  selectionBlocked?: boolean;
  /** In rosa ma oltre la quota di ruolo dopo uno scambio: non schierabile finché non si libera uno slot. */
  exceedsRoleQuota?: boolean;
}

/**
 * Perché una formazione è stata sintetizzata dal motore di calcolo turno
 * invece di essere inviata dal fantallenatore (EP-turni-calcolo). `null` per
 * una submission normale, umana o IA (distinto da `systemGeneratedAi`, che
 * riguarda la gestione IA di una squadra, non un fallback per assenza).
 */
export type LineupAutoResolutionSource = "draft" | "previous_round" | "zero_fallback" | null;

export interface SavedLineup {
  id: string;
  module: FantasyModule;
  revision: number;
  submittedAt: string;
  /** Formazione generata dall'automazione IA (EP13-P05). */
  systemGeneratedAi: boolean;
  aiAlgorithmVersion: string | null;
  aiDecidedAt: string | null;
  autoResolutionSource?: LineupAutoResolutionSource;
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
  /** Panchina attiva: primi N posti con la composizione `benchRoleQuota` (default 10 · 1P 3D 3C 3A). */
  benchActiveSize?: number;
  benchRoleQuota?: Record<LineupRole, number>;
  /** Squadra a cui appartiene questa formazione. Assente solo nelle risposte vecchie. */
  fantasyTeamId?: string;
  teamName?: string;
  roundId: string;
  roundNumber: number;
  kind: string;
  cutoffAt: string | null;
  status: FantasyTurnStatus;
  effectiveStatus: FantasyTurnStatus;
  modificationAllowed: boolean;
  lineupLockMarginMinutes: number;
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
  /** True se in lega c'è almeno un fantallenatore con utenza IA. */
  leagueHasAiManager?: boolean;
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

export type LineupLockCountdownState =
  | "counting_down"
  | "no_pending_lock"
  | "turn_not_open"
  | "no_roster"
  | "no_active_turn";

/** Mirror of `LineupLockCountdownResponse` (backend `fantasy_lineups/schemas.py`). */
export interface LineupLockCountdown {
  leagueId: string;
  roundId: string | null;
  roundNumber: number | null;
  roundStatus: string | null;
  state: LineupLockCountdownState;
  nextLockAt: string | null;
  serverNow: string;
}

/** Testo del conto alla rovescia quando non c'è nessun blocco da contare. */
export const LOCK_COUNTDOWN_IDLE_LABEL: Record<LineupLockCountdownState, string> = {
  no_active_turn: "Nessun turno attivo",
  turn_not_open: "Turno non ancora aperto",
  no_roster: "Rosa non ancora assegnata",
  no_pending_lock: "Formazione confermata",
  counting_down: "",
};

/**
 * Come `LOCK_COUNTDOWN_IDLE_LABEL`, ma un turno di riferimento saltato (sotto la soglia di
 * copertura) si legge «Turno saltato», non «Turno non ancora aperto» (Rosario, 21/11).
 */
export function lockCountdownIdleLabel(
  state: LineupLockCountdownState,
  roundStatus?: string | null,
): string {
  if (state === "turn_not_open" && roundStatus === "skipped") {
    return "Turno saltato";
  }
  return LOCK_COUNTDOWN_IDLE_LABEL[state] ?? "";
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

/** Panchina attiva: i primi 10 posti della panchina (poi tribuna libera). */
export const BENCH_ACTIVE_SIZE = 10;
/** Composizione richiesta nella panchina attiva: 1 portiere, 3 difensori, 3 centrocampisti, 3 attaccanti. */
export const BENCH_ACTIVE_ROLE_QUOTA: Readonly<Record<LineupRole, number>> = { P: 1, D: 3, C: 3, A: 3 };

const BENCH_ROLE_LABEL: Record<LineupRole, [string, string]> = {
  P: ["portiere", "portieri"],
  D: ["difensore", "difensori"],
  C: ["centrocampista", "centrocampisti"],
  A: ["attaccante", "attaccanti"],
};
/** Plurale con l'articolo: «i portieri», «gli attaccanti». */
const BENCH_ROLE_PLURAL_ARTICLE: Record<LineupRole, string> = {
  P: "i portieri",
  D: "i difensori",
  C: "i centrocampisti",
  A: "gli attaccanti",
};

/**
 * Ruoli che mancano nella panchina attiva. Il vincolo per ruolo è `min(quota, disponibili in
 * panchina)`: se la rosa non ha abbastanza giocatori di un ruolo non lo si può pretendere.
 * Chi è in `unfieldableAthleteIds` (di sicuro senza voto nel turno, `selectionBlocked`) non conta
 * tra i disponibili, come sul server (Rosario, 20/11); nei primi 10 conta comunque.
 */
export function benchActiveShortfall(
  bench: readonly LineupPlayerInput[],
  unfieldableAthleteIds: readonly string[] = [],
): Partial<Record<LineupRole, number>> {
  const unfieldable = new Set(unfieldableAthleteIds.filter(Boolean));
  const filled = bench.filter((player) => player.athleteId);
  const available = countRoles(filled.filter((player) => !unfieldable.has(player.athleteId)));
  const active = countRoles(filled.slice(0, BENCH_ACTIVE_SIZE));
  const missing: Partial<Record<LineupRole, number>> = {};
  for (const role of ["P", "D", "C", "A"] as const) {
    const required = Math.min(BENCH_ACTIVE_ROLE_QUOTA[role], available[role]);
    if (active[role] < required) {
      missing[role] = required - active[role];
    }
  }
  return missing;
}

/**
 * Riordina la panchina perché i primi 10 posti rispettino 1P·3D·3C·3A (o quanto disponibile) e,
 * dentro panchina e tribuna, dal portiere all'attaccante; mantiene l'ordine relativo nello stesso ruolo: i primi per ciascun ruolo entrano nella
 * panchina attiva, gli altri seguono nell'ordine originale.
 */
export function orderBenchForActiveRoles<T extends LineupPlayerInput>(bench: readonly T[]): T[] {
  const filled = bench.filter((player) => player.athleteId);
  const empty = bench.filter((player) => !player.athleteId);
  const taken = new Set<T>();
  const active: T[] = [];
  for (const role of ["P", "D", "C", "A"] as const) {
    let needed = BENCH_ACTIVE_ROLE_QUOTA[role];
    for (const player of filled) {
      if (needed === 0) {
        break;
      }
      if (player.role === role) {
        taken.add(player);
        active.push(player);
        needed -= 1;
      }
    }
  }
  // Posti liberi della panchina attiva (ruolo mancante in rosa): i successivi nell'ordine originale.
  const rest = filled.filter((player) => !taken.has(player));
  const fill = rest.slice(0, Math.max(0, BENCH_ACTIVE_SIZE - active.length));
  // Ordine interno della panchina attiva = ordine originale della lista.
  const activeSet = new Set<T>([...active, ...fill]);
  // Ogni blocco in ordine di ruolo (P, D, C, A): i cambi sono solo a parità di ruolo, quindi
  // conta solo l'ordine relativo dentro lo stesso ruolo, che il sort stabile conserva.
  const roleRank = (player: T) => ["P", "D", "C", "A"].indexOf(player.role ?? "");
  const byRole = (list: T[]) =>
    list
      .map((player, index) => ({ player, index }))
      .sort((x, y) => roleRank(x.player) - roleRank(y.player) || x.index - y.index)
      .map((entry) => entry.player);
  const activeOrdered = byRole(filled.filter((player) => activeSet.has(player)));
  const tribuna = byRole(filled.filter((player) => !activeSet.has(player)));
  return [...activeOrdered, ...tribuna, ...empty];
}

/** «1 attaccante», «2 difensori e 1 attaccante»: i ruoli che mancano nei primi 10. */
function benchShortfallText(missing: Partial<Record<LineupRole, number>>): string {
  return (["P", "D", "C", "A"] as const)
    .filter((role) => missing[role])
    .map((role) => `${missing[role]} ${BENCH_ROLE_LABEL[role][(missing[role] ?? 0) === 1 ? 0 : 1]}`)
    .join(", ");
}

function benchQuotaMessage(missing: Partial<Record<LineupRole, number>>): string {
  return `Nei primi ${BENCH_ACTIVE_SIZE} della panchina servono 1 portiere, 3 difensori, 3 centrocampisti e 3 attaccanti (mancano: ${benchShortfallText(missing)}).`;
}

/** Perché un ruolo che manca nei primi 10 non si può far salire dalla tribuna. */
export type BenchRepairBlock = "locked_in_tribuna" | "locked_in_bench" | "locked_between";

export interface BenchActiveRoleRepair<T extends LineupPlayerInput> {
  /** La panchina sistemata (o com'era, se non c'era niente da fare). */
  bench: T[];
  /** Ogni scambio fatto: chi è salito dalla tribuna e chi è sceso al suo posto. */
  moves: Array<{ promoted: T; demoted: T }>;
  /** Ruoli ancora scoperti nei primi 10: vuoto se la panchina ora è in regola. */
  missing: Partial<Record<LineupRole, number>>;
  /** Con `missing` non vuoto: quale ruolo manca e perché non si può sistemare. */
  message: string | null;
}

const isLineupRole = (role: unknown): role is LineupRole =>
  role === "P" || role === "D" || role === "C" || role === "A";

/**
 * Riporta i primi 10 della panchina alla quota per ruolo (1P·3D·3C·3A, o quanti ce ne sono) con il
 * minimo di spostamenti: per ogni ruolo che manca l'ultimo dei primi 10 che è in più per il suo
 * ruolo scende e diventa il primo della tribuna, chi era dopo di lui sale di un posto e il primo
 * della tribuna con il ruolo che manca diventa il 10°. Nessun altro si sposta e l'ordine dentro
 * ogni ruolo resta quello scelto (conta per i cambi automatici, che vanno solo a parità di ruolo).
 * Stessa regola del server (`restore_bench_active_roles`), usata dopo la pulizia di chi esce
 * dalla rosa: lì, di solito, scende proprio chi era appena salito dalla tribuna.
 *
 * Chi ha la partita già iniziata (`lockedAthleteIds`) non si sposta e non si scavalca: se l'unico
 * scambio possibile lo richiede, la panchina resta com'è e `message` dice quale ruolo manca e perché.
 */
export function restoreBenchActiveRoles<T extends LineupPlayerInput>(
  bench: readonly T[],
  options: { lockedAthleteIds?: readonly string[]; unfieldableAthleteIds?: readonly string[] } = {},
): BenchActiveRoleRepair<T> {
  const locked = new Set((options.lockedAthleteIds ?? []).filter(Boolean));
  const unfieldableIds = (options.unfieldableAthleteIds ?? []).filter(Boolean);
  const unfieldable = new Set(unfieldableIds);
  const empty = bench.filter((player) => !player.athleteId);
  let list = bench.filter((player) => player.athleteId);
  const moves: Array<{ promoted: T; demoted: T }> = [];
  const blocked: Partial<Record<LineupRole, BenchRepairBlock>> = {};
  for (;;) {
    const missing = benchActiveShortfall(list, unfieldableIds);
    const short = (["P", "D", "C", "A"] as const).filter((role) => missing[role]);
    if (short.length === 0) {
      break;
    }
    const available = countRoles(list.filter((player) => !unfieldable.has(player.athleteId)));
    const active = countRoles(list.slice(0, BENCH_ACTIVE_SIZE));
    const surplus = (player: T) =>
      !isLineupRole(player.role) ||
      active[player.role] > Math.min(BENCH_ACTIVE_ROLE_QUOTA[player.role], available[player.role]);
    let applied = false;
    for (const role of short) {
      const promotable: number[] = [];
      list.forEach((player, index) => {
        if (
          index >= BENCH_ACTIVE_SIZE &&
          player.role === role &&
          !locked.has(player.athleteId) &&
          !unfieldable.has(player.athleteId)
        ) {
          promotable.push(index);
        }
      });
      const demotable: number[] = [];
      for (let index = Math.min(BENCH_ACTIVE_SIZE, list.length) - 1; index >= 0; index -= 1) {
        const player = list[index] as T;
        if (!locked.has(player.athleteId) && surplus(player)) {
          demotable.push(index);
        }
      }
      if (promotable.length === 0) {
        blocked[role] = "locked_in_tribuna";
        continue;
      }
      if (demotable.length === 0) {
        blocked[role] = "locked_in_bench";
        continue;
      }
      let pair: [number, number] | null = null;
      for (const down of demotable) {
        const up = promotable.find(
          (candidate) => !list.slice(down + 1, candidate).some((player) => locked.has(player.athleteId)),
        );
        if (up !== undefined) {
          pair = [down, up];
          break;
        }
      }
      if (pair === null) {
        blocked[role] = "locked_between";
        continue;
      }
      const [down, up] = pair;
      const promoted = list[up] as T;
      const demoted = list[down] as T;
      const nextActive = list.filter((_, index) => index < BENCH_ACTIVE_SIZE && index !== down);
      nextActive.push(promoted);
      const nextTribuna = list.filter((_, index) => index >= BENCH_ACTIVE_SIZE && index !== up);
      list = [...nextActive, demoted, ...nextTribuna];
      moves.push({ promoted, demoted });
      delete blocked[role];
      applied = true;
      break;
    }
    if (!applied) {
      break;
    }
  }
  const missing = benchActiveShortfall(list, unfieldableIds);
  const short = (["P", "D", "C", "A"] as const).filter((role) => missing[role]);
  let message: string | null = null;
  if (short.length > 0) {
    const reasons = short.map((role) => {
      const plural = BENCH_ROLE_LABEL[role][1];
      switch (blocked[role]) {
        case "locked_in_bench":
          return `nei primi ${BENCH_ACTIVE_SIZE} chi potrebbe lasciare il posto a un ${BENCH_ROLE_LABEL[role][0]} ha la partita già iniziata`;
        case "locked_between":
          return `tra la panchina e ${BENCH_ROLE_PLURAL_ARTICLE[role]} in tribuna c'è chi ha la partita già iniziata e non si può scavalcare`;
        default:
          return `in tribuna non ci sono ${plural} schierabili: hanno la partita già iniziata`;
      }
    });
    message = `${benchQuotaMessage(missing)} Non si può sistemare da sola: ${reasons.join("; ")}.`;
  }
  return { bench: [...list, ...empty], moves, missing, message };
}

/**
 * Con la panchina fuori quota, con chi si può scambiare il calciatore al posto `index` per
 * rimetterla in regola: per uno dei primi 10 che è in più per il suo ruolo, chi in tribuna ha un
 * ruolo che manca; per uno in tribuna con un ruolo che manca, chi nei primi 10 è in più. Il «Cambia»
 * della panchina li propone insieme a quelli dello stesso ruolo.
 */
export function benchQuotaSwapIds(
  bench: readonly LineupPlayerInput[],
  index: number,
  unfieldableAthleteIds: readonly string[] = [],
): string[] {
  const current = bench[index];
  if (!current?.athleteId) {
    return [];
  }
  const unfieldable = new Set(unfieldableAthleteIds.filter(Boolean));
  const missing = benchActiveShortfall(bench, unfieldableAthleteIds);
  if (Object.keys(missing).length === 0) {
    return [];
  }
  const available = countRoles(bench.filter((player) => player.athleteId && !unfieldable.has(player.athleteId)));
  const active = countRoles(bench.slice(0, BENCH_ACTIVE_SIZE).filter((player) => player.athleteId));
  const surplus = (player: LineupPlayerInput) =>
    !isLineupRole(player.role) ||
    active[player.role] > Math.min(BENCH_ACTIVE_ROLE_QUOTA[player.role], available[player.role]);
  if (index < BENCH_ACTIVE_SIZE) {
    if (!surplus(current)) {
      return [];
    }
    return bench
      .slice(BENCH_ACTIVE_SIZE)
      .filter(
        (player) =>
          player.athleteId && !unfieldable.has(player.athleteId) && isLineupRole(player.role) && missing[player.role],
      )
      .map((player) => player.athleteId);
  }
  if (!isLineupRole(current.role) || !missing[current.role] || unfieldable.has(current.athleteId)) {
    return [];
  }
  return bench
    .slice(0, BENCH_ACTIVE_SIZE)
    .filter((player) => player.athleteId && surplus(player))
    .map((player) => player.athleteId);
}

/**
 * La panchina della formazione mostrata e salvata (panchina e tribuna).
 *
 * Chi è arrivato in rosa dopo l'ultimo salvataggio e oggi non può essere schierato (`isBlocked`:
 * nessun voto, squalificato) va in coda alla tribuna. Ma se il fantallenatore, o
 * «Sistema la panchina», l'ha già messo in un posto (`placedBench`, la panchina dell'editor), quel
 * posto si rispetta: prima tornava sempre in coda, e con lui l'unico attaccante che poteva
 * rimettere in regola i primi 10 (Rosario, 20/11: il tasto non cambiava niente).
 */
export function formationLineupBench(input: {
  orderedBench: readonly string[];
  savedBench: readonly string[];
  placedBench: readonly string[];
  isBlocked: (athleteId: string) => boolean;
}): string[] {
  const kept = new Set([...input.savedBench, ...input.placedBench]);
  const deferred = (athleteId: string) => input.isBlocked(athleteId) && !kept.has(athleteId);
  return [
    ...input.orderedBench.filter((athleteId) => !deferred(athleteId)),
    ...input.orderedBench.filter((athleteId) => deferred(athleteId)),
  ];
}

/** Esito di «Svuota formazione» (`clearLineupKeepingLocked`). */
export interface ClearedLineup {
  /** Gli slot del modulo: restano solo i titolari bloccati, nel loro slot; gli altri sono vuoti. */
  starterIds: string[];
  /** Panchina e tribuna ricomposte (tutta la rosa che non è titolare, come sempre). */
  benchIds: string[];
  /**
   * Chi non è bloccato ma resta al suo posto in panchina perché davanti a un bloccato: spostarlo
   * cambierebbe il posto del bloccato e il salvataggio verrebbe rifiutato.
   */
  heldBenchIds: string[];
}

/**
 * «Svuota formazione» (Rosario, 20/11): toglie i titolari e la scelta della panchina per
 * ricominciare da capo. Solo l'editor: niente salvataggi, niente mosse.
 *
 * - Titolari: restano solo i bloccati (partita già iniziata), nello stesso slot.
 * - Panchina: non può restare vuota (tutta la rosa che non gioca è in panchina o in tribuna, e il
 *   server la vuole completa), quindi torna all'ordine della rosa (`rosterAthleteIds`), con in coda
 *   chi oggi non si può schierare (`unavailableAthleteIds`) e i primi 10 riportati alla quota
 *   1P·3D·3C·3A da `restoreBenchActiveRoles`. I titolari tolti finiscono lì dentro.
 * - Bloccati in panchina: restano al loro posto, e con loro chi li precede. Davanti a un bloccato
 *   non si può né entrare né uscire (`evaluateBenchOrderLock`): ricomporre quel tratto farebbe
 *   rifiutare il salvataggio. Si riordina solo quello che viene dopo l'ultimo bloccato.
 *
 * Con tutti bloccati non cambia niente.
 */
export function clearLineupKeepingLocked(input: {
  /** Gli slot del modulo ("" = vuoto). */
  starterIds: readonly string[];
  /** Panchina e tribuna attuali, in ordine (senza chi è in esubero di ruolo). */
  benchIds: readonly string[];
  /** La rosa schierabile nell'ordine della rosa (senza chi è in esubero di ruolo). */
  rosterAthleteIds: readonly string[];
  lockedAthleteIds: readonly string[];
  /** Ruolo per la quota dei primi 10. */
  roleByAthleteId: Readonly<Record<string, string | null | undefined>>;
  /** Chi oggi non si può schierare (indisponibile, squalificato): in coda, dopo gli altri. */
  unavailableAthleteIds?: readonly string[];
  /** Di sicuro senza voto (`selectionBlocked`): non alza la quota dei primi 10, come in `evaluateLineup`. */
  unfieldableAthleteIds?: readonly string[];
}): ClearedLineup {
  const locked = new Set(input.lockedAthleteIds.filter(Boolean));
  const roster = [...new Set(input.rosterAthleteIds.filter(Boolean))];
  const inRoster = new Set(roster);
  const starterIds = input.starterIds.map((athleteId) => (athleteId && locked.has(athleteId) ? athleteId : ""));
  const keptStarters = new Set(starterIds.filter(Boolean));
  const bench = [...new Set(input.benchIds)].filter(
    (athleteId) => athleteId && inRoster.has(athleteId) && !keptStarters.has(athleteId),
  );
  // Fino all'ultimo bloccato la panchina resta com'è.
  let lastLocked = -1;
  bench.forEach((athleteId, index) => {
    if (locked.has(athleteId)) {
      lastLocked = index;
    }
  });
  const held = bench.slice(0, lastLocked + 1);
  const heldSet = new Set(held);
  const unavailable = new Set((input.unavailableAthleteIds ?? []).filter(Boolean));
  const rest = roster.filter((athleteId) => !keptStarters.has(athleteId) && !heldSet.has(athleteId));
  const ordered = [
    ...held,
    ...rest.filter((athleteId) => !unavailable.has(athleteId)),
    ...rest.filter((athleteId) => unavailable.has(athleteId)),
  ];
  const roleOf = (athleteId: string): LineupRole | null => {
    const role = input.roleByAthleteId[athleteId];
    return isLineupRole(role) ? role : null;
  };
  // Chi resta al suo posto conta come bloccato: la quota si sistema solo dopo l'ultimo bloccato.
  const repaired = restoreBenchActiveRoles(
    ordered.map((athleteId) => ({ athleteId, role: roleOf(athleteId) })),
    { lockedAthleteIds: held, unfieldableAthleteIds: input.unfieldableAthleteIds ?? [] },
  );
  return {
    starterIds,
    benchIds: repaired.bench.map((player) => player.athleteId),
    heldBenchIds: held.filter((athleteId) => !locked.has(athleteId)),
  };
}

/**
 * Chi sale titolare in uno slot vuoto (dopo «Svuota formazione», o dopo che il server ha tolto chi
 * non è più in rosa) lascia un buco in panchina, e chi viene dopo scorre di un posto. Se dopo il
 * buco c'è chi ha la partita già iniziata, scorrendo cambierebbe posto e il salvataggio verrebbe
 * rifiutato (`evaluateBenchOrderLock`). Allora il buco lo prende, come in uno scambio, il primo
 * pari ruolo non bloccato dopo l'ultimo bloccato che non era nella panchina salvata (di solito un
 * titolare tolto con «Svuota formazione»).
 *
 * Restituisce la panchina senza `athleteId` con il buco riempito, oppure `null` quando non serve
 * (nessun bloccato dopo il buco, nessuna formazione salvata) o non c'è chi lo riempia: allora la
 * panchina scorre come prima.
 */
export function benchAfterStarterPick(input: {
  /** Panchina e tribuna attuali, in ordine. */
  bench: readonly string[];
  /** Chi sale titolare. */
  athleteId: string;
  /** La panchina della formazione salvata (quella con cui il server confronta). */
  savedBench: readonly string[];
  lockedAthleteIds: readonly string[];
  roleByAthleteId: Readonly<Record<string, string | null | undefined>>;
}): string[] | null {
  const bench = input.bench.filter(Boolean);
  const index = bench.indexOf(input.athleteId);
  const locked = new Set(input.lockedAthleteIds.filter(Boolean));
  let lastLocked = -1;
  bench.forEach((athleteId, position) => {
    if (locked.has(athleteId)) {
      lastLocked = position;
    }
  });
  if (index < 0 || lastLocked < index || input.savedBench.filter(Boolean).length === 0) {
    return null;
  }
  const saved = new Set(input.savedBench);
  const role = input.roleByAthleteId[input.athleteId];
  const fill = bench.findIndex(
    (athleteId, position) =>
      position > lastLocked &&
      !locked.has(athleteId) &&
      !saved.has(athleteId) &&
      role != null &&
      input.roleByAthleteId[athleteId] === role,
  );
  if (fill < 0) {
    return null;
  }
  const next = [...bench];
  next[index] = bench[fill] as string;
  next.splice(fill, 1);
  return next;
}

/**
 * Testi di «Svuota formazione» (Rosario, 20/11). La panchina non può restare vuota: torna
 * all'ordine della rosa, e i testi lo dicono. Copia per l'app in
 * `apps/mobile/src/screens/formation/clearLineup.ts`.
 */
export const CLEAR_LINEUP_TITLE = "Svuota formazione";
export const CLEAR_LINEUP_DESCRIPTION =
  "Toglie i titolari e rimette la panchina nell'ordine della rosa, per ricominciare da capo.";
export const CLEAR_LINEUP_CONFIRM_TITLE = "Svuotare la formazione?";
export const CLEAR_LINEUP_CONFIRM_BODY =
  "Tolgo tutti i titolari e rimetto la panchina nell'ordine della rosa, così la ricomponi da capo.";
export const CLEAR_LINEUP_CONFIRM_POINTS: readonly string[] = [
  "I giocatori già bloccati restano al loro posto.",
  "Finché non salvi, vale ancora la formazione salvata: puoi tornare indietro con «Annulla modifiche».",
  "A turno iniziato, salvare la nuova formazione conta come una mossa.",
];
export const CLEAR_LINEUP_CANCEL_LABEL = "Indietro";
/** Sul web il tasto della conferma ripete l'azione; nell'app (Alert) basta «Svuota». */
export const CLEAR_LINEUP_CONFIRM_LABEL = "Svuota formazione";
const CLEAR_LINEUP_HELD_NOTE = "In panchina resta al suo posto anche chi è davanti a un giocatore già bloccato.";

/**
 * Messaggio dopo lo svuotamento sul web: i titolari si scelgono dall'elenco «Titolari» (i cerchi
 * del campo aprono la scheda del calciatore) e il tasto è «Applica formazione migliore».
 */
export function clearLineupSuccessMessage(heldBenchCount: number): string {
  const base = "Formazione svuotata. Scegli i titolari nell'elenco «Titolari», oppure usa «Applica formazione migliore».";
  return heldBenchCount > 0 ? `${base} ${CLEAR_LINEUP_HELD_NOTE}` : base;
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
  /** Di sicuro senza voto nel turno (`selectionBlocked`): non alzano la quota dei primi 10. */
  unfieldableAthleteIds?: readonly string[];
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
        // Con 1 «manca 1», non «mancano 1» (QA 24-25/11; `missingCount` di plural.ts, qui in
        // linea perché i moduli dei contratti non si importano a runtime fra loro).
        `Tutti i calciatori in rosa devono essere schierati: ${
          unusedRoster.length === 1 ? "manca 1" : `mancano ${unusedRoster.length}`
        } in panchina.`,
      ),
    );
  }

  if (strict) {
    const missing = benchActiveShortfall(input.bench, input.unfieldableAthleteIds ?? []);
    if (Object.keys(missing).length > 0) {
      issues.push(issue("bench_roles_invalid", benchQuotaMessage(missing)));
    }
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
 * True when the athlete's real match has started, or is about to. Server
 * clock is authoritative; simultaneous kickoffs lock together at the same
 * UTC instant.
 *
 * `marginMinutes` anticipates the lock instant (formazione a step,
 * EP-turni-automazione) — mirror of `is_athlete_kickoff_locked` in
 * `backend/src/fantasy_lineups/rules.py`. Optional and trailing so every
 * existing call site keeps working unchanged; 0 reproduces the previous
 * exact-kickoff behavior.
 */
export function isAthleteKickoffLocked(
  now: string | Date,
  kickoffAt: string | Date | null | undefined,
  statusShort?: string | null,
  lockLatched?: boolean,
  marginMinutes = 0,
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
  return ensureUtcMs(now) >= ensureUtcMs(kickoffAt) - marginMinutes * 60_000;
}

/** Istante di blocco ancora futuro del calciatore, oppure null se è già bloccato o senza orario. */
export function athleteLockAt(
  now: string | Date,
  kickoffAt: string | Date | null | undefined,
  statusShort?: string | null,
  lockLatched?: boolean,
  marginMinutes = 0,
): string | null {
  if (
    !kickoffAt ||
    isAthleteKickoffLocked(now, kickoffAt, statusShort, lockLatched, marginMinutes)
  ) {
    return null;
  }
  return new Date(ensureUtcMs(kickoffAt) - marginMinutes * 60_000).toISOString();
}

/** Il blocco più vicino tra i calciatori schierati (campo, panchina, tribuna). */
export function earliestAthleteLockAt(
  players: readonly {
    kickoffAt?: string | Date | null;
    fixtureStatus?: string | null;
    lockLatched?: boolean;
  }[],
  now: string | Date,
  marginMinutes = 0,
): string | null {
  let bestMs: number | null = null;
  let bestIso: string | null = null;
  for (const player of players) {
    const iso = athleteLockAt(
      now,
      player.kickoffAt,
      player.fixtureStatus,
      player.lockLatched,
      marginMinutes,
    );
    if (!iso) {
      continue;
    }
    const ms = ensureUtcMs(iso);
    if (bestMs == null || ms < bestMs) {
      bestMs = ms;
      bestIso = iso;
    }
  }
  return bestIso;
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

/**
 * "Salva formazione" stops on a started match or on exhausted tactical moves
 * for every user except the platform operator. The API already skips both
 * gates for GLOBAL_OPERATE; clients must do the same or the button rejects
 * the save before the request is sent.
 */
export function blockingLineupSaveIssue(input: {
  isPlatformOperator: boolean;
  lockIssues: readonly LineupIssue[];
  tacticalIssues: readonly LineupIssue[];
}): LineupIssue | null {
  // L'operatore non è fermato dai blocchi dei singoli calciatori, ma le mosse finite valgono
  // per la squadra chiunque la schieri.
  if (input.isPlatformOperator) {
    return input.tacticalIssues[0] ?? null;
  }
  return input.lockIssues[0] ?? input.tacticalIssues[0] ?? null;
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
  /** Anticipo del blocco in minuti (come `isAthleteKickoffLocked`); 0 se assente. */
  lockMarginMinutes?: number;
}): string[] {
  const next = input.template.map(() => "");
  const rosterById = new Map(input.roster.map((row) => [row.athleteId, row]));
  // `currentStarters` può contenere lo stesso atleta bloccato più di una
  // volta (es. sia nella bozza in corso sia nella formazione confermata):
  // senza questo controllo verrebbe riservato due volte, duplicandolo su
  // due slot dello stesso ruolo.
  const reserved = new Set<string>();
  for (const athleteId of input.currentStarters) {
    if (reserved.has(athleteId)) {
      continue;
    }
    const player = rosterById.get(athleteId);
    if (!player?.role) {
      continue;
    }
    if (!isRosterPlayerLocked(player, input.now, input.lockMarginMinutes)) {
      continue;
    }
    const slot = next.findIndex((value, index) => !value && input.template[index] === player.role);
    if (slot >= 0) {
      next[slot] = athleteId;
      reserved.add(athleteId);
    }
  }
  return next;
}

function isRosterPlayerLocked(
  player: LineupRosterPlayer,
  now: string | Date | undefined,
  marginMinutes = 0,
): boolean {
  return (
    player.locked === true ||
    (now != null &&
      isAthleteKickoffLocked(now, player.kickoffAt, player.fixtureStatus, player.lockLatched, marginMinutes))
  );
}

/**
 * Cambio modulo quando la «formazione migliore» non si può chiedere al server (demo, turno non
 * modificabile, errore di rete, rosa insufficiente): tiene i titolari compatibili con il nuovo
 * modulo invece di svuotare la formazione.
 *
 * 1. I titolari bloccati prima di tutti, come `preserveLockedStarters` (primo slot libero del
 *    loro ruolo).
 * 2. Poi i titolari non bloccati, nel loro ordine attuale, nei posti rimasti del loro ruolo.
 * 3. Chi non entra più torna in panchina con la regola di `orderedBenchFromRoster` (l'ordine
 *    salvato resta, chi scende va in coda); gli slot senza un pari ruolo restano vuoti.
 *
 * Un titolare bloccato che non trova posto nel nuovo modulo resta fuori dagli slot: chi chiama
 * deve controllarlo prima (il modulo non è raggiungibile) e non applicare il risultato.
 */
export function keepStartersForModule(input: {
  module: FantasyModule;
  currentStarters: readonly string[];
  /** Ordine di panchina attuale, da conservare per chi resta in panchina. */
  benchIds?: readonly string[];
  roster: readonly LineupRosterPlayer[];
  now?: string | Date;
  lockMarginMinutes?: number;
}): ModuleChangePlan {
  const template = starterTemplate(input.module);
  const starters = preserveLockedStarters({
    template,
    currentStarters: input.currentStarters,
    roster: input.roster,
    now: input.now,
    lockMarginMinutes: input.lockMarginMinutes,
  });
  const rosterById = new Map(input.roster.map((row) => [row.athleteId, row]));
  // Stesso atleta ripetuto in `currentStarters`: entra una volta sola.
  const placed = new Set(starters.filter(Boolean));
  for (const athleteId of input.currentStarters) {
    if (!athleteId || placed.has(athleteId)) {
      continue;
    }
    const player = rosterById.get(athleteId);
    // I bloccati li ha già sistemati il primo passaggio: se non sono lì, non c'è posto per loro.
    if (!player?.role || isRosterPlayerLocked(player, input.now, input.lockMarginMinutes)) {
      continue;
    }
    const slot = starters.findIndex((value, index) => !value && template[index] === player.role);
    if (slot >= 0) {
      starters[slot] = athleteId;
      placed.add(athleteId);
    }
  }
  return {
    starterIds: starters,
    // Chi è in esubero di ruolo non entra nella panchina della formazione.
    benchIds: orderedBenchFromRoster(
      withoutRoleQuotaExcess(
        input.roster.map((row) => row.athleteId),
        input.roster,
      ),
      starters,
      input.benchIds ?? [],
    ),
  };
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
 * Avviso del server nel contesto formazione (QA 19/11): chi non è più in rosa (scambio,
 * svincolo, asta, rimozione dell'admin) è stato tolto dalla formazione o dalla bozza di un
 * turno ancora aperto e il suo posto è vuoto.
 */
export const LINEUP_ATHLETE_LEFT_ROSTER_CODE = "lineup_athlete_left_roster";

/** Messaggi degli avvisi «non è più nella tua rosa» tra le `issues` del contesto. */
export function rosterDepartureNotices(issues: readonly LineupIssue[] | null | undefined): string[] {
  return (issues ?? [])
    .filter((item) => item.code === LINEUP_ATHLETE_LEFT_ROSTER_CODE)
    .map((item) => item.message);
}

/**
 * Rosa che non può schierare (es. 34/35 dopo uno scambio 2 per 1): il server la mette come primo
 * elemento delle `issues` del contesto formazione, col motivo («Rosa incompleta: 34 giocatori su
 * 35. Completa la rosa (mercato o scambio) per schierare la formazione.»).
 */
export const ROSTER_NOT_VALIDATED_CODE = "roster_not_validated";

/** Messaggio del server sulla rosa che non può schierare, `null` se la rosa è a posto. */
export function rosterBlockNotice(issues: readonly LineupIssue[] | null | undefined): string | null {
  return (issues ?? []).find((item) => item.code === ROSTER_NOT_VALIDATED_CODE)?.message ?? null;
}

/**
 * Titolari della formazione salvata nei posti del modulo, secondo `sortOrder`.
 *
 * Il server toglie dalla formazione restituita chi non è più in rosa e il suo posto resta vuoto:
 * gli altri tengono il loro `sortOrder`. In fila per indice scalerebbero di un posto (es. un
 * centrocampista nello slot di un difensore). Un `sortOrder` fuori dal modulo o già occupato va
 * nel primo posto libero.
 */
export function savedStarterSlotIds(
  starters: readonly Pick<LineupPlayer, "athleteId" | "sortOrder">[],
  slotCount: number,
): string[] {
  const slots = Array.from({ length: slotCount }, () => "");
  const unplaced: string[] = [];
  for (const player of starters) {
    const index = player.sortOrder;
    if (Number.isInteger(index) && index >= 0 && index < slotCount && !slots[index]) {
      slots[index] = player.athleteId;
    } else {
      unplaced.push(player.athleteId);
    }
  }
  for (const athleteId of unplaced) {
    const free = slots.indexOf("");
    if (free < 0) {
      break;
    }
    slots[free] = athleteId;
  }
  return slots;
}

/**
 * Gli stessi id senza chi è in esubero di ruolo (`exceedsRoleQuota`, QA 19/11).
 *
 * Chi è in esubero resta in rosa ma non si schiera finché la rosa non torna in regola: non va
 * nella formazione mandata al server (titolari, panchina e tribuna) né nel confronto con quella
 * salvata. Il server lo toglie comunque in silenzio dalla tribuna (app già installate) e rifiuta
 * la formazione se è titolare o nei primi 10 della panchina. Serve sia per gli id della rosa da
 * dare a `orderedBenchFromRoster` sia per una panchina già fatta.
 */
export function withoutRoleQuotaExcess(
  athleteIds: readonly string[],
  roster: readonly Pick<LineupRosterPlayer, "athleteId" | "exceedsRoleQuota">[],
): string[] {
  const excess = new Set(roster.filter((row) => row.exceedsRoleQuota === true).map((row) => row.athleteId));
  return athleteIds.filter((athleteId) => !excess.has(athleteId));
}

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
/**
 * Eccezioni allo scavalcamento, purché i bloccati non si spostino: chi entra prende il posto
 * esatto di un pari ruolo uscito (scambio 1:1), oppure dopo di lui non ci sono bloccati del
 * suo ruolo (es. cambio modulo). I cambi automatici vanno solo a parità di ruolo.
 */
export function evaluateBenchOrderLock(input: {
  previousBench: readonly string[];
  proposedBench: readonly string[];
  lockedAthleteIds: readonly string[];
  roleByAthleteId?: Readonly<Record<string, string | null | undefined>>;
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

  // Il bloccato tiene il suo numero (panchina o tribuna) e davanti a lui non diminuiscono i pari
  // ruolo: altrimenti, con un cambio modulo, guadagnerebbe priorità nei cambi automatici.
  const sameRoleAhead = (list: readonly string[], index: number, athleteId: string): number => {
    const role = input.roleByAthleteId?.[athleteId];
    if (role == null) {
      return 0;
    }
    return list.slice(0, index).filter((other) => input.roleByAthleteId?.[other] === role).length;
  };
  if (issues.length === 0) {
    for (const lockedId of lockedRemaining) {
      const previousIndex = previous.indexOf(lockedId);
      const proposedIndex = proposed.indexOf(lockedId);
      if (
        previousIndex !== proposedIndex ||
        sameRoleAhead(proposed, proposedIndex, lockedId) < sameRoleAhead(previous, previousIndex, lockedId)
      ) {
        issues.push(issue("bench_order_locked", BENCH_ORDER_LOCKED_MESSAGE));
        break;
      }
    }
  }

  if (lockedRemaining.length > 0 && issues.length === 0) {
    const lastLockedProposed = Math.max(...lockedRemaining.map((athleteId) => proposed.indexOf(athleteId)));
    const lockedKeepPosition = lockedRemaining.every(
      (athleteId) => previous.indexOf(athleteId) === proposed.indexOf(athleteId),
    );
    const roles = input.roleByAthleteId;
    for (const [index, athleteId] of proposed.entries()) {
      if (previousSet.has(athleteId) || index >= lastLockedProposed) {
        continue;
      }
      const departed = index < previous.length ? previous[index] : undefined;
      const incomingRole = roles?.[athleteId];
      const sameRoleSlot =
        roles !== undefined &&
        departed !== undefined &&
        !proposedSet.has(departed) &&
        incomingRole != null &&
        incomingRole === roles[departed];
      const noLockedSameRoleAfter =
        roles !== undefined &&
        incomingRole != null &&
        !proposed.slice(index + 1).some((other) => locked.has(other) && roles[other] === incomingRole);
      if (lockedKeepPosition && (sameRoleSlot || noLockedSameRoleAfter)) {
        continue;
      }
      issues.push(issue("bench_order_locked", BENCH_ORDER_LOCKED_MESSAGE));
      break;
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

  // Solo i primi BENCH_ACTIVE_SIZE: chi è in tribuna resta fuori dal turno.
  for (const benchPlayer of input.bench.slice(0, BENCH_ACTIVE_SIZE)) {
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

/** Esito per una squadra IA nel comando amministrativo (EP13-P05). */
export interface AiLineupTeamResult {
  fantasyTeamId: string;
  fantasyTeamName: string;
  outcome: string;
  message: string | null;
  starters: number;
  usedFallback: boolean;
}

export interface AiLineupRun {
  roundId: string;
  algorithmVersion: string;
  dryRun: boolean;
  teams: AiLineupTeamResult[];
  summary: string;
}

export type ModuleChangePlan = { starterIds: string[]; benchIds: string[] };

function combinations<T>(items: readonly T[], size: number, limit: number): T[][] {
  const out: T[][] = [];
  const walk = (start: number, picked: T[]) => {
    if (out.length >= limit) {
      return;
    }
    if (picked.length === size) {
      out.push([...picked]);
      return;
    }
    for (let index = start; index < items.length; index += 1) {
      picked.push(items[index] as T);
      walk(index + 1, picked);
      picked.pop();
    }
  };
  walk(0, []);
  return out;
}

/**
 * Cambio modulo a turno iniziato: i calciatori bloccati restano esattamente dove sono (titolari
 * restano titolari, in panchina e in tribuna stessa posizione). Cerca una disposizione valida:
 * tiene i titolari non bloccati finché il ruolo lo consente, fa salire dalla panchina chi manca
 * (stesso ruolo, non bloccato, disponibile) e manda in panchina chi esce. Restituisce `null` se
 * il modulo non è più raggiungibile: la UI lo mostra con il lucchetto.
 */
export function planModuleChange(input: {
  module: FantasyModule;
  starterIds: readonly string[];
  benchIds: readonly string[];
  roleByAthleteId: Readonly<Record<string, string | null | undefined>>;
  lockedAthleteIds: readonly string[];
  unavailableAthleteIds?: readonly string[];
  rosterAthleteIds: readonly string[];
  previousStarterIds: readonly string[];
  previousBenchIds: readonly string[];
}): ModuleChangePlan | null {
  const roles = input.roleByAthleteId;
  const locked = new Set(input.lockedAthleteIds.filter(Boolean));
  const unavailable = new Set((input.unavailableAthleteIds ?? []).filter(Boolean));
  const template = starterTemplate(input.module);
  const need = emptyCounts();
  for (const role of template) {
    need[role] += 1;
  }
  const currentStarters = input.starterIds.filter(Boolean);
  const bench = input.benchIds.filter(Boolean);
  const keep: Record<LineupRole, string[]> = { P: [], D: [], C: [], A: [] };
  const demoted: string[] = [];
  const missing = emptyCounts();
  const allRoles = ["P", "D", "C", "A"] as const;
  for (const role of allRoles) {
    const ofRole = currentStarters.filter((id) => roles[id] === role);
    const lockedOfRole = ofRole.filter((id) => locked.has(id));
    if (lockedOfRole.length > need[role]) {
      return null;
    }
    const unlockedOfRole = ofRole.filter((id) => !locked.has(id));
    const room = need[role] - lockedOfRole.length;
    keep[role] = [...lockedOfRole, ...unlockedOfRole.slice(0, room)];
    demoted.push(...unlockedOfRole.slice(room));
    missing[role] = need[role] - keep[role].length;
  }
  // Titolari senza ruolo riconosciuto: non possono restare in un modulo per ruoli.
  for (const id of currentStarters) {
    const role = roles[id];
    if (role !== "P" && role !== "D" && role !== "C" && role !== "A") {
      if (locked.has(id)) {
        return null;
      }
      demoted.push(id);
    }
  }

  // Scelte di chi sale dalla panchina, ruolo per ruolo (poche combinazioni: bastano).
  let choices: string[][] = [[]];
  for (const role of allRoles) {
    if (missing[role] === 0) {
      continue;
    }
    const candidates = bench.filter((id) => roles[id] === role && !locked.has(id) && !unavailable.has(id));
    if (candidates.length < missing[role]) {
      return null;
    }
    const picks = combinations(candidates, missing[role], 40);
    const next: string[][] = [];
    for (const base of choices) {
      for (const pick of picks) {
        next.push([...base, ...pick]);
        if (next.length >= 200) {
          break;
        }
      }
    }
    choices = next;
  }

  const referenceBench = input.previousBenchIds.filter(Boolean).length > 0 ? input.previousBenchIds.filter(Boolean) : bench;
  const previousStarters = input.previousStarterIds.filter(Boolean);
  const isValid = (starters: string[], proposedBench: string[]): boolean => {
    for (const id of locked) {
      const before = referenceBench.indexOf(id);
      if (before >= 0 && proposedBench.indexOf(id) !== before) {
        return false;
      }
      if (previousStarters.includes(id) && !starters.includes(id)) {
        return false;
      }
    }
    const asPlayers = (ids: readonly string[]) =>
      ids.map((athleteId) => ({ athleteId, role: (roles[athleteId] as LineupRole | undefined) ?? null }));
    const evaluation = evaluateLineup({
      module: input.module,
      starters: asPlayers(starters),
      bench: asPlayers(proposedBench),
      rosterAthleteIds: input.rosterAthleteIds,
    });
    if (!evaluation.valid) {
      return false;
    }
    if (previousStarters.length === 0 && input.previousBenchIds.length === 0) {
      return true;
    }
    const lockIssues = evaluateProgressiveLock({
      previousSlots: slotsFromLineupIds(previousStarters, input.previousBenchIds),
      proposedSlots: slotsFromLineupIds(starters, proposedBench),
      lockedAthleteIds: [...locked],
    });
    const orderIssues = evaluateBenchOrderLock({
      previousBench: input.previousBenchIds,
      proposedBench,
      lockedAthleteIds: [...locked],
      roleByAthleteId: roles,
    });
    return lockIssues.length === 0 && orderIssues.length === 0;
  };

  for (const promoted of choices) {
    const promotedByRole: Record<LineupRole, string[]> = { P: [], D: [], C: [], A: [] };
    for (const id of promoted) {
      const role = roles[id] as LineupRole;
      promotedByRole[role].push(id);
    }
    const queues: Record<LineupRole, string[]> = {
      P: [...keep.P, ...promotedByRole.P],
      D: [...keep.D, ...promotedByRole.D],
      C: [...keep.C, ...promotedByRole.C],
      A: [...keep.A, ...promotedByRole.A],
    };
    const starters = template.map((role) => queues[role].shift() ?? "");
    const promotedSet = new Set(promoted);

    // 1) chi scende prende i posti lasciati liberi (stesso ruolo prima), il resto in coda.
    const holes: string[] = [];
    const waiting = [...demoted];
    for (const id of bench) {
      if (!promotedSet.has(id)) {
        holes.push(id);
        continue;
      }
      const sameRole = waiting.findIndex((other) => roles[other] === roles[id]);
      const takeIndex = sameRole >= 0 ? sameRole : waiting.length > 0 ? 0 : -1;
      if (takeIndex >= 0) {
        holes.push(waiting.splice(takeIndex, 1)[0] as string);
      }
    }
    const filled = [...holes, ...waiting];
    if (isValid(starters, filled)) {
      return { starterIds: starters, benchIds: filled };
    }
    // 2) chi scende va in coda (tribuna), gli altri scorrono.
    const tail = [...bench.filter((id) => !promotedSet.has(id)), ...demoted];
    if (isValid(starters, tail)) {
      return { starterIds: starters, benchIds: tail };
    }
  }
  return null;
}
