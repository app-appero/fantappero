import { type ReactNode } from "react";
import { classNames } from "../utils/classNames.js";

export type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
  testId?: string;
};

/** Presentational empty state — copy via props, no domain strings. */
export function EmptyState({
  title,
  description,
  icon,
  actions,
  className,
  testId,
}: EmptyStateProps) {
  return (
    <section
      className={classNames("fa-empty-state", className)}
      data-testid={testId ?? "empty-state"}
      aria-label={title}
    >
      {icon ? (
        <div className="fa-empty-state__icon" aria-hidden="true">
          {icon}
        </div>
      ) : null}
      <h2 className="fa-empty-state__title">{title}</h2>
      {description ? <p className="fa-empty-state__description">{description}</p> : null}
      {actions ? <div className="fa-empty-state__actions">{actions}</div> : null}
    </section>
  );
}
