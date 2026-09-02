import type { MatchBadge, MatchBadgeKind } from "@fantappero/contracts";
import type { ReactElement } from "react";
import {
  AssistIcon,
  GoalIcon,
  OwnGoalIcon,
  PenaltyIcon,
  PenaltyMissedIcon,
  RedCardIcon,
  SubstitutionInIcon,
  SubstitutionOutIcon,
  YellowCardIcon,
} from "../../icons/MatchEventIcons.js";
import { classNames } from "../../utils/classNames.js";

const ICON_BY_KIND: Record<MatchBadgeKind, (size: number) => ReactElement> = {
  goal: (size) => <GoalIcon size={size} />,
  ownGoal: (size) => <OwnGoalIcon size={size} />,
  penaltyScored: (size) => <PenaltyIcon size={size} />,
  penaltyMissed: (size) => <PenaltyMissedIcon size={size} />,
  penaltySaved: (size) => <PenaltyIcon size={size} />,
  assist: (size) => <AssistIcon size={size} />,
  yellowCard: (size) => <YellowCardIcon size={size} />,
  redCard: (size) => <RedCardIcon size={size} />,
  substitutionIn: (size) => <SubstitutionInIcon size={size} />,
  substitutionOut: (size) => <SubstitutionOutIcon size={size} />,
};

const LABEL_BY_KIND: Record<MatchBadgeKind, string> = {
  goal: "Gol",
  ownGoal: "Autogol",
  penaltyScored: "Rigore segnato",
  penaltyMissed: "Rigore sbagliato",
  penaltySaved: "Rigore parato",
  assist: "Assist",
  yellowCard: "Ammonizione",
  redCard: "Espulsione",
  substitutionIn: "Entrato",
  substitutionOut: "Uscito",
};

export type EventBadgesProps = {
  badges: readonly MatchBadge[];
  size?: number;
  className?: string;
};

/** Riga di badge evento con conteggio (`⚽ ×2`), §6/§7. */
export function EventBadges({ badges, size = 14, className }: EventBadgesProps) {
  if (badges.length === 0) {
    return null;
  }
  return (
    <span className={classNames("fa-event-badges", className)} data-testid="event-badges">
      {badges.map((badge) => (
        <span
          key={badge.kind}
          className="fa-event-badges__item"
          title={badge.count > 1 ? `${LABEL_BY_KIND[badge.kind]} ×${badge.count}` : LABEL_BY_KIND[badge.kind]}
          data-testid={`event-badge-${badge.kind}`}
        >
          {ICON_BY_KIND[badge.kind](size)}
          {badge.count > 1 ? (
            <span className="fa-event-badges__count">×{badge.count}</span>
          ) : null}
        </span>
      ))}
    </span>
  );
}
