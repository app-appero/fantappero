import type { FantasyTeam } from "@fantappero/contracts";
import { Button, UiStatePanel } from "@fantappero/ui";

export function RosterEmptyState({
  viewedTeam,
  onReload,
}: {
  viewedTeam: FantasyTeam;
  onReload: () => void | Promise<void>;
}) {
  return (
    <div data-testid="roster-empty">
      <UiStatePanel
        state="empty"
        title="Rosa vuota"
        message="Completa l'asta o importa i giocatori per popolare la rosa."
      />
      <p data-testid="roster-empty-summary">
        {viewedTeam.name}: 0/{viewedTeam.rosterSize} slot occupati
      </p>
      <Button type="button" variant="secondary" onClick={() => void onReload()}>
        Ricarica
      </Button>
    </div>
  );
}
