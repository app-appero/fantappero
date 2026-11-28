import { lazyStyles } from "../theme/lazyStyles";
import type { ConfirmCopy } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

const { colors, spacing, typography, radius } = theme;

export type ConfirmDialogProps = {
  /** Titolo, domanda e pulsanti (`@fantappero/contracts`); `null` = finestra chiusa. */
  copy: ConfirmCopy | null;
  /** Il pulsante di conferma è rosso (azioni che tolgono qualcosa). */
  destructive?: boolean;
  /** L'azione è in corso: i pulsanti sono disattivati. */
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  testID?: string;
};

/**
 * «Sei sicuro?» dell'app (1.5): una finestra vera, non `Alert.alert`, che nel browser (app
 * aperta con Expo web) non si apre e quindi lasciava le azioni senza conferma o bloccate. Uguale
 * sul telefono e nel browser; i testi arrivano da `@fantappero/contracts`, gli stessi del sito.
 * Si chiude con «Annulla», con il tasto indietro o toccando fuori.
 */
export function ConfirmDialog({
  copy,
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
  testID = "confirm-dialog",
}: ConfirmDialogProps) {
  // Non montata a finestra chiusa: niente copia rimasta sotto (react-native-web tiene viva la
  // finestra durante l'animazione di chiusura e due aperture ravvicinate se ne ritrovano due).
  if (!copy) {
    return null;
  }
  return (
    <Modal transparent animationType="fade" visible onRequestClose={onCancel}>
      <View style={styles.overlay}>
        <Pressable
          style={styles.backdrop}
          onPress={busy ? undefined : onCancel}
          accessibilityLabel={copy.cancelLabel}
          testID={`${testID}-backdrop`}
        />
        <View
          style={styles.box}
          accessibilityViewIsModal
          accessibilityLabel={copy.title}
          testID={testID}
        >
          <Text style={styles.title} accessibilityRole="header" testID={`${testID}-title`}>
            {copy.title}
          </Text>
          <Text style={styles.message} testID={`${testID}-message`}>
            {copy.message}
          </Text>
          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={onCancel}
              style={[styles.cancel, busy && styles.disabled]}
              testID={`${testID}-cancel`}
            >
              <Text style={styles.cancelLabel}>{copy.cancelLabel}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={onConfirm}
              style={[destructive ? styles.danger : styles.primary, busy && styles.disabled]}
              testID={`${testID}-confirm`}
            >
              <Text style={destructive ? styles.dangerLabel : styles.primaryLabel}>
                {copy.confirmLabel}
              </Text>
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
  backdrop: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
  },
  box: {
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
  message: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.md,
    lineHeight: 22,
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
  danger: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  dangerLabel: {
    color: colors.danger,
    fontWeight: typography.fontWeight.semibold,
  },
  disabled: {
    opacity: 0.5,
  },
}));
