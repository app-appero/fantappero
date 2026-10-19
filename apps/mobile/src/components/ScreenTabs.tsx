import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

const { colors, spacing, typography, radius } = theme;

export type ScreenTabItem = {
  id: string;
  label: string;
};

/**
 * Striscia di tab in cima a una schermata, per passare tra viste correlate
 * (es. Home lega / Amministrazione, Rosa / Asta / Svincolati / Mercato) senza
 * voci di drawer separate — equivalente mobile dei tab web (EP13-P01).
 */
export function ScreenTabs({
  items,
  activeId,
  onSelect,
  testID = "screen-tabs",
}: {
  items: readonly ScreenTabItem[];
  activeId: string;
  onSelect: (id: string) => void;
  testID?: string;
}) {
  if (items.length < 2) {
    return null;
  }
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.scroll} contentContainerStyle={styles.row} testID={testID}>
      {items.map((item) => {
        const selected = item.id === activeId;
        return (
          <Pressable
            key={item.id}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => onSelect(item.id)}
            style={[styles.chip, selected && styles.chipSelected]}
            testID={`${testID}-${item.id}`}
          >
            <Text style={[styles.label, selected && styles.labelSelected]}>{item.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  scroll: { flexGrow: 0, marginBottom: spacing.md },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingRight: spacing.md,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: colors.background,
  },
  chipSelected: {
    borderColor: colors.brand,
    backgroundColor: colors.brand,
  },
  label: {
    fontSize: typography.fontSize.sm,
    color: colors.foreground,
  },
  labelSelected: {
    color: colors.onBrand,
    fontWeight: typography.fontWeight.semibold,
  },
}));
