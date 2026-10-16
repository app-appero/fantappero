import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

const { spacing, typography, radius } = theme;

export function StatusBadge({
  label,
  color,
  textColor,
  testID,
  style,
}: {
  label: string;
  color: string;
  textColor: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[styles.badge, { backgroundColor: color }, style]} testID={testID}>
      <Text style={[styles.label, { color: textColor }]}>{label}</Text>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
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
}));
