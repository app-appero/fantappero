import { hasPermissions, type PermissionContext } from "@fantappero/contracts";
import { StatusBar } from "expo-status-bar";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui";
import { MOBILE_NAV_ITEMS, NAV_LABELS } from "./src/navigation/navConfig";
import { buildPermissionContext, DEMO_LEAGUES, DEMO_MEMBER } from "./src/session/demoSession";

const { colors, spacing, typography, radius } = theme;

function filterMobileNav(context: PermissionContext) {
  return MOBILE_NAV_ITEMS.filter((item) => hasPermissions(context, item.requiredPermissions));
}

export default function App() {
  const permissionContext = useMemo(
    () => buildPermissionContext(DEMO_MEMBER, DEMO_LEAGUES[0]?.id ?? null),
    [],
  );
  const navItems = useMemo(() => filterMobileNav(permissionContext), [permissionContext]);
  const [activeId, setActiveId] = useState(navItems[0]?.id ?? "leagues");

  const activeLabel = NAV_LABELS[activeId] ?? activeId;

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      <Text style={styles.brand}>FantApperò</Text>
      <Text style={styles.title}>{activeLabel}</Text>
      <Text style={styles.copy}>
        Navigazione mobile EPUI-03 — wireframe completi su web responsive (EPUI-04).
      </Text>
      <View style={styles.statePanel} testID="mobile-shell-active">
        <Text style={styles.stateTitle}>Sezione attiva</Text>
        <Text style={styles.stateMessage}>{activeLabel}</Text>
      </View>

      <View style={styles.bottomNav} accessibilityRole="tablist" testID="mobile-bottom-nav">
        {navItems.map((item) => {
          const selected = item.id === activeId;
          return (
            <Pressable
              key={item.id}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              onPress={() => setActiveId(item.id)}
              style={[styles.tab, selected && styles.tabActive]}
              testID={`mobile-tab-${item.id}`}
            >
              <Text style={[styles.tabLabel, selected && styles.tabLabelActive]}>
                {NAV_LABELS[item.id]}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.xl,
    paddingBottom: spacing["3xl"],
  },
  brand: {
    color: colors.foregroundMuted,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.sm,
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize["2xl"],
    fontWeight: typography.fontWeight.semibold,
    marginBottom: spacing.md,
  },
  copy: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.md,
    marginBottom: spacing.lg,
  },
  statePanel: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    backgroundColor: colors.backgroundElevated,
  },
  stateTitle: {
    color: colors.success,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    marginBottom: spacing.sm,
  },
  stateMessage: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  bottomNav: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    paddingVertical: spacing.xs,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  tabActive: {
    borderTopWidth: 2,
    borderTopColor: colors.accent,
  },
  tabLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  tabLabelActive: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
});
