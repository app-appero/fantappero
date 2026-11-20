/**
 * Quota per ruolo dei primi 10 della panchina nella schermata Formazione (Rosario, 20/11).
 *
 * Nei primi 10 della panchina servono 1 portiere, 3 difensori, 3 centrocampisti e 3 attaccanti
 * (o quanti ce ne sono in panchina). Quando un attaccante usciva dalla rosa la panchina si
 * ricompattava e al suo posto saliva il primo della tribuna, spesso un portiere: «Sistema la
 * panchina» non cambiava niente se l'unico attaccante da far salire era arrivato dopo l'ultimo
 * salvataggio e non prendeva il voto (tornava sempre in coda), e «Cambia» proponeva solo i
 * portieri.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Sul web lo stesso criterio è in `@fantappero/contracts`
 * (`restoreBenchActiveRoles`, `benchQuotaSwapIds`, `formationLineupBench`, e per «Svuota
 * formazione» `clearLineupKeepingLocked` e `benchAfterStarterPick`); sul server in
 * `restore_bench_active_roles` (backend/src/fantasy_lineups/rules.py).
 */
import type { LineupPlayerInput, LineupRole } from "@fantappero/contracts";

export const BENCH_ACTIVE_SIZE = 10;
const ROLES = ["P", "D", "C", "A"] as const;
const QUOTA: Record<LineupRole, number> = { P: 1, D: 3, C: 3, A: 3 };
const LABEL: Record<LineupRole, [string, string]> = {
  P: ["portiere", "portieri"],
  D: ["difensore", "difensori"],
  C: ["centrocampista", "centrocampisti"],
  A: ["attaccante", "attaccanti"],
};
const PLURAL_ARTICLE: Record<LineupRole, string> = {
  P: "i portieri",
  D: "i difensori",
  C: "i centrocampisti",
  A: "gli attaccanti",
};

const isRole = (role: unknown): role is LineupRole => role === "P" || role === "D" || role === "C" || role === "A";

function countRoles(players: readonly LineupPlayerInput[]): Record<LineupRole, number> {
  const counts: Record<LineupRole, number> = { P: 0, D: 0, C: 0, A: 0 };
  for (const player of players) {
    if (player.athleteId && isRole(player.role)) {
      counts[player.role] += 1;
    }
  }
  return counts;
}

/**
 * Ruoli che mancano nei primi 10 (stessa regola di `benchActiveShortfall` dei contratti): chi è in
 * `unfieldableAthleteIds` (di sicuro senza voto, `selectionBlocked`) non alza la quota.
 */
export function benchShortfall(
  bench: readonly LineupPlayerInput[],
  unfieldableAthleteIds: readonly string[] = [],
): Partial<Record<LineupRole, number>> {
  const unfieldable = new Set(unfieldableAthleteIds.filter(Boolean));
  const filled = bench.filter((player) => player.athleteId);
  const available = countRoles(filled.filter((player) => !unfieldable.has(player.athleteId)));
  const active = countRoles(filled.slice(0, BENCH_ACTIVE_SIZE));
  const missing: Partial<Record<LineupRole, number>> = {};
  for (const role of ROLES) {
    const required = Math.min(QUOTA[role], available[role]);
    if (active[role] < required) {
      missing[role] = required - active[role];
    }
  }
  return missing;
}

function quotaMessage(missing: Partial<Record<LineupRole, number>>): string {
  const parts = ROLES.filter((role) => missing[role]).map(
    (role) => `${missing[role]} ${LABEL[role][(missing[role] ?? 0) === 1 ? 0 : 1]}`,
  );
  return `Nei primi ${BENCH_ACTIVE_SIZE} della panchina servono 1 portiere, 3 difensori, 3 centrocampisti e 3 attaccanti (mancano: ${parts.join(", ")}).`;
}

export type BenchRepair<T extends LineupPlayerInput> = {
  bench: T[];
  moves: Array<{ promoted: T; demoted: T }>;
  missing: Partial<Record<LineupRole, number>>;
  message: string | null;
};

