import { theme } from "@fantappero/ui/theme";
import { useEffect, useRef } from "react";
import {
  Animated,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { BrandLogo } from "./BrandLogo";
import { NavIcon } from "../navigation/NavIcons";
import type { ResolvedMobileNavItem } from "../navigation/navConfig";

const { colors, spacing, typography, radius } = theme;

const DRAWER_WIDTH = 300;

export type AppDrawerProps = {
  visible: boolean;
  items: readonly ResolvedMobileNavItem[];
  userDisplayName: string;
  showAdminPanel?: boolean;
  onClose: () => void;
  onNavigate: (item: ResolvedMobileNavItem) => void;
  onAdminPanelPress?: () => void;
  onLogout: () => void;
};

/** Drawer laterale scorrevole: catalogo navigazione allineato al web + Esci. */
export function AppDrawer({
  visible,
  items,
  userDisplayName,
  showAdminPanel = false,
  onClose,
  onNavigate,
  onAdminPanelPress,
  onLogout,
}: AppDrawerProps) {
  const insets = useSafeAreaInsets();
  const slide = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const fade = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(slide, {
          toValue: 0,
          duration: 220,
          useNativeDriver: true,
        }),
        Animated.timing(fade, {
          toValue: 1,
          duration: 220,
          useNativeDriver: true,
        }),
      ]).start();
      return;
    }
    Animated.parallel([
      Animated.timing(slide, {
        toValue: -DRAWER_WIDTH,
        duration: 180,
        useNativeDriver: true,
      }),
      Animated.timing(fade, {
        toValue: 0,
        duration: 180,
        useNativeDriver: true,
      }),
    ]).start();
  }, [fade, slide, visible]);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={styles.root} testID="app-drawer">
        <Animated.View style={[styles.backdrop, { opacity: fade }]}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Chiudi menu"
            onPress={onClose}
            style={StyleSheet.absoluteFill}
            testID="app-drawer-backdrop"
          />
        </Animated.View>
        <Animated.View
          style={[
            styles.panel,
            {
              paddingTop: insets.top + spacing.sm,
              paddingBottom: insets.bottom + spacing.md,
              transform: [{ translateX: slide }],
            },
          ]}
          testID="app-drawer-panel"
        >
          <View style={styles.header}>
            <BrandLogo variant="full" size="sm" />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Chiudi menu"
              onPress={onClose}
              style={styles.closeBtn}
              testID="app-drawer-close"
            >
              <Text style={styles.closeLabel}>Chiudi</Text>
            </Pressable>
          </View>
          <Text style={styles.user} testID="app-drawer-user">
            {userDisplayName}
          </Text>

          <ScrollView style={styles.scroll} contentContainerStyle={styles.list}>
            {items.map((item) => (
              <Pressable
                key={item.id}
                accessibilityRole="button"
                accessibilityLabel={item.label}
                onPress={() => onNavigate(item)}
                style={styles.row}
                testID={`app-drawer-item-${item.id}`}
              >
                <NavIcon id={item.id} color={colors.accent} size={20} />
                <Text style={styles.rowLabel}>{item.label}</Text>
              </Pressable>
            ))}
            {showAdminPanel ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Pannello globale"
                onPress={onAdminPanelPress}
                style={styles.row}
                testID="app-drawer-item-admin-home"
              >
                <NavIcon id="admin-home" color={colors.accent} size={20} />
                <Text style={styles.rowLabel}>Pannello globale</Text>
              </Pressable>
            ) : null}
          </ScrollView>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Esci"
            onPress={onLogout}
            style={styles.logoutBtn}
            testID="app-drawer-logout"
          >
            <Text style={styles.logoutLabel}>Esci</Text>
          </Pressable>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    flexDirection: "row",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  panel: {
    width: DRAWER_WIDTH,
    maxWidth: "86%",
    backgroundColor: colors.backgroundElevated,
    borderRightWidth: 1,
    borderRightColor: colors.border,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  closeBtn: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
  },
  closeLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.sm,
  },
  user: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.xs,
  },
  scroll: {
    flex: 1,
  },
  list: {
    gap: spacing.xs,
    paddingBottom: spacing.md,
  },
  row: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
  },
  rowLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    flexShrink: 1,
  },
  logoutBtn: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  logoutLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
});
