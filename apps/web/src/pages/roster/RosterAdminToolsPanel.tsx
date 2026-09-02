import type { FantasyTeam, FantasyTeamSummary } from "@fantappero/contracts";
import { Button } from "@fantappero/ui";

export function RosterAdminToolsPanel({
  ensuring,
  randomAiBusy,
  onEnsureTeams,
  leagueTeams,
  adminOrViewedTeam,
  onAssignRandomAiRoster,
  ensureMessage,
  ensureError,
  randomAiMessage,
  randomAiError,
}: {
  ensuring: boolean;
  randomAiBusy: boolean;
  onEnsureTeams: () => void | Promise<void>;
  leagueTeams: FantasyTeamSummary[];
  adminOrViewedTeam: FantasyTeam | null | undefined;
  onAssignRandomAiRoster: () => void | Promise<void>;
  ensureMessage: string | null;
  ensureError: string | null;
  randomAiMessage: string | null;
  randomAiError: string | null;
}) {
  return (
    <div style={{ marginTop: "1rem" }} data-testid="roster-admin-tools">
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          alignItems: "center",
        }}
      >
        <Button
          type="button"
          variant="secondary"
          disabled={ensuring || randomAiBusy}
          onClick={() => void onEnsureTeams()}
        >
          {ensuring ? "Verifica in corso…" : "Assicura squadre partecipanti"}
        </Button>
        {leagueTeams.some((row) => row.userType === "ai") ? (
          <Button
            type="button"
            variant="secondary"
            data-testid="roster-admin-random-ai"
            disabled={
              ensuring ||
              randomAiBusy ||
              adminOrViewedTeam?.userType !== "ai" ||
              (adminOrViewedTeam?.filledSlots ?? 0) >= (adminOrViewedTeam?.rosterSize ?? 0)
            }
            onClick={() => void onAssignRandomAiRoster()}
          >
            {randomAiBusy ? "Assegnazione in corso…" : "Assegna rosa random (IA)"}
          </Button>
        ) : null}
      </div>
      {ensureMessage ? <p data-testid="roster-ensure-ok">{ensureMessage}</p> : null}
      {ensureError ? <p data-testid="roster-ensure-error">{ensureError}</p> : null}
      {randomAiMessage ? <p data-testid="roster-random-ai-ok">{randomAiMessage}</p> : null}
      {randomAiError ? <p data-testid="roster-random-ai-error">{randomAiError}</p> : null}
    </div>
  );
}
