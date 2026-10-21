import { type HTMLAttributes } from "react";
import { Badge } from "../Badge.js";
import { Card, CardBody } from "../Card.js";
import { classNames } from "../../utils/classNames.js";

export type MatchStatus = "scheduled" | "live" | "finished" | "postponed" | "needs_update";

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
  /** Club crest, when the provider has published one. */
  homeLogoUrl?: string | null;
  awayLogoUrl?: string | null;
  /** Manager avatar for fantasy matchups. */
  homeAvatarUrl?: string | null;
  awayAvatarUrl?: string | null;
  homeSubtitle?: string;
  awaySubtitle?: string;
};

const STATUS_VARIANTS = {
  scheduled: "neutral",
  live: "accent",
  finished: "success",
  postponed: "warning",
  needs_update: "warning",
} as const;

function TeamMark({
  name,
  logoUrl,
  avatarUrl,
}: {
  name: string;
  logoUrl?: string | null;
  avatarUrl?: string | null;
}) {
  if (logoUrl) {
    return <img className="fa-match-card__team-logo" src={logoUrl} alt="" aria-hidden="true" />;
  }
  if (avatarUrl) {
    return <img className="fa-match-card__person-avatar" src={avatarUrl} alt="" aria-hidden="true" />;
  }
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="fa-match-card__avatar" aria-hidden="true">
      {initials}
    </span>
  );
}

export function MatchCard({
  homeTeam,
  awayTeam,
  kickoffLabel,
  status,
  statusLabel,
  contextLabel,
  score,
  homeLogoUrl,
  awayLogoUrl,
  homeAvatarUrl,
  awayAvatarUrl,
  homeSubtitle,
  awaySubtitle,
  className,
  ...rest
}: MatchCardProps) {
  return (
    <Card className={classNames("fa-match-card", className)} data-testid="match-card" {...rest}>
      <CardBody>
        {contextLabel ? <p className="fa-match-card__context">{contextLabel}</p> : null}
        <div className="fa-match-card__teams">
          <span className="fa-match-card__team">
            <TeamMark name={homeTeam} logoUrl={homeLogoUrl} avatarUrl={homeAvatarUrl} />
            <span className="fa-match-card__team-name">{homeTeam}</span>
            {homeSubtitle ? <span className="fa-match-card__team-subtitle">{homeSubtitle}</span> : null}
          </span>
          {score ? (
            <span className="fa-match-card__score" data-testid="match-card-score">
              {score.home} - {score.away}
            </span>
          ) : (
            <span className="fa-match-card__vs" aria-hidden="true">
              vs
            </span>
          )}
          <span className="fa-match-card__team">
            <TeamMark name={awayTeam} logoUrl={awayLogoUrl} avatarUrl={awayAvatarUrl} />
            <span className="fa-match-card__team-name">{awayTeam}</span>
            {awaySubtitle ? <span className="fa-match-card__team-subtitle">{awaySubtitle}</span> : null}
          </span>
        </div>
        <div className="fa-match-card__footer">
          <time className="fa-match-card__kickoff">{kickoffLabel}</time>
          <Badge variant={STATUS_VARIANTS[status]}>{statusLabel}</Badge>
        </div>
      </CardBody>
    </Card>
  );
}
