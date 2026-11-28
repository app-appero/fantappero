import { lazyStyles } from "../theme/lazyStyles";
import {
  type CalendarActionModalState,
  CALENDAR_ACTION_COPY,
  CALENDAR_CANCEL_LABEL,
  CALENDAR_CHECKING_TEXT,
  CALENDAR_ISSUES_HEADING,
  calendarBlockedNote,
  calendarForceNote,
  calendarProceedLabel,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

const { colors, spacing, typography, radius } = theme;

/**
 * Finestra di «Genera/Conferma calendario» (Rosario 22/11; app dalla 1.5, come il sito):
 * verifica le rose, poi la domanda «Vuoi generare il calendario?» oppure l'avviso con le squadre
 * non in regola e «Genera/Conferma comunque». I testi sono quelli di `@fantappero/contracts`.
 */
export function CalendarActionDialog({
  state,
  working,
  onCancel,
  onProceed,
}: {
  state: CalendarActionModalState | null;
  working: boolean;
  onCancel: () => void;
  /** `force` = c'è l'avviso sulle rose e l'amministratore ha scelto «comunque». */
  onProceed: (force: boolean) => void;
}) {
  // Non montata a finestra chiusa: niente copia rimasta sotto (vedi `ConfirmDialog`).
  if (!state) {
    return null;
  }
  const copy = CALENDAR_ACTION_COPY[state.action];
  const checking = state.phase === "checking";
  const hasIssues = !checking && state.teams.length > 0;
  const blockedNote = calendarBlockedNote(state.teams);
  return (
    <Modal transparent animationType="fade" visible onRequestClose={working ? undefined : onCancel}>
      <View style={styles.overlay}>
        <View style={styles.box} accessibilityViewIsModal testID="league-calendar-modal">
          <Text style={styles.title} accessibilityRole="header">
            {copy.title}
          </Text>
          <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent}>
            {checking ? (
              <Text style={styles.text} testID="league-calendar-modal-checking">
                {CALENDAR_CHECKING_TEXT}
              </Text>
            ) : hasIssues ? (
              <View style={styles.bodyContent} testID="league-calendar-modal-warning">
                <Text style={[styles.text, styles.strong]}>{CALENDAR_ISSUES_HEADING}</Text>
                <View style={styles.issues} testID="league-calendar-modal-issues">
                  {state.teams.map((team) => (
                    <Text key={team.teamId ?? team.teamName} style={styles.text}>
                      <Text style={styles.strong}>{team.teamName}</Text>: {team.issues.join(", ")}
                    </Text>
                  ))}
                </View>
                <Text style={styles.text}>{calendarForceNote(state.action)}</Text>
                {blockedNote ? (
                  <Text style={styles.text} testID="league-calendar-modal-blocked">
                    {blockedNote}
                  </Text>
                ) : null}
              </View>
            ) : (
              <Text style={styles.text} testID="league-calendar-modal-confirm">
                {copy.prompt}
              </Text>
            )}
          </ScrollView>
          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              disabled={working}
              onPress={onCancel}
              style={[styles.cancel, working && styles.disabled]}
              testID="league-calendar-modal-cancel"
            >
              <Text style={styles.cancelLabel}>{CALENDAR_CANCEL_LABEL}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              disabled={working || checking}
              onPress={() => onProceed(hasIssues)}
              style={[styles.primary, (working || checking) && styles.disabled]}
              testID="league-calendar-modal-proceed"
            >
              <Text style={styles.primaryLabel}>{calendarProceedLabel(state.action, hasIssues, working)}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.lg,
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  box: {
    maxHeight: "90%",
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  body: {
    flexGrow: 0,
  },
  bodyContent: {
    gap: spacing.sm,
  },
  issues: {
    gap: spacing.xs,
  },
  text: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.md,
    lineHeight: 22,
  },
  strong: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  cancel: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  cancelLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  primary: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.onBrand,
    fontWeight: typography.fontWeight.semibold,
  },
  disabled: {
    opacity: 0.5,
  },
}));
