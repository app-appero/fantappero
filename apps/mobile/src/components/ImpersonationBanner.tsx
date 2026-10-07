import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

const { colors, spacing, typography, radius } = theme;

export function ImpersonationBanner({
  displayName,
  onExit,
}: {
  displayName: string;
  onExit: () => Promise<void>;
}) {
  const [working, setWorking] = useState(false);

  return (
    <View style={styles.banner} accessibilityRole="summary" testID="impersonation-banner">
      <Text style={styles.text}>
        Stai impersonando {displayName} a scopo di assistenza.
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Torna al tuo account"
        disabled={working}
        onPress={() => {
          setWorking(true);
          void onExit().finally(() => setWorking(false));
        }}
        style={[styles.button, working && styles.disabled]}
        testID="impersonation-exit"
      >
        <Text style={styles.buttonLabel}>{working ? "Rientro…" : "Torna al tuo account"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.backgroundElevated,
    borderBottomWidth: 1,
    borderBottomColor: colors.warning,
  },
  text: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  button: {
    alignSelf: "flex-start",
    minHeight: 40,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  buttonLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.sm,
  },
  disabled: {
    opacity: 0.6,
  },
});