/**
 * Rimette in regola i primi 10 con il minimo di spostamenti: per ogni ruolo che manca l'ultimo
 * dei primi 10 che è in più per il suo ruolo scende e diventa il primo della tribuna, chi era dopo
 * di lui sale di un posto e il primo della tribuna con il ruolo che manca diventa il 10°. L'ordine
 * dentro ogni ruolo non cambia. Chi ha la partita già iniziata non si sposta e non si scavalca: se
 * serve, la panchina resta com'è e `message` dice quale ruolo manca e perché.
 */
export function restoreBenchActiveRoles<T extends LineupPlayerInput>(
  bench: readonly T[],
  lockedAthleteIds: readonly string[] = [],
  unfieldableAthleteIds: readonly string[] = [],
): BenchRepair<T> {
  const locked = new Set(lockedAthleteIds.filter(Boolean));
  const unfieldable = new Set(unfieldableAthleteIds.filter(Boolean));
  const empty = bench.filter((player) => !player.athleteId);
  let list = bench.filter((player) => player.athleteId);
  const moves: Array<{ promoted: T; demoted: T }> = [];
  const blocked: Partial<Record<LineupRole, "tribuna" | "bench" | "between">> = {};
  for (;;) {
    const missing = benchShortfall(list, unfieldableAthleteIds);
    const short = ROLES.filter((role) => missing[role]);
    if (short.length === 0) {
      break;
    }
    const available = countRoles(list.filter((player) => !unfieldable.has(player.athleteId)));
    const active = countRoles(list.slice(0, BENCH_ACTIVE_SIZE));
    const surplus = (player: T) =>
      !isRole(player.role) || active[player.role] > Math.min(QUOTA[player.role], available[player.role]);
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
        blocked[role] = "tribuna";
        continue;
      }
      if (demotable.length === 0) {
        blocked[role] = "bench";
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
        blocked[role] = "between";
        continue;
      }
      const [down, up] = pair;
      const promoted = list[up] as T;
      const demoted = list[down] as T;
      const nextActive = list.filter((_, index) => index < BENCH_ACTIVE_SIZE && index !== down);
      nextActive.push(promoted);
      list = [...nextActive, demoted, ...list.filter((_, index) => index >= BENCH_ACTIVE_SIZE && index !== up)];
      moves.push({ promoted, demoted });
      delete blocked[role];
      applied = true;
      break;
    }
    if (!applied) {
      break;
    }
  }
  const missing = benchShortfall(list, unfieldableAthleteIds);
  const short = ROLES.filter((role) => missing[role]);
  let message: string | null = null;
  if (short.length > 0) {
    const reasons = short.map((role) => {
      if (blocked[role] === "bench") {
        return `nei primi ${BENCH_ACTIVE_SIZE} chi potrebbe lasciare il posto a un ${LABEL[role][0]} ha la partita già iniziata`;
      }
      if (blocked[role] === "between") {
        return `tra la panchina e ${PLURAL_ARTICLE[role]} in tribuna c'è chi ha la partita già iniziata e non si può scavalcare`;
      }
      return `in tribuna non ci sono ${LABEL[role][1]} schierabili: hanno la partita già iniziata`;
    });
    message = `${quotaMessage(missing)} Non si può sistemare da sola: ${reasons.join("; ")}.`;
  }
  return { bench: [...list, ...empty], moves, missing, message };
}

/**
 * Con i primi 10 fuori quota, con chi si può scambiare il calciatore al posto `index`: per uno dei
 * primi 10 in più per il suo ruolo, chi in tribuna ha un ruolo che manca; per uno in tribuna con
 * un ruolo che manca, chi nei primi 10 è in più. «Cambia» li propone con quelli dello stesso ruolo.
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
  const missing = benchShortfall(bench, unfieldableAthleteIds);
  if (Object.keys(missing).length === 0) {
    return [];
  }
  const available = countRoles(bench.filter((player) => !unfieldable.has(player.athleteId)));
  const active = countRoles(bench.slice(0, BENCH_ACTIVE_SIZE));
  const surplus = (player: LineupPlayerInput) =>
    !isRole(player.role) || active[player.role] > Math.min(QUOTA[player.role], available[player.role]);
  if (index < BENCH_ACTIVE_SIZE) {
    if (!surplus(current)) {
      return [];
    }
    return bench
      .slice(BENCH_ACTIVE_SIZE)
      .filter(
        (player) =>
          player.athleteId && !unfieldable.has(player.athleteId) && isRole(player.role) && missing[player.role],
      )
      .map((player) => player.athleteId);
  }
  if (!isRole(current.role) || !missing[current.role] || unfieldable.has(current.athleteId)) {
    return [];
  }
  return bench
    .slice(0, BENCH_ACTIVE_SIZE)
    .filter((player) => player.athleteId && surplus(player))
    .map((player) => player.athleteId);
}

/**
 * La panchina della formazione (panchina e tribuna): chi è arrivato in rosa dopo l'ultimo
 * salvataggio e non può essere schierato (`isBlocked`) va in coda, a meno che non sia già stato
 * messo in un posto (`placedBench`, la panchina dell'editor, anche da «Sistema la panchina»).
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
export type ClearedLineup = {
  /** Gli slot del modulo: restano solo i titolari bloccati, nel loro slot; gli altri sono vuoti. */
  starterIds: string[];
  /** Panchina e tribuna ricomposte (tutta la rosa che non è titolare, come sempre). */
  benchIds: string[];
  /** Chi non è bloccato ma resta al suo posto in panchina perché davanti a un bloccato. */
  heldBenchIds: string[];
};

