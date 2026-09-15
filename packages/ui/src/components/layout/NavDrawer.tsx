import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
} from "react";
import { createPortal } from "react-dom";
import { classNames } from "../../utils/classNames.js";

export type NavDrawerProps = {
  open: boolean;
  onClose: () => void;
  /** Brand mark in the drawer header. */
  brand?: ReactNode;
  /** Signed-in user, shown under the header like the native drawer. */
  userDisplayName?: string;
  /** Primary navigation (typically `SidebarNav`). */
  children: ReactNode;
  /** Footer actions such as logout. */
  footer?: ReactNode;
  closeLabel?: string;
  ariaLabel?: string;
  className?: string;
};

/**
 * Left overlay drawer for mobile web, matching the native `AppDrawer`.
 * Desktop keeps the persistent sidebar; this panel is the <768px menu.
 */
export function NavDrawer({
  open,
  onClose,
  brand,
  userDisplayName,
  children,
  footer,
  closeLabel = "Chiudi",
  ariaLabel = "Menu",
  className,
}: NavDrawerProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) {
      return;
    }

    previouslyFocused.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus({ preventScroll: true });

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus({ preventScroll: true });
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const drawer = (
    <div
      className={classNames("fa-nav-drawer", className)}
      data-testid="nav-drawer"
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        className="fa-nav-drawer__backdrop"
        aria-label={closeLabel}
        onClick={onClose}
        data-testid="nav-drawer-backdrop"
      />
      <aside
        id="nav-drawer-panel"
        className="fa-nav-drawer__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="nav-drawer-panel"
      >
        <header className="fa-nav-drawer__header">
          <div className="fa-nav-drawer__brand" id={titleId}>
            {brand ?? ariaLabel}
          </div>
          <button
            ref={closeRef}
            type="button"
            className="fa-nav-drawer__close"
            onClick={onClose}
            aria-label={closeLabel}
            data-testid="nav-drawer-close"
          >
            {closeLabel}
          </button>
        </header>
        {userDisplayName ? (
          <p className="fa-nav-drawer__user" data-testid="nav-drawer-user">
            {userDisplayName}
          </p>
        ) : null}
        <div className="fa-nav-drawer__body">{children}</div>
        {footer ? <div className="fa-nav-drawer__footer">{footer}</div> : null}
      </aside>
    </div>
  );

  if (typeof document === "undefined") {
    return drawer;
  }

  return createPortal(drawer, document.body);
}
