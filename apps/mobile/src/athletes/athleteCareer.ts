/**
 * Carriera della scheda calciatore (1.3, Rosario 21-22/11, canvas «Proposte 1.3», scheda
 * «Scheda calciatore»): una riga per stagione + squadra + campionato, dalla più recente, con
 * la stagione in corso evidenziata. Presenze, gol, assist e media voto; per i portieri gol
 * subiti, porte inviolate (solo dalla stagione in corso), rigori parati e parate. Un dato che
 * manca è «—».
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`.
 */
import type { AthleteCareerRow } from "@fantappero/contracts";

export const MISSING_STAT = "—";

/** Portiere: ruolo P (di lega o ufficiale). */
export function isGoalkeeperRole(role: string | null | undefined): boolean {
  return role === "P";
}

/** 2026 → «2026/27». */
export function careerSeasonTitle(seasonYear: number): string {
  return `${seasonYear}/${String((seasonYear + 1) % 100).padStart(2, "0")}`;
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : MISSING_STAT;
}

function formatAverage(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2).replace(".", ",") : MISSING_STAT;
}

export type CareerStat = {
  key: string;
  /** Etichetta intera, per le caselle e i lettori di schermo: «Presenze». */
  label: string;
  /** Etichetta corta nella riga della carriera: «pres.». */
  short: string;
  value: string;
};

type StatSpec = {
  key: string;
  label: string;
  short: string;
  pick: (row: AthleteCareerRow) => string;
};

const APPEARANCES: StatSpec = { key: "appearances", label: "Presenze", short: "pres.", pick: (row) => formatCount(row.appearances) };
const GOALS: StatSpec = { key: "goals", label: "Gol", short: "gol", pick: (row) => formatCount(row.goals) };
const ASSISTS: StatSpec = { key: "assists", label: "Assist", short: "assist", pick: (row) => formatCount(row.assists) };
const AVERAGE: StatSpec = { key: "averageRating", label: "Media voto", short: "media", pick: (row) => formatAverage(row.averageRating) };
const GOALS_CONCEDED: StatSpec = {
  key: "goalsConceded",
  label: "Gol subiti",
  short: "subiti",
  pick: (row) => formatCount(row.goalsConceded),
};
const CLEAN_SHEETS: StatSpec = {
  key: "cleanSheets",
  label: "Porte inviolate",
  short: "inviolate",
  pick: (row) => formatCount(row.cleanSheets),
};
const PENALTIES_SAVED: StatSpec = {
  key: "penaltiesSaved",
  label: "Rigori parati",
  short: "rig. parati",
  pick: (row) => formatCount(row.penaltiesSaved),
};
const SAVES: StatSpec = { key: "saves", label: "Parate", short: "parate", pick: (row) => formatCount(row.saves) };

const OUTFIELD_STATS: readonly StatSpec[] = [APPEARANCES, GOALS, ASSISTS, AVERAGE];
const GOALKEEPER_STATS: readonly StatSpec[] = [APPEARANCES, GOALS_CONCEDED, CLEAN_SHEETS, PENALTIES_SAVED, SAVES, AVERAGE];

/** Colonne della carriera: quelle del portiere o quelle di movimento. */
export function careerStatLabels(goalkeeper: boolean): string[] {
  return (goalkeeper ? GOALKEEPER_STATS : OUTFIELD_STATS).map((spec) => spec.label);
}

/** Dalla stagione più recente; a parità di stagione resta l'ordine ricevuto. */
export function sortCareerRows(rows: readonly AthleteCareerRow[]): AthleteCareerRow[] {
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => b.row.seasonYear - a.row.seasonYear || a.index - b.index)
    .map(({ row }) => row);
}

export type CareerRowModel = {
  key: string;
  /** «2026/27 · Lazio». */
  title: string;
  /** Campionato o `null` se non noto. */
  competition: string | null;
  isCurrent: boolean;
  stats: CareerStat[];
  accessibilityLabel: string;
};

