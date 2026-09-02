import type { FantasyTeam } from "@fantappero/contracts";
import { Text, View } from "react-native";
import { UiStatePanel } from "../../components/UiStatePanel";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterEmptyState({ viewedTeam }: { viewedTeam: FantasyTeam }) {
  return (
    <View testID="roster-empty">
      <UiStatePanel
        state="empty"
        title="Rosa vuota"
        message="Completa l'asta o importa i giocatori per popolare la rosa."
      />
      <Text style={styles.summary} testID="roster-empty-summary">
        {viewedTeam.name}: 0/{viewedTeam.rosterSize} slot occupati
      </Text>
    </View>
  );
}
