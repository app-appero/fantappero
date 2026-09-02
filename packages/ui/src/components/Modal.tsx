import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
} from "react";
import { classNames } from "../utils/classNames.js";
import { Button } from "./Button.js";

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  closeLabel?: string;
};

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  className,
  closeLabel = "Chiudi",
}: ModalProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
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
    dialogRef.current?.focus();

    return () => {
      previouslyFocused.current?.focus();
    };
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div className="fa-modal" onKeyDown={handleKeyDown}>
      <button
        type="button"
        className="fa-modal__backdrop"
        aria-label={closeLabel}
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={classNames("fa-modal__dialog", className)}
      >
        <header className="fa-modal__header">
          <h2 className="fa-modal__title" id={titleId}>
            {title}
          </h2>
          <Button
            variant="ghost"
            size="sm"
            className="fa-modal__close"
            onClick={onClose}
            aria-label={closeLabel}
          >
            ×
          </Button>
        </header>
        <div className="fa-modal__body">{children}</div>
        {footer ? <footer className="fa-modal__footer">{footer}</footer> : null}
      </div>
    </div>
  );
}
