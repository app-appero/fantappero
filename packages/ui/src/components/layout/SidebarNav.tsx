import { type AnchorHTMLAttributes, type ReactNode } from "react";
import { classNames } from "../../utils/classNames.js";

export type NavLinkItem = {
  id: string;
  label: string;
  href: string;
  icon?: ReactNode;
  active?: boolean;
  /** When true the item is omitted from assistive nav (handled by parent filter). */
  hidden?: boolean;
};

export type SidebarNavProps = {
  items: readonly NavLinkItem[];
  ariaLabel?: string;
  className?: string;
  /** Render as anchor (default) or delegate navigation to app router. */
  linkComponent?: (props: NavLinkAnchorProps) => ReactNode;
};

export type NavLinkAnchorProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  active?: boolean;
};

function DefaultNavLink({ active, className, ...rest }: NavLinkAnchorProps) {
  return (
    <a
      className={classNames("fa-sidebar-nav__link", active && "fa-sidebar-nav__link--active", className)}
      aria-current={active ? "page" : undefined}
      {...rest}
    />
  );
}

export function SidebarNav({
  items,
  ariaLabel = "Navigazione principale",
  className,
  linkComponent: LinkComponent = DefaultNavLink,
}: SidebarNavProps) {
  const visibleItems = items.filter((item) => !item.hidden);

  return (
    <nav
      className={classNames("fa-sidebar-nav", className)}
      aria-label={ariaLabel}
      data-testid="sidebar-nav"
    >
      <ul className="fa-sidebar-nav__list">
        {visibleItems.map((item) => (
          <li key={item.id} className="fa-sidebar-nav__item">
            <LinkComponent href={item.href} active={item.active}>
              {item.icon ? (
                <span className="fa-sidebar-nav__icon" aria-hidden="true">
                  {item.icon}
                </span>
              ) : null}
              <span className="fa-sidebar-nav__label">{item.label}</span>
            </LinkComponent>
          </li>
        ))}
      </ul>
    </nav>
  );
}
