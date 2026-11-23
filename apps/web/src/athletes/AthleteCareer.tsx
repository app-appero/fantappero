import type { AthleteCareerRow } from "@fantappero/contracts";
import { formatAverageValue, fullSeasonLabel } from "../market/athleteValue";

/**
 * Carriera della scheda calciatore (1.3, canvas «Scheda calciatore»): una riga per stagione,
 * squadra e campionato, dalla più recente, compresa quella in corso (evidenziata). Per i
 * portieri gol subiti, porte inviolate (solo dalla stagione in corso), rigori parati e parate
 * al posto di gol e assist. Su computer è una tabella, su telefono una scheda per stagione.
 */
type CareerColumn = {
  key: string;
  /** Intestazione corta della tabella («Pres.»). */
  short: string;
  /** Nome intero (tooltip e screen reader). */
  full: string;
  /** Parola dopo il numero nelle schede del telefono («pres.»). */
  unit: string;
  value: (row: AthleteCareerRow) => string;
};

function count(value: number | null): string {
  return value === null || value === undefined ? "—" : String(value);
}

function average(value: number | null): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "—" : formatAverageValue(value);
}

const APPEARANCES: CareerColumn = {
  key: "appearances",
  short: "Pres.",
  full: "Presenze",
  unit: "pres.",
  value: (row) => count(row.appearances),
};

const AVERAGE: CareerColumn = {
  key: "average",
  short: "Media",
  full: "Media voto",
  unit: "media",
  value: (row) => average(row.averageRating),
};

const OUTFIELD_COLUMNS: CareerColumn[] = [
  APPEARANCES,
  { key: "goals", short: "Gol", full: "Gol", unit: "gol", value: (row) => count(row.goals) },
  { key: "assists", short: "Assist", full: "Assist", unit: "assist", value: (row) => count(row.assists) },
  AVERAGE,
];

const GOALKEEPER_COLUMNS: CareerColumn[] = [
  APPEARANCES,
  {
    key: "goalsConceded",
    short: "Subiti",
    full: "Gol subiti",
    unit: "subiti",
    value: (row) => count(row.goalsConceded),
  },
  {
    key: "cleanSheets",
    short: "Inviolate",
    full: "Porte inviolate",
    unit: "inviolate",
    value: (row) => count(row.cleanSheets),
  },
  {
    key: "penaltiesSaved",
    short: "Rig. parati",
    full: "Rigori parati",
    unit: "rig. parati",
    value: (row) => count(row.penaltiesSaved),
  },
  { key: "saves", short: "Parate", full: "Parate", unit: "parate", value: (row) => count(row.saves) },
  AVERAGE,
];

export function careerColumns(role: string | null | undefined): CareerColumn[] {
  return role === "P" ? GOALKEEPER_COLUMNS : OUTFIELD_COLUMNS;
}

/** Dalla stagione più recente; a parità di stagione resta l'ordine del backend. */
export function sortCareerRows(rows: readonly AthleteCareerRow[]): AthleteCareerRow[] {
  return [...rows].sort((left, right) => right.seasonYear - left.seasonYear);
}

/** «2026/27», come nel canvas (le righe del mercato usano la forma corta «25/26»). */
const careerSeasonLabel = fullSeasonLabel;

function rowKey(row: AthleteCareerRow, index: number): string {
  return `${row.seasonYear}-${row.clubId ?? row.clubName ?? ""}-${row.competitionId ?? row.competitionName ?? ""}-${index}`;
}

export function AthleteCareer({
  rows,
  role,
}: {
  rows: readonly AthleteCareerRow[];
  /** Ruolo del calciatore in lega: con «P» le colonne del portiere. */
  role: string | null | undefined;
}) {
  const columns = careerColumns(role);
  const sorted = sortCareerRows(rows);
  return (
    <section className="fa-athlete-card__section fa-athlete-career" data-testid="athlete-career">
      <h3>Carriera</h3>
      {sorted.length === 0 ? (
        <p className="fa-athlete-card__muted">Nessuna stagione nello storico.</p>
      ) : (
        <>
          <div className="fa-athlete-career__table-wrap">
            <table className="fa-athlete-career__table" data-testid="athlete-career-table">
              <thead>
                <tr>
                  <th scope="col">Stagione</th>
                  <th scope="col">Squadra</th>
                  <th scope="col">Campionato</th>
                  {columns.map((column) => (
                    <th
                      key={column.key}
                      scope="col"
                      className="fa-athlete-career__num"
                      data-column={column.key}
                    >
                      {column.short === column.full ? (
                        column.short
                      ) : (
                        <abbr title={column.full}>{column.short}</abbr>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((row, index) => (
                  <tr
                    key={rowKey(row, index)}
                    className={row.isCurrent ? "fa-athlete-career__row--current" : undefined}
                    data-testid={`athlete-career-row-${index}`}
                  >
                    <td>
                      {careerSeasonLabel(row.seasonYear)}
                      {row.isCurrent ? (
                        <>
                          <span aria-hidden="true"> ●</span>
                          <span className="fa-sr-only"> (in corso)</span>
                        </>
                      ) : null}
                    </td>
                    <td>{row.clubName ?? "—"}</td>
                    <td>{row.competitionName ?? "—"}</td>
                    {columns.map((column) => (
                      <td key={column.key} className="fa-athlete-career__num" data-column={column.key}>
                        {column.value(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="fa-athlete-career__cards" aria-label="Carriera stagione per stagione">
            {sorted.map((row, index) => (
              <li
                key={rowKey(row, index)}
                className={
                  row.isCurrent
                    ? "fa-athlete-career__card fa-athlete-career__card--current"
                    : "fa-athlete-career__card"
                }
              >
                <p className="fa-athlete-career__card-head">
                  <strong>
                    {careerSeasonLabel(row.seasonYear)} · {row.clubName ?? "—"}
                    {row.isCurrent ? <span className="fa-sr-only"> (in corso)</span> : null}
                  </strong>
                  <span>{row.competitionName ?? "—"}</span>
                </p>
                <p className="fa-athlete-career__card-line">
                  {columns.map((column, columnIndex) => (
                    <span key={column.key}>
                      {columnIndex > 0 ? " · " : null}
                      <b>{column.value(row)}</b> {column.unit}
                    </span>
                  ))}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
