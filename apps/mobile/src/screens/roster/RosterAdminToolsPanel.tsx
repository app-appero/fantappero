import { Pressable, Text, View } from "react-native";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterAdminToolsPanel({
  ensuring,
  onEnsureTeams,
  ensureMessage,
  ensureError,
}: {
  ensuring: boolean;
  onEnsureTeams: () => void | Promise<void>;
  ensureMessage: string | null;
  ensureError: string | null;
}) {
  return (
    <View style={styles.admin} testID="roster-admin-tools">
      <Pressable
        style={[styles.button, ensuring && styles.disabled]}
        disabled={ensuring}
        onPress={() => void onEnsureTeams()}
      >
        <Text style={styles.buttonLabel}>
          {ensuring ? "Verifica in corso…" : "Assicura squadre partecipanti"}
        </Text>
      </Pressable>
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
    </View>
  );
}
