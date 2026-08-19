import { type HTMLAttributes } from "react";
import { Badge } from "../Badge.js";
import { Card, CardBody } from "../Card.js";
import { classNames } from "../../utils/classNames.js";

export type MatchStatus = "scheduled" | "live" | "finished" | "postponed";

export type MatchCardProps = HTMLAttributes<HTMLElement> & {
  homeTeam: string;
  awayTeam: string;
  kickoffLabel: string;
  status: MatchStatus;
  /** Localized status caption supplied by the app. */
  statusLabel: string;
  /** Optional competition or matchday label. */
  contextLabel?: string;
  /** Live/final score, when known (omitted before kickoff). */
  score?: { home: number; away: number } | null;
};

const STATUS_VARIANTS = {
  scheduled: "neutral",
  live: "accent",
  finished: "success",
  postponed: "warning",
} as const;

export function MatchCard({
  homeTeam,
  awayTeam,
  kickoffLabel,
  status,
  statusLabel,
  contextLabel,
  score,
  className,
  ...rest
}: MatchCardProps) {
  return (
    <Card className={classNames("fa-match-card", className)} data-testid="match-card" {...rest}>
      <CardBody>
        {contextLabel ? <p className="fa-match-card__context">{contextLabel}</p> : null}
        <div className="fa-match-card__teams">
          <span className="fa-match-card__team">{homeTeam}</span>
          {score ? (
            <span className="fa-match-card__score" data-testid="match-card-score">
              {score.home} - {score.away}
            </span>
          ) : (
            <span className="fa-match-card__vs" aria-hidden="true">
              vs
            </span>
          )}
          <span className="fa-match-card__team">{awayTeam}</span>
        </div>
        <div className="fa-match-card__footer">
          <time className="fa-match-card__kickoff">{kickoffLabel}</time>
          <Badge variant={STATUS_VARIANTS[status]}>{statusLabel}</Badge>
        </div>
      </CardBody>
    </Card>
  );
}