/** Righe della carriera pronte da mostrare. */
export function careerRowModels(
  rows: readonly AthleteCareerRow[] | null | undefined,
  options: { goalkeeper: boolean },
): CareerRowModel[] {
  const specs = options.goalkeeper ? GOALKEEPER_STATS : OUTFIELD_STATS;
  return sortCareerRows(rows ?? []).map((row, index) => {
    const club = row.clubName?.trim() || "Squadra non nota";
    const season = careerSeasonTitle(row.seasonYear);
    const stats = specs.map((spec) => ({ key: spec.key, label: spec.label, short: spec.short, value: spec.pick(row) }));
    const competition = row.competitionName?.trim() || null;
    const head = [season, club, competition, row.isCurrent ? "in corso" : null].filter(Boolean).join(", ");
    return {
      key: `${row.seasonYear}-${row.clubId ?? row.clubName ?? ""}-${row.competitionId ?? row.competitionName ?? ""}-${index}`,
      title: `${season} · ${club}`,
      competition,
      isCurrent: row.isCurrent,
      stats,
      accessibilityLabel: `${head}: ${stats.map((stat) => `${stat.label} ${stat.value}`).join(", ")}`,
    };
  });
}

function sumOf(rows: readonly AthleteCareerRow[], pick: (row: AthleteCareerRow) => number | null): number | null {
  let total: number | null = null;
  for (const row of rows) {
    const value = pick(row);
    if (typeof value === "number" && Number.isFinite(value)) {
      total = (total ?? 0) + value;
    }
  }
  return total;
}

/** Media pesata per partite con voto (o presenze); una riga sola resta com'è. */
function weightedAverage(
  rows: readonly AthleteCareerRow[],
  pick: (row: AthleteCareerRow) => number | null,
): number | null {
  const withValue = rows.filter((row) => {
    const value = pick(row);
    return typeof value === "number" && Number.isFinite(value);
  });
  if (withValue.length === 0) {
    return null;
  }
  if (withValue.length === 1) {
    return pick(withValue[0] as AthleteCareerRow);
  }
  let weighted = 0;
  let weights = 0;
  for (const row of withValue) {
    const weight = row.votes ?? row.appearances ?? 0;
    if (weight > 0) {
      weighted += (pick(row) as number) * weight;
      weights += weight;
    }
  }
  return weights > 0 ? weighted / weights : null;
}

export type CurrentSeasonSummary = {
  /** «Stagione 2026/27 · in corso». */
  title: string;
  tiles: CareerStat[];
};

/**
 * Caselle della stagione in corso in cima alla scheda (canvas), dalle righe `isCurrent` della
 * carriera (sommate se ha cambiato squadra); `null` se la carriera non ha la stagione in corso.
 */
export function currentSeasonSummary(
  rows: readonly AthleteCareerRow[] | null | undefined,
  options: { goalkeeper: boolean },
): CurrentSeasonSummary | null {
  const current = (rows ?? []).filter((row) => row.isCurrent);
  const first = current[0];
  if (!first) {
    return null;
  }
  const tile = (key: string, label: string, value: string): CareerStat => ({ key, label, short: label, value });
  const appearances = tile("appearances", "Presenze", formatCount(sumOf(current, (row) => row.appearances)));
  const average = tile("averageRating", "Media voto", formatAverage(weightedAverage(current, (row) => row.averageRating)));
  const fantasy = tile("fantasyAverage", "Fantamedia", formatAverage(weightedAverage(current, (row) => row.fantasyAverage)));
  const tiles = options.goalkeeper
    ? [
        appearances,
        tile("goalsConceded", "Gol subiti", formatCount(sumOf(current, (row) => row.goalsConceded))),
        tile("cleanSheets", "Porte inviolate", formatCount(sumOf(current, (row) => row.cleanSheets))),
        tile("penaltiesSaved", "Rigori parati", formatCount(sumOf(current, (row) => row.penaltiesSaved))),
        tile("saves", "Parate", formatCount(sumOf(current, (row) => row.saves))),
        average,
        fantasy,
      ]
    : [
        appearances,
        tile("goals", "Gol", formatCount(sumOf(current, (row) => row.goals))),
        tile("assists", "Assist", formatCount(sumOf(current, (row) => row.assists))),
        average,
        fantasy,
        tile("redCards", "Espulsioni", formatCount(sumOf(current, (row) => row.redCards))),
      ];
  return { title: `Stagione ${careerSeasonTitle(first.seasonYear)} · in corso`, tiles };
}
