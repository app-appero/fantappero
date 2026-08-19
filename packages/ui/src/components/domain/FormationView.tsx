import { type HTMLAttributes } from "react";
import { Card, CardBody, CardHeader } from "../Card.js";
import { Badge, roleBadgeVariant } from "../Badge.js";
import { classNames } from "../../utils/classNames.js";

export type FormationSlot = {
  id: string;
  label: string;
  playerName?: string;
  role: string;
};

export type FormationViewProps = HTMLAttributes<HTMLElement> & {
  /** Heading for the formation block (app-supplied copy). */
  title: string;
  slots: readonly FormationSlot[];
  bench?: readonly FormationSlot[];
  benchTitle?: string;
  pitchAriaLabel?: string;
  benchAriaLabel?: string;
  /** How many ordered bench players can actually enter (EP06-04). */
  maxSubstitutions?: number;
};

export function FormationView({
  title,
  slots,
  bench = [],
  benchTitle,
  pitchAriaLabel,
  benchAriaLabel,
  maxSubstitutions = 5,
  className,
  ...rest
}: FormationViewProps) {
  return (
    <Card className={classNames("fa-formation-view", className)} data-testid="formation-view" {...rest}>
      <CardHeader title={title} />
      <CardBody>
        <div
          className="fa-formation-view__pitch"
          role="list"
          aria-label={pitchAriaLabel}
        >
          {slots.map((slot) => (
            <div key={slot.id} className="fa-formation-view__slot" role="listitem">
              <Badge variant={roleBadgeVariant(slot.role)}>{slot.role}</Badge>
              <span className="fa-formation-view__player">
                {slot.playerName ?? slot.label}
              </span>
            </div>
          ))}
        </div>
        {bench.length > 0 ? (
          <div
            className="fa-formation-view__bench"
            role="list"
            aria-label={benchAriaLabel}
          >
            {benchTitle ? <p className="fa-formation-view__bench-title">{benchTitle}</p> : null}
            <ol className="fa-formation-view__bench-list">
              {bench.map((slot, index) => (
                <li
                  key={slot.id}
                  className={classNames(
                    "fa-formation-view__bench-item",
                    index < maxSubstitutions
                      ? "fa-formation-view__bench-item--can-enter"
                      : "fa-formation-view__bench-item--overflow",
                  )}
                >
                  <span className="fa-formation-view__bench-index">{index + 1}.</span>
                  <Badge variant={roleBadgeVariant(slot.role)}>{slot.role}</Badge>
                  <span>{slot.playerName ?? slot.label}</span>
                  {index < maxSubstitutions ? (
                    <span className="fa-formation-view__bench-hint">può subentrare</span>
                  ) : (
                    <span className="fa-formation-view__bench-hint">
                      oltre i {maxSubstitutions} cambi
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
