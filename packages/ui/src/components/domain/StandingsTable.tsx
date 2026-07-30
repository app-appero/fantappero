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
  isCurrentUser?: boolean;
  highlightLabel?: string;
};

export type StandingsTableProps = {
  caption: string;
  positionLabel: string;
  teamLabel: string;
  playedLabel: string;
  pointsLabel: string;
  goalsLabel: string;
  rows: StandingsRow[];
  testId?: string;
};

/** Presentational standings table for wireframes and future classifica views. */
export function StandingsTable({
  caption,
  positionLabel,
  teamLabel,
  playedLabel,
  pointsLabel,
  goalsLabel,
  rows,
  testId = "standings-table",
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
              {row.teamName}
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
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
