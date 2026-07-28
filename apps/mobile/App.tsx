import { StatusBar } from "expo-status-bar";
import { StyleSheet, Text, View } from "react-native";
import { SERVICES, type HealthResponse } from "@fantappero/contracts";
import { colors, spacing, typography } from "@fantappero/ui";
import { getMobileHealth } from "./src/health";

const health: HealthResponse = getMobileHealth();

export default function App() {
  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      <Text style={styles.brand}>FantApperò</Text>
      <Text style={styles.title}>Mobile scaffold</Text>
      <Text style={styles.copy}>
        Minimal health screen for monorepo bootstrap. No product features yet.
      </Text>
      <Text style={styles.label}>service</Text>
      <Text style={styles.value}>{SERVICES.mobile}</Text>
      <Text style={styles.label}>health</Text>
      <Text style={styles.health}>{health.status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.xl,
    justifyContent: "center",
  },
  brand: {
    color: colors.muted,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.sm,
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    marginBottom: spacing.md,
  },
  copy: {
    color: colors.muted,
    fontSize: typography.fontSize.md,
    marginBottom: spacing.lg,
  },
  label: {
    color: colors.muted,
    fontSize: typography.fontSize.sm,
    marginTop: spacing.sm,
  },
  value: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
  },
  health: {
    color: colors.ok,
    fontSize: typography.fontSize.md,
  },
});
