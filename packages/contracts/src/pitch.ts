/**
 * Logica di campo condivisa web/mobile (EP13-P04-quater): ruolo canonico,
 * posizionamento dei giocatori sul campo e badge evento per giocatore.
 *
 * Il provider reale usa i codici G/D/M/F, il fantacalcio usa P/D/C/A: sono
 * due alfabeti per gli stessi quattro ruoli. Qui vivono mappati su un unico
 * enum canonico, cosi' badge/colori restano coerenti indipendentemente dalla
 * fonte — senza inventare un terzo vocabolario da mostrare all'utente (il
 * codice originale resta visibile, cambia solo il colore/stile del badge).
 */

export type PitchRole = "GK" | "DEF" | "MID" | "FWD";

const ROLE_BY_CODE: Record<string, PitchRole> = {
  P: "GK",
  G: "GK",
  D: "DEF",
  C: "MID",
  M: "MID",
  A: "FWD",
  F: "FWD",
};

export const PITCH_ROLE_LABEL: Record<PitchRole, string> = {
  GK: "Portiere",
  DEF: "Difensore",
  MID: "Centrocampista",
  FWD: "Attaccante",
};

export type PitchRoleVariant = "success" | "warning" | "accent" | "danger";

export const PITCH_ROLE_VARIANT: Record<PitchRole, PitchRoleVariant> = {
  GK: "success",
  DEF: "warning",
  MID: "accent",
  FWD: "danger",
};

/** Ruolo canonico da un codice provider (G/D/M/F) o fantacalcio (P/D/C/A). */
export function resolvePitchRole(code: string | null | undefined): PitchRole | null {
  if (!code) {
    return null;
  }
  return ROLE_BY_CODE[code.trim().toUpperCase()] ?? null;
}

/** Variante colore coerente per badge ruolo, "neutral" implicito se il codice non è noto. */
export function pitchRoleVariant(code: string | null | undefined): PitchRoleVariant | "neutral" {
  const role = resolvePitchRole(code);
  return role ? PITCH_ROLE_VARIANT[role] : "neutral";
}

/** Etichetta estesa (per tooltip), il codice originale se non riconosciuto. */
export function pitchRoleFullLabel(code: string | null | undefined): string {
  const role = resolvePitchRole(code);
  return role ? PITCH_ROLE_LABEL[role] : (code ?? "?");
}

export interface PitchPosition {
  id: string;
  /** 0 (sinistra) — 100 (destra). */
  xPercent: number;
  /** 0 (in alto, attacco) — 100 (in basso, portiere). */
  yPercent: number;
}

function rowToYPercent(row: number, totalRows: number): number {
  if (totalRows <= 1) {
    return 90;
  }
  const t = (row - 1) / (totalRows - 1);
  return 92 - t * 82;
}

function columnToXPercent(index: number, count: number): number {
  if (count <= 1) {
    return 50;
  }
  const margin = 12;
  const usable = 100 - margin * 2;
  return margin + (index / (count - 1)) * usable;
}

export interface GridEntryLike {
  id: string;
  /** Formato provider `"riga:colonna"`, riga 1 = portiere. `null` se non disponibile. */
  grid: string | null;
}

/**
 * Posiziona i giocatori usando il campo `grid` del provider (fonte primaria,
 * §3): riga 1 = portiere, righe crescenti = più avanzate.
 */
export function layoutFromGrid<T extends GridEntryLike>(entries: readonly T[]): PitchPosition[] {
  const rows = new Map<number, { col: number; entry: T }[]>();
  let maxRow = 1;
  for (const entry of entries) {
    if (!entry.grid) {
      continue;
    }
    const [rowRaw, colRaw] = entry.grid.split(":");
    const row = Number.parseInt(rowRaw ?? "", 10);
    const col = Number.parseInt(colRaw ?? "", 10);
    if (!Number.isFinite(row) || !Number.isFinite(col)) {
      continue;
    }
    maxRow = Math.max(maxRow, row);
    const bucket = rows.get(row) ?? [];
    bucket.push({ col, entry });
    rows.set(row, bucket);
  }

  const positions: PitchPosition[] = [];
  for (const [row, bucket] of rows) {
    const sorted = [...bucket].sort((a, b) => a.col - b.col);
    const y = rowToYPercent(row, maxRow);
    sorted.forEach(({ entry }, index) => {
      positions.push({ id: entry.id, xPercent: columnToXPercent(index, sorted.length), yPercent: y });
    });
  }
  return positions;
}

