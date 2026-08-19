import { type ReactNode } from "react";
import { classNames } from "../../utils/classNames.js";
import type { NavLinkAnchorProps, NavLinkItem } from "./SidebarNav.js";

export type BottomNavProps = {
  items: readonly NavLinkItem[];
  ariaLabel?: string;
  className?: string;
  linkComponent?: (props: NavLinkAnchorProps) => ReactNode;
};

function DefaultBottomLink({ active, className, children, ...rest }: NavLinkAnchorProps) {
  return (
    <a
      className={classNames("fa-bottom-nav__link", active && "fa-bottom-nav__link--active", className)}
      aria-current={active ? "page" : undefined}
      {...rest}
    >
      {children}
    </a>
  );
}

export function BottomNav({
  items,
  ariaLabel = "Navigazione mobile",
  className,
  linkComponent: LinkComponent = DefaultBottomLink,
}: BottomNavProps) {
  const visibleItems = items.filter((item) => !item.hidden);

  return (
    <nav
      className={classNames("fa-bottom-nav", className)}
      aria-label={ariaLabel}
      data-testid="bottom-nav"
    >
      <ul className="fa-bottom-nav__list">
        {visibleItems.map((item) => (
          <li key={item.id} className="fa-bottom-nav__item">
            <LinkComponent href={item.href} active={item.active}>
              {item.icon ? (
                <span className="fa-bottom-nav__icon" aria-hidden="true">
                  {item.icon}
                </span>
              ) : null}
              <span className="fa-bottom-nav__label">{item.label}</span>
            </LinkComponent>
          </li>
        ))}
      </ul>
    </nav>
  );
}
