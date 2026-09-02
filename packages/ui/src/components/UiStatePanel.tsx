export type UiState = "loading" | "empty" | "error" | "success" | "forbidden";

export type UiStatePanelProps = {
  state: UiState;
  title: string;
  message: string;
  /** Optional test id for automated UI flows. */
  testId?: string;
};

/** Presentational panel for standard UI states (no business logic). */
export function UiStatePanel({ state, title, message, testId }: UiStatePanelProps) {
  return (
    <section
      className={`fa-state-panel fa-state-panel--${state}`}
      data-ui-state={state}
      data-testid={testId ?? `ui-state-${state}`}
      aria-live={state === "loading" ? "polite" : undefined}
      aria-busy={state === "loading" ? true : undefined}
    >
      <h2 className="fa-state-panel__title">{title}</h2>
      <p className="fa-state-panel__message">{message}</p>
    </section>
  );
}
