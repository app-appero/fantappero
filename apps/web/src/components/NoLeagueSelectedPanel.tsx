import { UiStatePanel } from "@fantappero/ui";
import { useAuth } from "../auth/AuthContext";

export function NoLeagueSelectedPanel({
  testId,
  emptyMessage,
}: {
  testId: string;
  emptyMessage: string;
}) {
  const { leaguesError } = useAuth();
  if (leaguesError) {
    return (
      <UiStatePanel
        state="error"
        title="Impossibile caricare le tue leghe"
        message={leaguesError}
        testId={`${testId}-leagues-error`}
      />
    );
  }
  return (
    <UiStatePanel
      state="empty"
      title="Nessuna lega selezionata"
      message={emptyMessage}
      testId={testId}
    />
  );
}
