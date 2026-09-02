import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";

const { colors, spacing, typography, radius } = theme;

export type LeagueOption = {
  value: string;
  label: string;
};

export type LeagueSelectorProps = {
  label: string;
  leagues: readonly LeagueOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  testID?: string;
  /** Rendered once next to the label, e.g. a lock countdown for the active league. */
  accessory?: ReactNode;
};

/** Compact league picker for the mobile shell header. */
export function LeagueSelector({
  label,
  leagues,
  value,
  onChange,
  placeholder = "Seleziona lega",
  testID = "league-selector",
  accessory,
}: LeagueSelectorProps) {
  if (leagues.length === 0) {
    return null;
  }

  return (
    <View style={styles.wrapper} testID={testID}>
      <View style={styles.labelRow}>
        <Text style={styles.label} accessibilityRole="text">
          {label}
        </Text>
        {accessory}
      </View>
      <View style={styles.options} accessibilityRole="radiogroup" accessibilityLabel={label}>
        {leagues.map((league) => {
          const selected = league.value === value;
          return (
            <Pressable
              key={league.value}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={league.label}
              onPress={() => onChange(league.value)}
              style={[styles.chip, selected && styles.chipSelected]}
              testID={`${testID}-${league.value}`}
            >
              <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>
                {league.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    flexShrink: 1,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  label: {
    color: colors.foregroundSubtle,
    fontSize: typography.fontSize.xs,
  },
  options: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundSubtle,
  },
  chipSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.backgroundElevated,
  },
  chipLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  chipLabelSelected: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
});
