import { type HTMLAttributes } from "react";
import { Card, CardBody } from "../Card.js";
import { classNames } from "../../utils/classNames.js";

export type ResultCardProps = HTMLAttributes<HTMLElement> & {
  homeTeam: string;
  awayTeam: string;
  homeScore: number;
  awayScore: number;
  caption?: string;
  provisional?: boolean;
  /** Shown when provisional is true (app-supplied copy). */
  provisionalLabel?: string;
  scoreAriaLabel?: string;
};

export function ResultCard({
  homeTeam,
  awayTeam,
  homeScore,
  awayScore,
  caption,
  provisional = false,
  provisionalLabel,
  scoreAriaLabel,
  className,
  ...rest
}: ResultCardProps) {
  return (
    <Card
      className={classNames("fa-result-card", provisional && "fa-result-card--provisional", className)}
      data-testid="result-card"
      {...rest}
    >
      <CardBody>
        <div className="fa-result-card__teams">
          <span className="fa-result-card__team">{homeTeam}</span>
          <span className="fa-result-card__score" aria-label={scoreAriaLabel}>
            {homeScore} – {awayScore}
          </span>
          <span className="fa-result-card__team">{awayTeam}</span>
        </div>
        {provisional && provisionalLabel ? (
          <p className="fa-result-card__provisional">{provisionalLabel}</p>
        ) : null}
        {caption ? <p className="fa-result-card__caption">{caption}</p> : null}
      </CardBody>
    </Card>
  );
}