function gridRow(grid: string | null): number | null {
  if (!grid) {
    return null;
  }
  const row = Number.parseInt(grid.split(":")[0] ?? "", 10);
  return Number.isFinite(row) ? row : null;
}

/**
 * Ruolo dedotto dalla riga del `grid` ufficiale (riga 1 = portiere, ultima
 * riga = attacco, righe intermedie = centrocampo): a differenza del campo
 * `pos` del provider — che riflette il ruolo abituale/anagrafico del
 * calciatore, non sempre quello schierato in questa specifica partita — è
 * sempre coerente con la riga in cui il giocatore viene effettivamente
 * disegnato da `layoutFromGrid`.
 */
export function pitchRoleCodeFromGrid(
  grid: string | null,
  allGrids: readonly (string | null)[],
): "G" | "D" | "M" | "F" | null {
  const row = gridRow(grid);
  if (row === null) {
    return null;
  }
  let maxRow = row;
  for (const other of allGrids) {
    const otherRow = gridRow(other);
    if (otherRow !== null) {
      maxRow = Math.max(maxRow, otherRow);
    }
  }
  if (row <= 1) {
    return "G";
  }
  if (row === maxRow) {
    return "F";
  }
  if (row === 2) {
    return "D";
  }
  return "M";
}

export interface RoleLayoutEntryLike {
  id: string;
  /** Codice ruolo del provider per questa partita (G/D/M/F): dove parte in campo. */
  position: string | null;
  /** Ruolo reale dalla rosa del provider (P/D/C/A), se il calciatore è abbinato. */
  fantasyRole?: string | null;
  /** Formato provider `"riga:colonna"`: solo ordinamento e tie-break, mai il reparto. */
  grid: string | null;
}

export interface RoleLayout {
  positions: PitchPosition[];
  /** Ruolo G/D/M/F mostrato nel badge e usato per il reparto, per id. */
  roles: Map<string, "G" | "D" | "M" | "F">;
}

const ROLE_CODE: Record<PitchRole, "G" | "D" | "M" | "F"> = {
  GK: "G",
  DEF: "D",
  MID: "M",
  FWD: "F",
};

const OUTFIELD_ORDER: PitchRole[] = ["DEF", "MID", "FWD"];

function gridSortKey(grid: string | null, index: number): [number, number, number] {
  const [rowRaw, colRaw] = (grid ?? "").split(":");
  const row = Number.parseInt(rowRaw ?? "", 10);
  const col = Number.parseInt(colRaw ?? "", 10);
  return [Number.isFinite(row) ? row : 99, Number.isFinite(col) ? col : 99, index];
}

function compareKeys(a: number[], b: number[]): number {
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) {
      return (a[i] ?? 0) - (b[i] ?? 0);
    }
  }
  return 0;
}

/**
 * Assegna a ogni titolare un reparto (G/D/M/F). Fonte principale: il ruolo
 * reale dalla rosa del provider (`fantasyRole`), altrimenti il `pos` della
 * partita. Se i conteggi non tornano col modulo (4-3-3 = 1+4+3+3) si
 * spostano i giocatori dal reparto in eccesso a quello in difetto, scegliendo
 * prima chi per il `pos` della partita parte già in quel reparto, poi chi ha
 * la riga di `grid` più vicina. Il portiere non si sposta mai.
 */
