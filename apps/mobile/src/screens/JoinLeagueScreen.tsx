import type { RouteProp } from "@react-navigation/core";
import { useRoute } from "@react-navigation/core";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput } from "react-native";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { useDemoSession } from "../session/DemoSessionContext";
import { resolveJoinInviteState } from "./inviteDemo";

const { colors, spacing, typography, radius } = theme;

export function JoinLeagueScreen() {
  const { can } = useDemoSession();
  const route = useRoute<RouteProp<RootStackParamList, "JoinLeague">>();
  const state = resolveJoinInviteState(can(["league:view"]), route.params?.stato);
  const [code, setCode] = useState(route.params?.code ?? "");
  const [message, setMessage] = useState<string | null>(null);

  if (state === "forbidden") {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non puoi accettare inviti con questa sessione."
          testID="join-league-forbidden"
        />
      </PageContainer>
    );
  }
  if (state === "loading") {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="loading"
          title="Verifica invito"
          message="Controllo validità e capienza della lega…"
          testID="join-league-loading"
        />
      </PageContainer>
    );
  }
  if (state === "error") {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="error"
          title="Ingresso non riuscito"
          message="L'invito non è valido, è scaduto o la lega è piena (demo)."
          testID="join-league-error"
        />
      </PageContainer>
    );
  }
  if (state === "success" || message) {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="success"
          title="Ingresso completato"
          message={message ?? "Ora fai parte di Lega del Quartiere (demo)."}
          testID="join-league-success"
        />
      </PageContainer>
    );
  }

  function accept() {
    if (!code.trim()) {
      setMessage(null);
      return;
    }
    setMessage("Ora fai parte di Lega del Quartiere (demo).");
  }

  return (
    <PageContainer title="Entra in una lega" testID="screen-join-league">
      <UiStatePanel
        state="empty"
        title="Inserisci il codice"
        message="Usa il codice ricevuto dall'amministratore della lega."
        testID="join-league-empty"
      />
      <Text style={styles.label}>Codice invito</Text>
      <TextInput
        value={code}
        onChangeText={setCode}
        autoCapitalize="characters"
        autoCorrect={false}
        placeholder="ABCDE-FGHIJ"
        style={styles.input}
        testID="join-league-code"
      />
      <Pressable
        accessibilityRole="button"
        onPress={accept}
        style={styles.primaryButton}
        testID="join-league-submit"
      >
        <Text style={styles.primaryLabel}>Entra nella lega</Text>
      </Pressable>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  label: {
    marginTop: spacing.md,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.backgroundElevated,
  },
  primaryButton: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
  },
  primaryLabel: {
    color: colors.background,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
});
