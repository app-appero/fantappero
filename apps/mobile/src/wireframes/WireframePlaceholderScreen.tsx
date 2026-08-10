import { getWireframeScreen, type WireframeScreenId } from "@fantappero/contracts";
import { useNavigation } from "@react-navigation/core";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useWireframeState, wireframeStateParam } from "./useWireframeState";
import type { WireframeUiState } from "@fantappero/contracts";
import { WIREFRAME_STATES } from "@fantappero/contracts";

const { colors, spacing, typography, radius } = theme;

export type WireframePlaceholderScreenProps = {
  screenId: WireframeScreenId;
  showStatePicker?: boolean;
};

function renderWireframeBody(
  screenId: WireframeScreenId,
  state: WireframeUiState,
): React.ReactNode {
  const screen = getWireframeScreen(screenId);
  const testID = `wireframe-${screen.id}-${state}`;

  if (state === "loading") {
    return (
      <UiStatePanel
        state="loading"
        title={screen.loading.title}
        message={screen.loading.message}
        testID={`${testID}-panel`}
      />
    );
  }

  if (state === "empty") {
    return (
      <View testID={testID}>
        <UiStatePanel
          state="empty"
          title={screen.empty.title}
          message={screen.empty.description}
          testID={`${testID}-panel`}
        />
        {screen.empty.ctaLabel ? (
          <Pressable style={styles.cta} accessibilityRole="button">
            <Text style={styles.ctaLabel}>{screen.empty.ctaLabel}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  if (state === "error") {
    return (
      <View testID={testID}>
        <UiStatePanel
          state="error"
          title={screen.error.title}
          message={screen.error.message}
          testID={`${testID}-panel`}
        />
        {screen.error.retryLabel ? (
          <Pressable style={styles.ctaSecondary} accessibilityRole="button">
            <Text style={styles.ctaSecondaryLabel}>{screen.error.retryLabel}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  if (state === "forbidden") {
    return (
      <UiStatePanel
        state="forbidden"
        title={screen.forbidden.title}
        message={screen.forbidden.message}
        testID={testID}
      />
    );
  }

  return (
    <View testID={testID}>
      <UiStatePanel
        state="success"
        title={screen.title}
        message={`Wireframe ${screen.primaryCta} — contenuto reale in arrivo con le card M1–M4.`}
        testID={`${testID}-panel`}
      />
      <Text style={styles.meta}>Priorità: {screen.priorityInfo.join(" · ")}</Text>
    </View>
  );
}

/** Placeholder screen driven by shared wireframe catalog copy (EPUI-04/06). */
export function WireframePlaceholderScreen({
  screenId,
  showStatePicker = __DEV__,
}: WireframePlaceholderScreenProps) {
  const screen = getWireframeScreen(screenId);
  const state = useWireframeState();
  const navigation = useNavigation();

  return (
    <PageContainer title={screen.title} testID={`screen-${screenId}`}>
      {renderWireframeBody(screenId, state)}
      {showStatePicker ? (
        <View style={styles.statePicker} accessibilityRole="tablist" accessibilityLabel="Stato UI demo">
          <Text style={styles.statePickerLabel}>Stato UI (dev)</Text>
          <View style={styles.statePickerRow}>
            {WIREFRAME_STATES.map((option) => {
              const selected = option === state;
              return (
                <Pressable
                  key={option}
                  accessibilityRole="tab"
                  accessibilityState={{ selected }}
                  accessibilityLabel={`Stato ${option}`}
                  onPress={() =>
                    navigation.setParams(wireframeStateParam(option) as never)
                  }
                  style={[styles.stateChip, selected && styles.stateChipSelected]}
                  testID={`state-toggle-${option}`}
                >
                  <Text style={[styles.stateChipLabel, selected && styles.stateChipLabelSelected]}>
                    {option}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  cta: {
    marginTop: spacing.md,
    alignSelf: "flex-start",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
  },
  ctaLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.sm,
  },
  ctaSecondary: {
    marginTop: spacing.md,
    alignSelf: "flex-start",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  ctaSecondaryLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  meta: {
    marginTop: spacing.md,
    color: colors.foregroundSubtle,
    fontSize: typography.fontSize.xs,
  },
  statePicker: {
    marginTop: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.sm,
  },
  statePickerLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  statePickerRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  stateChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stateChipSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.backgroundElevated,
  },
  stateChipLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    textTransform: "capitalize",
  },
  stateChipLabelSelected: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
});
