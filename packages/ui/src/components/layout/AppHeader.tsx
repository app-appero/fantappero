import { type HTMLAttributes, type ReactNode } from "react";
import { classNames } from "../../utils/classNames.js";

export type AppHeaderProps = HTMLAttributes<HTMLElement> & {
  /** Hamburger / menu trigger, shown on mobile web like the native app. */
  menuSlot?: ReactNode;
  brand?: ReactNode;
  /** League selector or context switcher slot. */
  contextSlot?: ReactNode;
  /** User menu, notifications, etc. */
  actionsSlot?: ReactNode;
  /** When true, applies admin/global operator visual treatment. */
  variant?: "app" | "admin";
};

export function AppHeader({
  menuSlot,
  brand,
  contextSlot,
  actionsSlot,
  variant = "app",
  className,
  children,
  ...rest
}: AppHeaderProps) {
  return (
    <header
      className={classNames(
        "fa-app-header",
        variant === "admin" && "fa-app-header--admin",
        className,
      )}
      data-testid="app-header"
      {...rest}
    >
      {menuSlot ? <div className="fa-app-header__menu">{menuSlot}</div> : null}
      <div className="fa-app-header__brand">{brand}</div>
      {contextSlot ? <div className="fa-app-header__context">{contextSlot}</div> : null}
      {actionsSlot ? <div className="fa-app-header__actions">{actionsSlot}</div> : null}
      {children}
    </header>
  );
}
