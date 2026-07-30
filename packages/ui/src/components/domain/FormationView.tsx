import { type HTMLAttributes } from "react";
import { Card, CardBody, CardHeader } from "../Card.js";
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
};

export function FormationView({
  title,
  slots,
  bench = [],
  benchTitle,
  pitchAriaLabel,
  benchAriaLabel,
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
              <span className="fa-formation-view__role">{slot.role}</span>
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
            <ul className="fa-formation-view__bench-list">
              {bench.map((slot) => (
                <li key={slot.id}>
                  <span className="fa-formation-view__role">{slot.role}</span>{" "}
                  {slot.playerName ?? slot.label}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
