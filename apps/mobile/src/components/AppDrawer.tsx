import { theme } from "@fantappero/ui/theme";
import { useEffect, useMemo, useRef } from "react";
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
import { buildMobileNavSections, type ResolvedMobileNavItem } from "../navigation/navConfig";

const { colors, spacing, typography, radius } = theme;

const DRAWER_WIDTH = 300;

export type AppDrawerProps = {
  visible: boolean;
  items: readonly ResolvedMobileNavItem[];
  userDisplayName: string;
  showAdminPanel?: boolean;
  /** Id della voce corrispondente alla schermata corrente. */
  activeItemId?: string | null;
  /** Gruppi aperti; se omesso tutti i gruppi sono aperti. */
  expandedGroupIds?: readonly string[];
  onToggleGroup?: (groupId: string) => void;
  /** Inviti pendenti da evidenziare sulla voce «Inviti» (EP13-P07). */
  pendingInviteCount?: number;
  onNotificationsPress?: () => void;
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
  activeItemId = null,
  expandedGroupIds,
  onToggleGroup,
  pendingInviteCount = 0,
  onNotificationsPress,
  onClose,
  onNavigate,
  onAdminPanelPress,
  onLogout,
}: AppDrawerProps) {
  const insets = useSafeAreaInsets();
  const sections = useMemo(() => buildMobileNavSections(items), [items]);
  const isExpanded = (groupId: string) =>
    expandedGroupIds ? expandedGroupIds.includes(groupId) : true;
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

  function renderItem(item: ResolvedMobileNavItem, nested: boolean) {
    const active = item.id === activeItemId;
    return (
      <Pressable
        key={item.id}
        accessibilityRole="button"
        accessibilityLabel={item.label}
        accessibilityState={{ selected: active }}
        onPress={() => onNavigate(item)}
        style={[styles.row, nested && styles.rowNested, active && styles.rowActive]}
        testID={`app-drawer-item-${item.id}`}
      >
        <NavIcon id={item.id} color={active ? colors.accent : colors.foregroundMuted} size={20} />
        <Text style={[styles.rowLabel, active && styles.rowLabelActive]}>{item.label}</Text>
        {item.id === "received-invites" && pendingInviteCount > 0 ? (
          <Text
            style={styles.badge}
            accessibilityLabel={`${pendingInviteCount} inviti in attesa di risposta`}
            testID="app-drawer-invite-badge"
          >
            {pendingInviteCount > 99 ? "99+" : pendingInviteCount}
          </Text>
        ) : null}
      </Pressable>
    );
  }

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
            {sections.map((section) => {
              if (section.kind === "item") {
                return renderItem(section.item, false);
              }

              const expanded = isExpanded(section.id);
              const containsActive = section.items.some((item) => item.id === activeItemId);

              return (
                <View key={section.id} style={styles.group}>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={section.label}
                    accessibilityState={{ expanded }}
                    onPress={() => onToggleGroup?.(section.id)}
                    style={styles.groupHeader}
                    testID={`app-drawer-group-${section.id}`}
                  >
                    <Text
                      style={[styles.groupLabel, containsActive && styles.groupLabelActive]}
                    >
                      {section.label}
                    </Text>
                    <Text style={styles.groupCaret}>{expanded ? "▾" : "▸"}</Text>
                  </Pressable>
                  {expanded ? (
                    <View style={styles.groupList}>
                      {section.items.map((item) => renderItem(item, true))}
                    </View>
                  ) : null}
                </View>
              );
            })}
            {onNotificationsPress ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Notifiche"
                onPress={onNotificationsPress}
                style={styles.row}
                testID="app-drawer-item-notifications"
              >
                <NavIcon id="admin-home" color={colors.foregroundMuted} size={20} />
                <Text style={styles.rowLabel}>Notifiche</Text>
              </Pressable>
            ) : null}
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
  rowNested: {
    marginLeft: spacing.md,
  },
  rowActive: {
    backgroundColor: colors.background,
  },
  rowLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    flexShrink: 1,
  },
  badge: {
    marginLeft: "auto",
    minWidth: 22,
    paddingHorizontal: 6,
    borderRadius: 999,
    backgroundColor: colors.danger,
    color: colors.accentContrast,
    fontSize: typography.fontSize.sm,
    fontWeight: "700",
    textAlign: "center",
    overflow: "hidden",
  },
  rowLabelActive: {
    color: colors.accent,
  },
  group: {
    gap: spacing.xs,
  },
  groupHeader: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
  },
  groupLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  groupLabelActive: {
    color: colors.accent,
  },
  groupCaret: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  groupList: {
    gap: spacing.xs,
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
    marginLeft: spacing.md,
    paddingLeft: spacing.xs,
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
