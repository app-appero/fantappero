import { useNavigation } from "@react-navigation/core";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { WireframePlaceholderScreen } from "../wireframes/WireframePlaceholderScreen";

const { colors, spacing, typography, radius } = theme;

/** Auth macro-area placeholder — full page without app shell tab bar. */
export function AuthScreen() {
  const navigation = useNavigation();

  return (
    <View style={styles.root} testID="screen-auth">
      <WireframePlaceholderScreen screenId="auth" />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Continua come demo"
        onPress={() => navigation.navigate("MainTabs" as never)}
        style={styles.demoButton}
        testID="auth-demo-continue"
      >
        <Text style={styles.demoButtonLabel}>Continua come demo</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  demoButton: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
  },
  demoButtonLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
});
