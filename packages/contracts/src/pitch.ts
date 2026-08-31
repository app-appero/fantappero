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

  const totalRows = rowCounts.length + 1;
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

    // Le righe tra la prima (difesa) e l'ultima (attacco) sono tutte
    // centrocampo: il fantacalcio non distingue mediano da trequartista, il
    // provider a volte sì (es. "4-2-3-1"), quindi il pool centrocampisti
    // viene distribuito in ordine sulle righe intermedie che il modulo
    // dichiara, quante che siano.
    const midRowCounts = rowCounts.slice(1, -1);
    const midPool = [...buckets.MID];
    midRowCounts.forEach((count, index) => {
      placeRow(3 + index, midPool, count);
    });

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
