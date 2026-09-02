import { Badge } from "../Badge.js";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../Table.js";

export type StandingsRow = {
  id: string;
  position: number;
  teamName: string;
  played: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  /** Fantapunti fatti/subiti, già formattati dall'app (EP13-P02). */
  fantasyPointsFor?: string;
  fantasyPointsAgainst?: string;
  isCurrentUser?: boolean;
  highlightLabel?: string;
  /** Fantallenatore proprietario della squadra; abilita il click sul nome. */
  managerUserId?: string;
};

export type StandingsTableProps = {
  caption: string;
  positionLabel: string;
  teamLabel: string;
  playedLabel: string;
  pointsLabel: string;
  goalsLabel: string;
  /** Quando presente aggiunge la colonna Fantapunti fatti:subiti. */
  fantasyPointsLabel?: string;
  rows: StandingsRow[];
  testId?: string;
  /**
   * Se presente, il nome squadra diventa cliccabile per le righe con
   * `managerUserId` — l'app decide dove portare (es. profilo fantallenatore),
   * questo componente resta senza dipendenze di routing.
   */
  onManagerClick?: (row: StandingsRow) => void;
};

/** Presentational standings table for wireframes and future classifica views. */
export function StandingsTable({
  caption,
  positionLabel,
  teamLabel,
  playedLabel,
  pointsLabel,
  goalsLabel,
  fantasyPointsLabel,
  rows,
  testId = "standings-table",
  onManagerClick,
}: StandingsTableProps) {
  return (
    <Table compact data-testid={testId}>
      <caption className="fa-sr-only">{caption}</caption>
      <TableHead>
        <TableRow>
          <TableHeaderCell>{positionLabel}</TableHeaderCell>
          <TableHeaderCell>{teamLabel}</TableHeaderCell>
          <TableHeaderCell>{playedLabel}</TableHeaderCell>
          <TableHeaderCell>{pointsLabel}</TableHeaderCell>
          <TableHeaderCell>{goalsLabel}</TableHeaderCell>
          {fantasyPointsLabel ? (
            <TableHeaderCell>{fantasyPointsLabel}</TableHeaderCell>
          ) : null}
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow
            key={row.id}
            data-testid={row.isCurrentUser ? "standings-row-current" : undefined}
            className={row.isCurrentUser ? "fa-standings-row--current" : undefined}
          >
            <TableCell>{row.position}</TableCell>
            <TableCell>
              {onManagerClick && row.managerUserId ? (
                <button
                  type="button"
                  className="fa-standings-row__manager-link"
                  onClick={() => onManagerClick(row)}
                  aria-label={`Apri il profilo del fantallenatore di ${row.teamName}`}
                >
                  {row.teamName}
                </button>
              ) : (
                row.teamName
              )}
              {row.highlightLabel ? (
                <Badge variant="accent" className="fa-standings-row__badge">
                  {row.highlightLabel}
                </Badge>
              ) : null}
            </TableCell>
            <TableCell>{row.played}</TableCell>
            <TableCell>{row.points}</TableCell>
            <TableCell>
              {row.goalsFor}:{row.goalsAgainst}
            </TableCell>
            {fantasyPointsLabel ? (
              <TableCell>
                {row.fantasyPointsFor ?? "—"}:{row.fantasyPointsAgainst ?? "—"}
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
