import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { BrandLogo } from "../components/BrandLogo";
import { LeagueSelector } from "../components/LeagueSelector";

const { colors, spacing, typography, radius } = theme;

export type AppHeaderProps = {
  surface?: "app" | "admin";
  userDisplayName: string;
  showLeagueSelector?: boolean;
  leagues?: readonly { value: string; label: string }[];
  activeLeagueId?: string | null;
  onLeagueChange?: (leagueId: string) => void;
  onBrandPress?: () => void;
  onAdminPress?: () => void;
  onBackToAppPress?: () => void;
  onLeagueAdminPress?: () => void;
  showAdminLink?: boolean;
  showLeagueAdminLink?: boolean;
  showDevSettings?: boolean;
  onDevSettingsPress?: () => void;
};

export function AppHeader({
  surface = "app",
  userDisplayName,
  showLeagueSelector = false,
  leagues = [],
  activeLeagueId,
  onLeagueChange,
  onBrandPress,
  onAdminPress,
  onBackToAppPress,
  onLeagueAdminPress,
  showAdminLink = false,
  showLeagueAdminLink = false,
  showDevSettings = false,
  onDevSettingsPress,
}: AppHeaderProps) {
  const isAdmin = surface === "admin";

  return (
    <View
      style={[styles.header, isAdmin && styles.headerAdmin]}
      accessibilityRole="header"
      testID={isAdmin ? "admin-header" : "app-header"}
    >
      <View style={styles.topRow}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isAdmin ? "FantApperò operazioni" : "FantApperò, home"}
          onPress={onBrandPress}
          style={styles.brandButton}
        >
          {isAdmin ? (
            <View style={styles.adminBrand}>
              <BrandLogo variant="mark" size="sm" />
              <Text style={styles.brandAdmin}>Operazioni</Text>
            </View>
          ) : (
            <BrandLogo variant="full" size="sm" />
          )}
        </Pressable>
        <View style={styles.actions}>
          {showDevSettings ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Impostazioni demo"
              onPress={onDevSettingsPress}
              style={styles.linkButton}
              testID="dev-settings-button"
            >
              <Text style={styles.linkText}>Demo</Text>
            </Pressable>
          ) : null}
          {showAdminLink ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Pannello globale"
              onPress={onAdminPress}
              style={styles.linkButton}
              testID="admin-panel-link"
            >
              <Text style={styles.linkText}>Pannello</Text>
            </Pressable>
          ) : null}
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
          {showLeagueAdminLink ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Admin lega"
              onPress={onLeagueAdminPress}
              style={styles.linkButton}
              testID="league-admin-link"
            >
              <Text style={styles.linkText}>Admin lega</Text>
            </Pressable>
          ) : null}
          <View
            style={[styles.userChip, isAdmin && styles.userChipAdmin]}
            accessibilityRole="text"
            accessibilityLabel={`Utente ${userDisplayName}`}
            testID={isAdmin ? "admin-user-display" : "user-display"}
          >
            <Text style={styles.userChipText}>{userDisplayName}</Text>
          </View>
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
    paddingHorizontal: spacing.lg,
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
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  brandButton: {
    flexShrink: 1,
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
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.xs,
  },
  linkButton: {
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xs,
  },
  linkText: {
    color: colors.accent,
    fontSize: typography.fontSize.xs,
  },
  userChip: {
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