function assignRoles<T extends RoleLayoutEntryLike>(
  entries: readonly T[],
  formation: string | null | undefined,
): Map<string, PitchRole> | null {
  const assigned = new Map<string, PitchRole>();
  const matchRole = new Map<string, PitchRole | null>();
  for (const entry of entries) {
    const real = resolvePitchRole(entry.fantasyRole);
    const onPitch = resolvePitchRole(entry.position);
    const role = real ?? onPitch;
    if (!role) {
      return null;
    }
    assigned.set(entry.id, role);
    matchRole.set(entry.id, onPitch);
  }

  const parts = (formation ?? "").split("-").map((part) => Number.parseInt(part.trim(), 10));
  const validFormation =
    parts.length >= 2 &&
    parts.every((n) => Number.isFinite(n) && n > 0) &&
    parts.reduce((sum, n) => sum + n, 0) === entries.length - 1;
  if (!validFormation) {
    return assigned;
  }
  const target: Record<PitchRole, number> = {
    GK: 1,
    DEF: parts[0] ?? 0,
    MID: parts.slice(1, -1).reduce((sum, n) => sum + n, 0),
    FWD: parts[parts.length - 1] ?? 0,
  };
  const count = (role: PitchRole) => [...assigned.values()].filter((r) => r === role).length;
  if (count("GK") !== 1) {
    return assigned;
  }
  const rowOf = (entry: T, index: number) => gridSortKey(entry.grid, index)[0];

  for (let guard = 0; guard < entries.length; guard += 1) {
    const deficit = OUTFIELD_ORDER.find((role) => count(role) < target[role]);
    const surplus = OUTFIELD_ORDER.find((role) => count(role) > target[role]);
    if (!deficit || !surplus) {
      break;
    }
    const towardsAttack = OUTFIELD_ORDER.indexOf(deficit) > OUTFIELD_ORDER.indexOf(surplus);
    const candidates = entries
      .map((entry, index) => ({ entry, index }))
      .filter(({ entry }) => assigned.get(entry.id) === surplus);
    candidates.sort((a, b) => {
      const aMatch = matchRole.get(a.entry.id) === deficit ? 0 : 1;
      const bMatch = matchRole.get(b.entry.id) === deficit ? 0 : 1;
      if (aMatch !== bMatch) {
        return aMatch - bMatch;
      }
      const aRow = rowOf(a.entry, a.index);
      const bRow = rowOf(b.entry, b.index);
      return towardsAttack ? bRow - aRow : aRow - bRow;
    });
    const pick = candidates[0];
    if (!pick) {
      break;
    }
    assigned.set(pick.entry.id, deficit);
  }
  return assigned;
}

/**
 * Posiziona undici titolari reali per reparto reale, non per il `grid`: il
 * `grid` del provider può attribuire una riga sbagliata (un portiere in
 * difesa, un centrocampista in porta). Righe: portiere, difesa, una riga per
 * ogni cifra intermedia del modulo (4-2-3-1) quando coerente, attacco. Dentro
 * un reparto l'ordine sinistra-destra segue il `grid`.
 *
 * Restituisce `null` solo se manca il ruolo di almeno un giocatore: il
 * chiamante ricade allora su `layoutFromGrid`.
 */
export function layoutFromRoles<T extends RoleLayoutEntryLike>(
  entries: readonly T[],
  formation: string | null | undefined,
): RoleLayout | null {
  if (entries.length === 0) {
    return null;
  }
  const roleById = assignRoles(entries, formation);
  if (!roleById) {
    return null;
  }
  const buckets: Record<PitchRole, { entry: T; key: [number, number, number] }[]> = {
    GK: [],
    DEF: [],
    MID: [],
    FWD: [],
  };
  for (const [index, entry] of entries.entries()) {
    const role = roleById.get(entry.id);
    if (!role) {
      return null;
    }
    buckets[role].push({ entry, key: gridSortKey(entry.grid, index) });
  }
  for (const role of Object.keys(buckets) as PitchRole[]) {
    buckets[role].sort((a, b) => compareKeys(a.key, b.key));
  }

  const parts = (formation ?? "").split("-").map((part) => Number.parseInt(part.trim(), 10));
  const middleParts =
    parts.length >= 3 && parts.every((n) => Number.isFinite(n) && n > 0) ? parts.slice(1, -1) : [];
  const midSplit =
    middleParts.length > 0 && middleParts.reduce((sum, n) => sum + n, 0) === buckets.MID.length
      ? middleParts
      : [buckets.MID.length];

  const rows: T[][] = [buckets.GK.map((item) => item.entry), buckets.DEF.map((item) => item.entry)];
  const mids = buckets.MID.map((item) => item.entry);
  for (const count of midSplit) {
    rows.push(mids.splice(0, count));
  }
  rows.push(buckets.FWD.map((item) => item.entry));
  const filledRows = rows.filter((row) => row.length > 0);

  const positions: PitchPosition[] = [];
  filledRows.forEach((rowEntries, rowIndex) => {
    const ordered = [...rowEntries].sort((a, b) =>
      compareKeys(gridSortKey(a.grid, 0).slice(1), gridSortKey(b.grid, 0).slice(1)),
    );
    const y = rowToYPercent(rowIndex + 1, filledRows.length);
    ordered.forEach((entry, index) => {
      positions.push({ id: entry.id, xPercent: columnToXPercent(index, ordered.length), yPercent: y });
    });
  });
  const roles = new Map<string, "G" | "D" | "M" | "F">();
  for (const [id, role] of roleById) {
    roles.set(id, ROLE_CODE[role]);
  }
  return { positions, roles };
}

