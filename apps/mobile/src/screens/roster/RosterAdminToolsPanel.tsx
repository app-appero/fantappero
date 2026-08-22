import { Pressable, Text, View } from "react-native";
import type { FantasyTeam, FantasyTeamSummary } from "@fantappero/contracts";
import { rosterStyles as styles } from "./rosterStyles";

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
  const canAssignRandomAi =
    !ensuring &&
    !randomAiBusy &&
    adminOrViewedTeam?.userType === "ai" &&
    (adminOrViewedTeam?.filledSlots ?? 0) < (adminOrViewedTeam?.rosterSize ?? 0);

  return (
    <View style={styles.admin} testID="roster-admin-tools">
      <Pressable
        style={[styles.button, (ensuring || randomAiBusy) && styles.disabled]}
        disabled={ensuring || randomAiBusy}
        onPress={() => void onEnsureTeams()}
      >
        <Text style={styles.buttonLabel}>
          {ensuring ? "Verifica in corso…" : "Assicura squadre partecipanti"}
        </Text>
      </Pressable>
      {leagueTeams.some((row) => row.userType === "ai") ? (
        <Pressable
          style={[styles.button, !canAssignRandomAi && styles.disabled]}
          disabled={!canAssignRandomAi}
          onPress={() => void onAssignRandomAiRoster()}
          testID="roster-admin-random-ai"
        >
          <Text style={styles.buttonLabel}>
            {randomAiBusy ? "Assegnazione in corso…" : "Assegna rosa random (IA)"}
          </Text>
        </Pressable>
      ) : null}
      {ensureMessage ? (
        <Text style={styles.ok} testID="roster-ensure-ok">
          {ensureMessage}
        </Text>
      ) : null}
      {ensureError ? (
        <Text style={styles.error} testID="roster-ensure-error">
          {ensureError}
        </Text>
      ) : null}
      {randomAiMessage ? (
        <Text style={styles.ok} testID="roster-random-ai-ok">
          {randomAiMessage}
        </Text>
      ) : null}
      {randomAiError ? (
        <Text style={styles.error} testID="roster-random-ai-error">
          {randomAiError}
        </Text>
      ) : null}
    </View>
  );
}
