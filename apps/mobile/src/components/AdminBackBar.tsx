import { lazyStyles } from "../theme/lazyStyles";
import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ADMIN_BACK_LABEL } from "../navigation/adminScreens";

const { colors, spacing, typography, radius } = theme;

/**
 * Tasto «Indietro» in cima a ogni schermata del pannello operatore (1.5): prima c'era solo il
 * menù in alto e il tasto indietro del telefono. Sta sopra il contenuto che scorre, quindi si
 * vede sempre.
 */
export function AdminBackBar({ onPress }: { onPress: () => void }) {
  return (
    <View style={styles.bar}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={ADMIN_BACK_LABEL}
        onPress={onPress}
        style={styles.button}
        hitSlop={8}
        testID="admin-back"
      >
        <Feather name="chevron-left" size={22} color={colors.foreground} />
        <Text style={styles.label}>{ADMIN_BACK_LABEL}</Text>
      </Pressable>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  bar: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
    backgroundColor: colors.background,
    alignItems: "flex-start",
  },
  button: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingLeft: spacing.sm,
    paddingRight: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    backgroundColor: colors.backgroundElevated,
  },
  label: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
}));
