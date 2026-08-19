import { type HTMLAttributes, type ReactNode } from "react";
import { classNames } from "../../utils/classNames.js";

export type AppShellProps = HTMLAttributes<HTMLDivElement> & {
  header?: ReactNode;
  sidebar?: ReactNode;
  bottomNav?: ReactNode;
  skipLink?: ReactNode;
  children: ReactNode;
  /** app (member) or admin (global operator panel). */
  surface?: "app" | "admin";
};

export function AppShell({
  header,
  sidebar,
  bottomNav,
  skipLink,
  children,
  surface = "app",
  className,
  ...rest
}: AppShellProps) {
  return (
    <div
      className={classNames("fa-app-shell", className)}
      data-surface={surface}
      data-testid="app-shell"
      {...rest}
    >
      {skipLink}
      {header}
      <div className="fa-app-shell__body">
        {sidebar ? (
          <aside className="fa-app-shell__sidebar" data-testid="app-sidebar">
            {sidebar}
          </aside>
        ) : null}
        <main className="fa-app-shell__main" id="main-content">
          {children}
        </main>
      </div>
      {bottomNav ? (
        <div className="fa-app-shell__bottom-nav" data-testid="app-bottom-nav">
          {bottomNav}
        </div>
      ) : null}
    </div>
  );
}
