import { Button } from "@fantappero/ui";

/** Etichetta lunga su desktop, abbreviata su telefono (la lunga resta per lo screen reader). */
export function RosterColLabel({ full, short }: { full: string; short: string }) {
  return (
    <>
      <span className="fa-roster-col-label fa-roster-col-label--full">{full}</span>
      <span className="fa-roster-col-label fa-roster-col-label--short">{short}</span>
    </>
  );
}

/** Rimuovi / Assegna: testo su desktop, badge icona su telefono. Il testo resta nel DOM. */
export function RosterActionButton({
  action,
  disabled,
  testId,
  label,
  onClick,
}: {
  action: "assign" | "release";
  disabled?: boolean;
  testId: string;
  label: string;
  onClick: () => void;
}) {
  const release = action === "release";
  return (
    <Button
      type="button"
      variant="secondary"
      className={`fa-roster-action fa-roster-action--${action}`}
      disabled={disabled}
      data-testid={testId}
      aria-label={label}
      onClick={onClick}
    >
      <span className="fa-roster-action__label">{release ? "Rimuovi" : "Assegna"}</span>
      <span className="fa-roster-action__icon" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          {release ? (
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          ) : (
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          )}
        </svg>
      </span>
    </Button>
  );
}
