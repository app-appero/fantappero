import type { WireframeUiState } from "@fantappero/contracts";
import { StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";

const { colors, spacing, typography, radius } = theme;

export type UiStatePanelProps = {
  state: WireframeUiState;
  title: string;
  message: string;
  testID?: string;
};

const stateAccent: Record<WireframeUiState, string> = {
  loading: colors.accent,
  empty: colors.foregroundMuted,
  error: colors.danger,
  success: colors.success,
  forbidden: colors.warning,
};

/** Presentational panel for standard UI states on React Native (EPUI-06). */
export function UiStatePanel({ state, title, message, testID }: UiStatePanelProps) {
  return (
    <View
      style={[styles.panel, { borderLeftColor: stateAccent[state] }]}
      accessibilityRole="summary"
      accessibilityLabel={`${title}. ${message}`}
      accessibilityLiveRegion={state === "loading" ? "polite" : undefined}
      accessibilityState={{ busy: state === "loading" }}
      testID={testID ?? `ui-state-${state}`}
    >
      <Text style={[styles.title, { color: stateAccent[state] }]} accessibilityRole="header">
        {title}
      </Text>
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderRadius: radius.lg,
    backgroundColor: colors.backgroundElevated,
  },
  title: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    marginBottom: spacing.sm,
  },
  message: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    lineHeight: typography.fontSize.sm * typography.lineHeight.normal,
  },
});
