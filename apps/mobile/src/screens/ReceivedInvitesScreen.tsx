import { theme } from "@fantappero/ui/theme";
import { useRoute, type RouteProp } from "@react-navigation/core";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { useDemoSession } from "../session/DemoSessionContext";
import { resolveReceivedInvitesState, type DirectoryDemoState } from "./directoryDemo";

const { colors, spacing, typography, radius } = theme;

const DEMO_INVITES = [
  { id: "invite-quartiere", leagueName: "Lega del Quartiere", invitedBy: "Giulia Bianchi" },
  { id: "invite-ufficio", leagueName: "Fantacalcio Ufficio", invitedBy: "Andrea Blu" },
] as const;

const NON_SUCCESS_COPY: Record<
  Exclude<DirectoryDemoState, "success">,
  { state: "loading" | "empty" | "error" | "forbidden"; title: string; message: string }
> = {
  loading: {
    state: "loading",
    title: "Caricamento inviti",
    message: "Preparazione degli inviti nominativi demo…",
  },
  empty: {
    state: "empty",
    title: "Nessun invito ricevuto",
    message: "Non hai inviti nominativi in attesa.",
  },
  error: {
    state: "error",
    title: "Inviti non disponibili",
    message: "Non è stato possibile leggere gli inviti demo.",
  },
  forbidden: {
    state: "forbidden",
    title: "Permessi insufficienti",
    message: "Questa sessione non può consultare gli inviti ricevuti.",
  },
  unavailable: {
    state: "empty",
    title: "Invito indisponibile",
    message: "L’invito selezionato non è più attivo.",
  },
  "already-invited": {
    state: "error",
    title: "Invito già gestito",
    message: "Hai già accettato o rifiutato questo invito.",
  },
  capacity: {
    state: "error",
    title: "Lega al completo",
    message: "L’invito è valido, ma la lega ha raggiunto la capienza.",
  },
};

/** Elenco locale degli inviti nominativi ricevuti; accetta/rifiuta mutano solo memoria. */
export function ReceivedInvitesScreen() {
  const { can } = useDemoSession();
  const route = useRoute<RouteProp<RootStackParamList, "ReceivedInvites">>();
  const state = resolveReceivedInvitesState(can(["league:view"]), route.params?.stato);
  const [pendingIds, setPendingIds] = useState<readonly string[]>(
    DEMO_INVITES.map((invite) => invite.id),
  );
  const [feedback, setFeedback] = useState<string | null>(null);

  if (state !== "success") {
    const copy = NON_SUCCESS_COPY[state];
    return (
      <PageContainer title="Inviti ricevuti" testID="screen-received-invites">
        <UiStatePanel
          state={copy.state}
          title={copy.title}
          message={copy.message}
          testID={`received-invites-${state}`}
        />
      </PageContainer>
    );
  }

  const pending = DEMO_INVITES.filter((invite) => pendingIds.includes(invite.id));

  return (
    <PageContainer title="Inviti ricevuti" testID="screen-received-invites">
      <Text style={styles.hint}>
        Azioni simulate nella sessione corrente. Nessuna accettazione viene inviata a un server.
      </Text>
      {feedback ? (
        <UiStatePanel
          state="success"
          title="Invito aggiornato"
          message={feedback}
          testID="received-invites-action-success"
        />
      ) : null}
      {pending.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun invito in attesa"
          message="Hai gestito tutti gli inviti nominativi demo."
          testID="received-invites-empty"
        />
      ) : (
        <View style={styles.list} testID="received-invites-list">
          {pending.map((invite) => (
            <View key={invite.id} style={styles.card}>
              <Text style={styles.name}>{invite.leagueName}</Text>
              <Text style={styles.hint}>Invito nominativo da {invite.invitedBy}</Text>
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    setPendingIds((current) => current.filter((id) => id !== invite.id));
                    setFeedback(`Hai accettato l’invito a ${invite.leagueName} (demo).`);
                  }}
                  style={styles.primaryButton}
                  testID={`received-invite-accept-${invite.id}`}
                >
                  <Text style={styles.primaryLabel}>Accetta</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    setPendingIds((current) => current.filter((id) => id !== invite.id));
                    setFeedback(`Hai rifiutato l’invito a ${invite.leagueName} (demo).`);
                  }}
                  style={styles.secondaryButton}
                  testID={`received-invite-decline-${invite.id}`}
                >
                  <Text style={styles.secondaryLabel}>Rifiuta</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </View>
      )}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  list: {
    gap: spacing.sm,
  },
  card: {
    gap: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
  },
  name: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  primaryButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
  },
  primaryLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  secondaryLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
});
