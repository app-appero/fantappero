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
  managerDisplayName?: string | null;
  /** Se presente è l'unico nome mostrato in classifica (al posto di squadra + nome). */
  managerNickname?: string | null;
  managerAvatarUrl?: string | null;
};

export type StandingsTableProps = {
  caption: string;
  positionLabel: string;
  teamLabel: string;
  playedLabel: string;
  pointsLabel: string;
  goalsLabel: string;
  /** Se presente, gol fatti e gol subiti sono due colonne separate (`goalsLabel` = gol fatti). */
  goalsAgainstLabel?: string;
  /** Quando presente aggiunge la colonna Fantapunti. Con `goalsAgainstLabel` mostra solo i fatti. */
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
function primaryLabel(row: StandingsRow): string {
  return row.managerNickname?.trim() || row.managerDisplayName?.trim() || row.teamName;
}

export function StandingsTable({
  caption,
  positionLabel,
  teamLabel,
  playedLabel,
  pointsLabel,
  goalsLabel,
  goalsAgainstLabel,
  fantasyPointsLabel,
  rows,
  testId = "standings-table",
  onManagerClick,
}: StandingsTableProps) {
  const split = Boolean(goalsAgainstLabel);
  return (
    <>
    <StandingsCards
      rows={rows}
      onManagerClick={onManagerClick}
      labels={{ played: playedLabel, goalsFor: goalsLabel, goalsAgainst: goalsAgainstLabel, fantasy: fantasyPointsLabel }}
      testId={`${testId}-cards`}
    />
    <Table compact data-testid={testId} className="fa-standings-desk">
      <caption className="fa-sr-only">{caption}</caption>
      <TableHead>
        <TableRow>
          <TableHeaderCell>{positionLabel}</TableHeaderCell>
          <TableHeaderCell>{teamLabel}</TableHeaderCell>
          <TableHeaderCell>{playedLabel}</TableHeaderCell>
          <TableHeaderCell>{pointsLabel}</TableHeaderCell>
          <TableHeaderCell>{goalsLabel}</TableHeaderCell>
          {split ? <TableHeaderCell>{goalsAgainstLabel}</TableHeaderCell> : null}
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
              <span className="fa-standings-row__identity">
                {row.managerDisplayName ? (
                  row.managerAvatarUrl ? (
                    <img
                      className="fa-standings-row__avatar"
                      src={row.managerAvatarUrl}
                      alt=""
                      aria-hidden="true"
                    />
                  ) : (
                    <span className="fa-standings-row__avatar fa-standings-row__avatar--initials" aria-hidden="true">
                      {row.managerDisplayName.charAt(0).toUpperCase()}
                    </span>
                  )
                ) : null}
                <span className="fa-standings-row__labels">
                  {onManagerClick && row.managerUserId ? (
                    <button
                      type="button"
                      className="fa-standings-row__manager-link"
                      onClick={() => onManagerClick(row)}
                      aria-label={`Apri il profilo di ${primaryLabel(row)}`}
                    >
                      <span>{primaryLabel(row)}</span>
                    </button>
                  ) : (
                    <span>{primaryLabel(row)}</span>
                  )}
                </span>
              </span>
              {row.highlightLabel ? (
                <Badge variant="accent" className="fa-standings-row__badge">
                  {row.highlightLabel}
                </Badge>
              ) : null}
            </TableCell>
            <TableCell>{row.played}</TableCell>
            <TableCell>{row.points}</TableCell>
            {split ? (
              <>
                <TableCell>{row.goalsFor}</TableCell>
                <TableCell>{row.goalsAgainst}</TableCell>
              </>
            ) : (
              <TableCell>
                {row.goalsFor}:{row.goalsAgainst}
              </TableCell>
            )}
            {fantasyPointsLabel ? (
              <TableCell>
                {split
                  ? (row.fantasyPointsFor ?? "—")
                  : `${row.fantasyPointsFor ?? "—"}:${row.fantasyPointsAgainst ?? "—"}`}
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
    </>
  );
}

/** Vista a schede (schermi stretti): come l'app mobile, un allenatore per scheda. */
function StandingsCards({
  rows,
  onManagerClick,
  labels,
  testId,
}: {
  rows: StandingsRow[];
  onManagerClick?: (row: StandingsRow) => void;
  labels: { played: string; goalsFor: string; goalsAgainst?: string; fantasy?: string };
  testId: string;
}) {
  return (
    <ul className="fa-standings-cards" data-testid={testId}>
      {rows.map((row) => {
        const name = primaryLabel(row);
        const initial = name.charAt(0).toUpperCase();
        return (
          <li
            key={row.id}
            className={
              row.isCurrentUser ? "fa-standings-card fa-standings-card--current" : "fa-standings-card"
            }
          >
            <div className="fa-standings-card__top">
              <span className="fa-standings-card__pos">{row.position}</span>
              {row.managerAvatarUrl ? (
                <img className="fa-standings-row__avatar" src={row.managerAvatarUrl} alt="" aria-hidden="true" />
              ) : (
                <span className="fa-standings-row__avatar fa-standings-row__avatar--initials" aria-hidden="true">
                  {initial}
                </span>
              )}
              {onManagerClick && row.managerUserId ? (
                <button
                  type="button"
                  className="fa-standings-card__name fa-standings-row__manager-link"
                  onClick={() => onManagerClick(row)}
                  aria-label={`Apri il profilo di ${name}`}
                >
                  {name}
                </button>
              ) : (
                <span className="fa-standings-card__name">{name}</span>
              )}
              <span className="fa-standings-card__points">
                <strong>{row.points}</strong>
                <small>PUNTI</small>
              </span>
            </div>
            <dl className="fa-standings-card__stats">
              <div><dt>Gare</dt><dd>{row.played}</dd></div>
              <div><dt>{labels.goalsAgainst ? "Gol fatti" : labels.goalsFor}</dt><dd>{labels.goalsAgainst ? row.goalsFor : `${row.goalsFor}:${row.goalsAgainst}`}</dd></div>
              {labels.goalsAgainst ? (
                <div className="fa-standings-card__stat--danger"><dt>Gol subiti</dt><dd>{row.goalsAgainst}</dd></div>
              ) : null}
              {labels.fantasy ? <div><dt>Fantapunti</dt><dd>{row.fantasyPointsFor ?? "—"}</dd></div> : null}
            </dl>
          </li>
        );
      })}
    </ul>
  );
}
