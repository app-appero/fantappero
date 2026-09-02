import { type ReactNode } from "react";
import { NavLink, type NavLinkProps } from "../router/simpleRouter";
import type { NavLinkAnchorProps } from "@fantappero/ui";

/** Router-aware nav link for SidebarNav / BottomNav `linkComponent` slot. */
export function RouterNavLinkAdapter({
  href,
  active,
  children,
  className,
  ...rest
}: NavLinkAnchorProps) {
  const to = href ?? "/";
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "fa-sidebar-nav__link",
          (active ?? isActive) && "fa-sidebar-nav__link--active",
          className,
        ]
          .filter(Boolean)
          .join(" ")
      }
      {...(rest as Omit<NavLinkProps, "to">)}
    >
      {children as ReactNode}
    </NavLink>
  );
}

export function RouterBottomNavLink({
  href,
  active,
  children,
  className,
  ...rest
}: NavLinkAnchorProps) {
  const to = href ?? "/";
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "fa-bottom-nav__link",
          (active ?? isActive) && "fa-bottom-nav__link--active",
          className,
        ]
          .filter(Boolean)
          .join(" ")
      }
      {...(rest as Omit<NavLinkProps, "to">)}
    >
      {children as ReactNode}
    </NavLink>
  );
}
