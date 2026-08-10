import { theme } from "@fantappero/ui/theme";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { BrandLogo } from "../components/BrandLogo";
import { LeagueSelector } from "../components/LeagueSelector";
import { NavIcon } from "../navigation/NavIcons";

const { colors, spacing, typography, radius } = theme;

export type AppHeaderProps = {
  surface?: "app" | "admin";
  userDisplayName: string;
  showLeagueSelector?: boolean;
  leagues?: readonly { value: string; label: string }[];
  activeLeagueId?: string | null;
  onLeagueChange?: (leagueId: string) => void;
  onBrandPress?: () => void;
  onBackToAppPress?: () => void;
  /** Apre il drawer laterale (solo surface app). */
  onMenuPress?: () => void;
  showMenuButton?: boolean;
  onLogoutPress?: () => void;
  showLogout?: boolean;
};

export function AppHeader({
  surface = "app",
  userDisplayName,
  showLeagueSelector = false,
  leagues = [],
  activeLeagueId,
  onLeagueChange,
  onBrandPress,
  onBackToAppPress,
  onMenuPress,
  showMenuButton = false,
  onLogoutPress,
  showLogout = false,
}: AppHeaderProps) {
  const isAdmin = surface === "admin";

  return (
    <View
      style={[styles.header, isAdmin && styles.headerAdmin]}
      accessibilityRole="header"
      testID={isAdmin ? "admin-header" : "app-header"}
    >
      <View style={styles.topRow}>
        {showMenuButton && onMenuPress ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Apri menu"
            onPress={onMenuPress}
            style={styles.menuButton}
            testID="app-menu-button"
          >
            <NavIcon id="more" color={colors.foreground} size={24} />
          </Pressable>
        ) : null}

        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isAdmin ? "FantApperò operazioni" : "FantApperò, home"}
          onPress={onBrandPress}
          style={styles.brandButton}
          testID="app-brand-button"
        >
          {isAdmin ? (
            <View style={styles.adminBrand}>
              <BrandLogo variant="mark" size="md" />
              <Text style={styles.brandAdmin}>Operazioni</Text>
            </View>
          ) : (
            <BrandLogo variant="full" size="md" />
          )}
        </Pressable>

        <View style={styles.actions}>
          {isAdmin && onBackToAppPress ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Torna all'app"
              onPress={onBackToAppPress}
              style={styles.linkButton}
            >
              <Text style={styles.linkText}>App</Text>
            </Pressable>
          ) : null}
          <View
            style={[styles.userChip, isAdmin && styles.userChipAdmin]}
            accessibilityRole="text"
            accessibilityLabel={`Utente ${userDisplayName}`}
            testID={isAdmin ? "admin-user-display" : "user-display"}
          >
            <Text style={styles.userChipText} numberOfLines={1}>
              {userDisplayName}
            </Text>
          </View>
          {showLogout && onLogoutPress ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Esci"
              onPress={onLogoutPress}
              style={styles.linkButton}
              testID="logout-button"
            >
              <Text style={styles.linkText}>Esci</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      {showLeagueSelector && activeLeagueId && onLeagueChange ? (
        <LeagueSelector
          label="Lega attiva"
          leagues={leagues}
          value={activeLeagueId}
          onChange={onLeagueChange}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    gap: spacing.sm,
  },
  headerAdmin: {
    borderBottomColor: colors.warning,
    borderBottomWidth: 2,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  menuButton: {
    minWidth: 44,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  brandButton: {
    flexGrow: 1,
    flexShrink: 1,
    minWidth: 0,
    justifyContent: "center",
  },
  adminBrand: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  brandAdmin: {
    color: colors.warning,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    flexShrink: 0,
    gap: spacing.xs,
    maxWidth: "42%",
  },
  linkButton: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  linkText: {
    color: colors.accent,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  userChip: {
    maxWidth: 96,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundSubtle,
    borderWidth: 1,
    borderColor: colors.border,
  },
  userChipAdmin: {
    borderColor: colors.warningMuted,
  },
  userChipText: {
    color: colors.foreground,
    fontSize: typography.fontSize.xs,
  },
});