/**
 * Fallback quando il `grid` non è disponibile (sempre il caso per le
 * formazioni fantasy, mai schierate su un campo reale): usa modulo + ruolo +
 * ordine (§3). Il modulo è una stringa a trattini (`"4-2-3-1"`,
 * `"4-3-3"`...): nessun modulo è hardcodato, il numero di righe si adatta
 * dinamicamente a quante cifre contiene.
 */
export function layoutFromModule<T>(
  players: readonly T[],
  module: string | null | undefined,
  roleOf: (player: T) => string | null | undefined,
  idOf: (player: T) => string,
  sortKeyOf: (player: T) => number,
): PitchPosition[] {
  const buckets: Record<PitchRole, T[]> = { GK: [], DEF: [], MID: [], FWD: [] };
  for (const player of players) {
    const role = resolvePitchRole(roleOf(player));
    if (role) {
      buckets[role].push(player);
    }
  }
  (Object.keys(buckets) as PitchRole[]).forEach((role) => {
    buckets[role] = [...buckets[role]].sort((a, b) => sortKeyOf(a) - sortKeyOf(b));
  });

  const parsedRowCounts = (module ?? "")
    .split(/[-x]/i)
    .map((part) => Number.parseInt(part.trim(), 10))
    .filter((n) => Number.isFinite(n) && n > 0);
  // Nessun modulo leggibile: deduce le righe dalla composizione reale dei
  // ruoli disponibili invece di rinunciare al posizionamento.
  const rowCounts =
    parsedRowCounts.length > 0
      ? parsedRowCounts
      : [buckets.DEF.length, buckets.MID.length, buckets.FWD.length].filter((n) => n > 0);

  // Sempre 4 reparti (P, D, C, A) alla stessa altezza: due squadre con moduli
  // diversi (4-3-3 contro 4-2-3-1) restano allineate quando sono affiancate.
  const totalRows = 4;
  const positions: PitchPosition[] = [];

  const placeRow = (row: number, pool: T[], count: number): void => {
    const slice = pool.splice(0, Math.max(count, 0));
    slice.forEach((player, index) => {
      positions.push({
        id: idOf(player),
        xPercent: columnToXPercent(index, slice.length),
        yPercent: rowToYPercent(row, totalRows),
      });
    });
  };

  const gkPool = [...buckets.GK];
  placeRow(1, gkPool, gkPool.length || 1);

  if (rowCounts.length > 0) {
    const defPool = [...buckets.DEF];
    placeRow(2, defPool, rowCounts[0] ?? defPool.length);

    // Il fantacalcio non distingue mediano da trequartista: tutto il centrocampo
    // sta su una sola riga, qualunque cifra intermedia dichiari il modulo.
    const midPool = [...buckets.MID];
    placeRow(3, midPool, midPool.length);

    const fwdPool = [...buckets.FWD];
    const lastCount = rowCounts[rowCounts.length - 1] ?? fwdPool.length;
    placeRow(totalRows, fwdPool, lastCount);
  }

  return positions;
}

export type MatchBadgeKind =
  | "goal"
  | "ownGoal"
  | "penaltyScored"
  | "penaltyMissed"
  | "penaltySaved"
  | "assist"
  | "yellowCard"
  | "redCard"
  | "substitutionIn"
  | "substitutionOut";

export interface MatchBadge {
  kind: MatchBadgeKind;
  count: number;
}

/** Sottoinsieme di `FixtureTimelineEvent` sufficiente a derivare i badge. */
export interface RealMatchBadgeEvent {
  scoringKind: string | null;
  eventType: string;
  eventDetail: string | null;
  athleteId: string | null;
  relatedAthleteId: string | null;
}

