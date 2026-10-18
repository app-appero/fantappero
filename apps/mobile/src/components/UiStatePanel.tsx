import { lazyStyles } from "../theme/lazyStyles";
import type { WireframeUiState } from "@fantappero/contracts";
import { StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { liveStringMap } from "../theme/liveColors";

const { colors, spacing, typography, radius } = theme;

export type UiStatePanelProps = {
  state: WireframeUiState;
  title: string;
  message: string;
  testID?: string;
};

const stateAccent = liveStringMap<WireframeUiState>(() => ({
  loading: colors.accent,
  empty: colors.foregroundMuted,
  error: colors.danger,
  success: colors.success,
  forbidden: colors.warning,
}));

/** Presentational panel for standard UI states on React Native (EPUI-06). */
export function UiStatePanel({ state, title, message, testID }: UiStatePanelProps) {
  return (
    <View
      style={[styles.panel, state === "empty" && styles.panelEmpty, state !== "empty" && { borderColor: stateAccent[state] }]}
      accessibilityRole="summary"
      accessibilityLabel={`${title}. ${message}`}
      accessibilityLiveRegion={state === "loading" ? "polite" : undefined}
      accessibilityState={{ busy: state === "loading" }}
      testID={testID ?? `ui-state-${state}`}
    >
      <Text style={[styles.title, { color: state === "empty" ? colors.foreground : stateAccent[state] }, state === "empty" && styles.centered]} accessibilityRole="header">
        {title}
      </Text>
      <Text style={[styles.message, state === "empty" && styles.centered]}>{message}</Text>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  panel: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl,
    backgroundColor: colors.backgroundElevated,
  },
  panelEmpty: {
    borderStyle: "dashed",
    borderWidth: 1.5,
    alignItems: "center",
    paddingVertical: spacing.lg,
  },
  title: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    marginBottom: spacing.sm,
  },
  centered: { textAlign: "center" },
  message: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    lineHeight: typography.fontSize.sm * typography.lineHeight.normal,
  },
}));
