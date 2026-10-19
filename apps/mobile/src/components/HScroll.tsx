import type { ReactNode } from "react";
import { ScrollView, StyleSheet, type AccessibilityRole } from "react-native";
import { theme } from "@fantappero/ui/theme";

/** Riga di filtri/tab che non va mai a capo: si scorre di lato. */
export function HScroll({
  children,
  testID,
  accessibilityRole,
}: {
  children: ReactNode;
  testID?: string;
  accessibilityRole?: AccessibilityRole;
}) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      style={styles.scroll}
      contentContainerStyle={styles.content}
      testID={testID}
      accessibilityRole={accessibilityRole}
    >
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 0 },
  content: { flexDirection: "row", alignItems: "center", gap: theme.spacing.xs, paddingRight: theme.spacing.md },
});