function classifyRealEventKind(
  event: RealMatchBadgeEvent,
): "assist" | "substitutionOut" | Exclude<MatchBadgeKind, "assist" | "substitutionIn" | "substitutionOut"> | null {
  switch (event.scoringKind) {
    case "goal":
      return "goal";
    case "own_goal":
      return "ownGoal";
    case "penalty_scored":
      return "penaltyScored";
    case "penalty_missed":
    case "penalty_off_target":
      return "penaltyMissed";
    case "penalty_saved":
      return "penaltySaved";
    case "assist":
      return "assist";
    default:
      break;
  }
  const type = event.eventType.toLowerCase();
  const detail = (event.eventDetail ?? "").toLowerCase();
  if (type === "goal") {
    if (detail.includes("own")) {
      return "ownGoal";
    }
    if (detail.includes("missed")) {
      return "penaltyMissed";
    }
    if (detail.includes("penalty")) {
      return "penaltyScored";
    }
    return "goal";
  }
  if (type === "card") {
    if (detail.includes("red")) {
      return "redCard";
    }
    if (detail.includes("yellow")) {
      return "yellowCard";
    }
    return null;
  }
  if (type === "subst") {
    return "substitutionOut";
  }
  return null;
}

/**
 * Badge evento per giocatore, raggruppati per `athleteId` (§16: collegamento
 * per id, non per nome). Un gol con assist produce due badge su due
 * giocatori diversi; più eventi sullo stesso giocatore si sommano nel
 * `count` (§7).
 */
export function realMatchBadgesByAthlete(
  events: readonly RealMatchBadgeEvent[],
): Map<string, MatchBadge[]> {
  const byAthlete = new Map<string, Map<MatchBadgeKind, number>>();
  const bump = (athleteId: string | null, kind: MatchBadgeKind): void => {
    if (!athleteId) {
      return;
    }
    const bucket = byAthlete.get(athleteId) ?? new Map<MatchBadgeKind, number>();
    bucket.set(kind, (bucket.get(kind) ?? 0) + 1);
    byAthlete.set(athleteId, bucket);
  };

  for (const event of events) {
    const kind = classifyRealEventKind(event);
    if (!kind) {
      continue;
    }
    if (kind === "assist") {
      bump(event.relatedAthleteId, "assist");
      continue;
    }
    if (kind === "substitutionOut") {
      bump(event.athleteId, "substitutionOut");
      bump(event.relatedAthleteId, "substitutionIn");
      continue;
    }
    bump(event.athleteId, kind);
    // Il gol grezzo del provider porta già l'assist in `relatedAthleteId`
    // (la copia sintetica `scoring_kind="assist"` è deduplicata dal backend,
    // vedi live_view.build_timeline): va letto qui, non da un evento a parte.
    if (kind === "goal") {
      bump(event.relatedAthleteId, "assist");
    }
  }

  const result = new Map<string, MatchBadge[]>();
  for (const [athleteId, bucket] of byAthlete) {
    result.set(
      athleteId,
      [...bucket.entries()].map(([kind, count]) => ({ kind, count })),
    );
  }
  return result;
}

const FANTASY_BONUS_BADGE: Record<string, MatchBadgeKind> = {
  goal: "goal",
  assist: "assist",
  own_goal: "ownGoal",
  penalty_missed: "penaltyMissed",
  penalty_saved: "penaltySaved",
  yellow_card: "yellowCard",
  red_card: "redCard",
};

/** Badge "uscito/entrato" di un giocatore dai minuti di sostituzione (come gol e assist). */
export function substitutionBadges(player: {
  substitutedOutMinute?: number | null;
  substitutedInMinute?: number | null;
}): MatchBadge[] {
  const out: MatchBadge[] = [];
  if (player.substitutedInMinute != null) {
    out.push({ kind: "substitutionIn", count: 1 });
  }
  if (player.substitutedOutMinute != null) {
    out.push({ kind: "substitutionOut", count: 1 });
  }
  return out;
}

/** Badge di un giocatore fantasy dalle componenti bonus/malus già calcolate (§20). */
export function fantasyBadgesFromBonusMalus(
  components: readonly { id: string; count: number }[],
): MatchBadge[] {
  const out: MatchBadge[] = [];
  for (const component of components) {
    const kind = FANTASY_BONUS_BADGE[component.id];
    if (!kind) {
      continue;
    }
    out.push({ kind, count: component.count > 0 ? component.count : 1 });
  }
  return out;
}
