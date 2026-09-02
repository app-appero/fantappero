import { type HTMLAttributes } from "react";
import { Badge, type BadgeVariant } from "../Badge.js";
import { Card, CardBody } from "../Card.js";
import { classNames } from "../../utils/classNames.js";

export type PlayerCardProps = HTMLAttributes<HTMLElement> & {
  name: string;
  role: string;
  club: string;
  /** Fantasy rating or match score. */
  rating?: string | number;
  /** Short status label (e.g. "Titolare", "Infortunato"). */
  statusLabel?: string;
  statusVariant?: BadgeVariant;
};

export function PlayerCard({
  name,
  role,
  club,
  rating,
  statusLabel,
  statusVariant = "neutral",
  className,
  ...rest
}: PlayerCardProps) {
  return (
    <Card className={classNames("fa-player-card", className)} data-testid="player-card" {...rest}>
      <CardBody>
        <div className="fa-player-card__header">
          <div>
            <p className="fa-player-card__name">{name}</p>
            <p className="fa-player-card__meta">
              <Badge variant="accent">{role}</Badge>
              <span className="fa-player-card__club">{club}</span>
            </p>
          </div>
          {rating !== undefined ? (
            <span className="fa-player-card__rating" aria-label="Valutazione">
              {rating}
            </span>
          ) : null}
        </div>
        {statusLabel ? (
          <Badge variant={statusVariant} className="fa-player-card__status">
            {statusLabel}
          </Badge>
        ) : null}
      </CardBody>
    </Card>
  );
}

export type PlayerRowProps = HTMLAttributes<HTMLTableRowElement> & {
  name: string;
  role: string;
  club: string;
  rating?: string | number;
};

/** Compact table row variant for roster lists. */
export function PlayerRow({ name, role, club, rating, className, ...rest }: PlayerRowProps) {
  return (
    <tr className={classNames("fa-player-row", className)} data-testid="player-row" {...rest}>
      <td className="fa-player-row__name">{name}</td>
      <td className="fa-player-row__role">{role}</td>
      <td className="fa-player-row__club">{club}</td>
      <td className="fa-player-row__rating">{rating ?? "—"}</td>
    </tr>
  );
}
