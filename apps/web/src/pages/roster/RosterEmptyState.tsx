import { UiStatePanel } from "@fantappero/ui";

export function RosterEmptyState() {
  return (
    <div data-testid="roster-empty">
      <UiStatePanel
        state="empty"
        title="Rosa vuota"
        message="Completa l'asta o importa i giocatori per popolare la rosa."
      />
    </div>
  );
}
