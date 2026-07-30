import { type HTMLAttributes } from "react";
import { classNames } from "../../utils/classNames.js";

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

export type BreadcrumbProps = HTMLAttributes<HTMLElement> & {
  items: readonly BreadcrumbItem[];
  /** Accessible name for the nav landmark. */
  ariaLabel?: string;
};

export function Breadcrumb({
  items,
  ariaLabel = "Percorso",
  className,
  ...rest
}: BreadcrumbProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <nav className={classNames("fa-breadcrumb", className)} aria-label={ariaLabel} {...rest}>
      <ol className="fa-breadcrumb__list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="fa-breadcrumb__item">
              {item.href && !isLast ? (
                <a className="fa-breadcrumb__link" href={item.href}>
                  {item.label}
                </a>
              ) : (
                <span
                  className="fa-breadcrumb__current"
                  aria-current={isLast ? "page" : undefined}
                >
                  {item.label}
                </span>
              )}
              {!isLast ? (
                <span className="fa-breadcrumb__separator" aria-hidden="true">
                  /
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
