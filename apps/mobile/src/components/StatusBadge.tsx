import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { spacing, typography, radius } = theme;

export function StatusBadge({
  label,
  color,
  textColor,
  testID,
}: {
  label: string;
  color: string;
  textColor: string;
  testID?: string;
}) {
  return (
    <View style={[styles.badge, { backgroundColor: color }]} testID={testID}>
      <Text style={[styles.label, { color: textColor }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  label: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
});
