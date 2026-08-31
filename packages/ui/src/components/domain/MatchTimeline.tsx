import { type ReactNode } from "react";
import { classNames } from "../../utils/classNames.js";

export type TimelineEventItem = {
  type: "event";
  id: string;
  side: "home" | "away";
  minuteLabel: string;
  icon?: ReactNode;
  headline: ReactNode;
  detail?: ReactNode;
};

export type TimelineMarkerItem = {
  type: "marker";
  id: string;
  label: string;
};

export type TimelineEntry = TimelineEventItem | TimelineMarkerItem;

export type MatchTimelineProps = {
  entries: readonly TimelineEntry[];
  homeLabel: string;
  awayLabel: string;
  emptyMessage?: string;
};

/**
 * Timeline verticale casa/ospite con linea centrale (EP13-P04-quater
 * §9/§10/§12): ogni evento sta dal lato della propria squadra, il minuto
 * resta sulla linea di mezzo. I separatori di periodo (inizio, intervallo,
 * fine) attraversano tutta la larghezza.
 */
export function MatchTimeline({ entries, homeLabel, awayLabel, emptyMessage }: MatchTimelineProps) {
  if (entries.length === 0) {
    return (
      <p className="fa-timeline__empty" data-testid="match-timeline-empty">
        {emptyMessage ?? "Nessun evento disponibile."}
      </p>
    );
  }

  return (
    <div className="fa-timeline" data-testid="match-timeline">
      <div className="fa-timeline__header">
        <span className="fa-timeline__header-side">{homeLabel}</span>
        <span className="fa-timeline__header-side fa-timeline__header-side--away">{awayLabel}</span>
      </div>
      <ol className="fa-timeline__list">
        {entries.map((entry) =>
          entry.type === "marker" ? (
            <li key={entry.id} className="fa-timeline__marker" data-testid="timeline-marker">
              <span className="fa-timeline__marker-label">{entry.label}</span>
            </li>
          ) : (
            <li
              key={entry.id}
              className={classNames(
                "fa-timeline__row",
                entry.side === "home" ? "fa-timeline__row--home" : "fa-timeline__row--away",
              )}
              data-testid={`timeline-event-${entry.id}`}
            >
              <div className="fa-timeline__content">
                {entry.icon ? <span className="fa-timeline__icon">{entry.icon}</span> : null}
                <span className="fa-timeline__headline">{entry.headline}</span>
                {entry.detail ? <span className="fa-timeline__detail">{entry.detail}</span> : null}
              </div>
              <div className="fa-timeline__spine" aria-hidden="true">
                <span className="fa-timeline__minute">{entry.minuteLabel}</span>
              </div>
              <div className="fa-timeline__content fa-timeline__content--spacer" aria-hidden="true" />
            </li>
          ),
        )}
      </ol>
    </div>
  );
}
