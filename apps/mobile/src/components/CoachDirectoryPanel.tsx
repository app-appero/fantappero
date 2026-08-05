import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  DEMO_COACHES,
  resolveNominalInviteOutcome,
  type DirectoryDemoState,
} from "../screens/directoryDemo";
import { UiStatePanel } from "./UiStatePanel";

const { colors, spacing, typography, radius } = theme;

const STATE_COPY: Record<
  Exclude<DirectoryDemoState, "success">,
  { state: "loading" | "empty" | "error" | "forbidden"; title: string; message: string }
> = {
  loading: {
    state: "loading",
    title: "Caricamento directory",
    message: "Preparazione dei profili demo disponibili…",
  },
  empty: {
    state: "empty",
    title: "Directory vuota",
    message: "Nessun fantallenatore ha attivato la disponibilità.",
  },
  error: {
    state: "error",
    title: "Directory non disponibile",
    message: "Impossibile leggere i dati demo della directory.",
  },
  forbidden: {
    state: "forbidden",
    title: "Permessi insufficienti",
    message: "Solo l’amministratore della lega può consultare la directory.",
  },
  unavailable: {
    state: "empty",
    title: "Fantallenatore indisponibile",
    message: "Il profilo selezionato non accetta inviti nominativi.",
  },
  "already-invited": {
    state: "error",
    title: "Già invitato",
    message: "Esiste già un invito nominativo attivo per questo profilo.",
  },
  capacity: {
    state: "error",
    title: "Capienza raggiunta",
    message: "Non puoi inviare altri inviti: tutti i posti della lega sono occupati.",
  },
};

export type CoachDirectoryPanelProps = {
  state: DirectoryDemoState;
  memberCount: number;
  capacity: number;
  testIDPrefix: string;
};

/** Directory locale riusabile: nessuna ricerca remota e azioni solo in memoria. */
export function CoachDirectoryPanel({
  state,
  memberCount,
  capacity,
  testIDPrefix,
}: CoachDirectoryPanelProps) {
  const [feedback, setFeedback] = useState<DirectoryDemoState | null>(null);
  const [invitedIds, setInvitedIds] = useState<readonly string[]>([]);

  if (state !== "success") {
    const copy = STATE_COPY[state];
    return (
      <UiStatePanel
        state={copy.state}
        title={copy.title}
        message={copy.message}
        testID={`${testIDPrefix}-${state}`}
      />
    );
  }

  const feedbackCopy = feedback && feedback !== "success" ? STATE_COPY[feedback] : null;

  return (
    <View style={styles.section} testID={`${testIDPrefix}-success`}>
      <Text style={styles.hint}>
        Profili demo con disponibilità manuale. Inviti {memberCount}/{capacity}; nessun dato viene
        inviato in rete.
      </Text>
      {feedback === "success" ? (
        <UiStatePanel
          state="success"
          title="Invito nominativo simulato"
          message="L’invito è stato aggiunto localmente alla demo."
          testID={`${testIDPrefix}-invite-success`}
        />
      ) : feedbackCopy ? (
        <UiStatePanel
          state={feedbackCopy.state}
          title={feedbackCopy.title}
          message={feedbackCopy.message}
          testID={`${testIDPrefix}-invite-${feedback}`}
        />
      ) : null}
      {DEMO_COACHES.map((coach) => {
        const locallyInvited = invitedIds.includes(coach.id) || Boolean(coach.alreadyInvited);
        const unavailable = !coach.available;
        return (
          <View key={coach.id} style={styles.card}>
            <View style={styles.identity}>
              <Text style={styles.name}>{coach.displayName}</Text>
              <Text style={styles.status}>
                {coach.userType === "ai" ? "IA" : "Manuale"} ·{" "}
                {coach.available ? "Disponibile" : "Non disponibile"}
              </Text>
            </View>
            <Pressable
              accessibilityRole="button"
              disabled={locallyInvited || unavailable}
              onPress={() => {
                const outcome = resolveNominalInviteOutcome(coach, memberCount, capacity);
                setFeedback(outcome);
                if (outcome === "success") {
                  setInvitedIds((current) => [...current, coach.id]);
                }
              }}
              style={[
                styles.button,
                (locallyInvited || unavailable) && styles.buttonDisabled,
              ]}
              testID={`${testIDPrefix}-invite-${coach.id}`}
            >
              <Text style={styles.buttonLabel}>
                {unavailable
                  ? "Indisponibile"
                  : locallyInvited
                    ? "Già invitato"
                    : "Invita"}
              </Text>
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.sm,
  },
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  card: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  identity: {
    flex: 1,
  },
  name: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  status: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginTop: spacing.xs,
  },
  button: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
  },
  buttonDisabled: {
    opacity: 0.55,
  },
  buttonLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
  },
});