/**
 * «Svuota formazione» (Rosario, 20/11): toglie i titolari e la scelta della panchina per
 * ricominciare da capo. Solo l'editor: niente salvataggi, niente mosse. Stessa regola di
 * `clearLineupKeepingLocked` dei contratti (web).
 *
 * - Titolari: restano solo i bloccati (partita già iniziata), nello stesso slot.
 * - Panchina: non può restare vuota (tutta la rosa che non gioca è in panchina o in tribuna, e il
 *   server la vuole completa), quindi torna all'ordine della rosa, con in coda chi oggi non si può
 *   schierare e i primi 10 riportati alla quota 1P·3D·3C·3A da `restoreBenchActiveRoles`.
 * - Bloccati in panchina: restano al loro posto, e con loro chi li precede (davanti a un bloccato
 *   non si entra e non si esce, altrimenti il salvataggio viene rifiutato). Si riordina solo quello
 *   che viene dopo l'ultimo bloccato.
 *
 * Con tutti bloccati non cambia niente.
 */
export function clearLineupKeepingLocked(input: {
  starterIds: readonly string[];
  /** Panchina e tribuna attuali, in ordine (senza chi è in esubero di ruolo). */
  benchIds: readonly string[];
  /** La rosa schierabile nell'ordine della rosa (senza chi è in esubero di ruolo). */
  rosterAthleteIds: readonly string[];
  lockedAthleteIds: readonly string[];
  roleByAthleteId: Readonly<Record<string, string | null | undefined>>;
  /** Chi oggi non si può schierare (indisponibile, squalificato): in coda, dopo gli altri. */
  unavailableAthleteIds?: readonly string[];
  /** Di sicuro senza voto (`selectionBlocked`): non alza la quota dei primi 10. */
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
    return isRole(role) ? role : null;
  };
  // Chi resta al suo posto conta come bloccato: la quota si sistema solo dopo l'ultimo bloccato.
  const repaired = restoreBenchActiveRoles(
    ordered.map((athleteId) => ({ athleteId, role: roleOf(athleteId) })),
    held,
    input.unfieldableAthleteIds ?? [],
  );
  return {
    starterIds,
    benchIds: repaired.bench.map((player) => player.athleteId),
    heldBenchIds: held.filter((athleteId) => !locked.has(athleteId)),
  };
}

/**
 * Chi sale titolare in uno slot vuoto (dopo «Svuota formazione», o dopo che il server ha tolto chi
 * non è più in rosa) lascia un buco in panchina e chi viene dopo scorre. Se dopo il buco c'è chi ha
 * la partita già iniziata, cambierebbe posto e il salvataggio verrebbe rifiutato: allora il buco lo
 * prende, come in uno scambio, il primo pari ruolo non bloccato dopo l'ultimo bloccato che non era
 * nella panchina salvata (di solito un titolare tolto con «Svuota formazione»). Stessa regola di
 * `benchAfterStarterPick` dei contratti.
 *
 * `null` quando non serve (nessun bloccato dopo il buco, nessuna formazione salvata) o non c'è chi
 * riempia il buco: la panchina scorre come prima.
 */
export function benchAfterStarterPick(input: {
  bench: readonly string[];
  athleteId: string;
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
