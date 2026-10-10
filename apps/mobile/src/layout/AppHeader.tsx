import { lazyStyles } from "../theme/lazyStyles";
import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { BrandLogo } from "../components/BrandLogo";
import { LeagueSelector } from "../components/LeagueSelector";
import { LockCountdown } from "../components/LockCountdown";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { NavIcon } from "../navigation/NavIcons";

const { colors, spacing, typography, radius } = theme;

export type AppHeaderProps = {
  surface?: "app" | "admin";
  userDisplayName: string;
  showLeagueSelector?: boolean;
  leagues?: readonly { value: string; label: string }[];
  activeLeagueId?: string | null;
  /** Serve alla hook del conto alla rovescia lock formazione (solo surface app). */
  accessToken?: string | null;
  onLeagueChange?: (leagueId: string) => void;
  /** Crea lega / Unisciti con codice — il + dell'header apre il modale (EP13-P01). */
  onCreateLeaguePress?: () => void;
  onJoinLeaguePress?: () => void;
  onBrandPress?: () => void;
  onBackToAppPress?: () => void;
  /** Apre il profilo al posto del nome utente (solo surface app). */
  onProfilePress?: () => void;
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
  accessToken,
  onLeagueChange,
  onCreateLeaguePress,
  onJoinLeaguePress,
  onBrandPress,
  onProfilePress,
  onBackToAppPress,
  onMenuPress,
  showMenuButton = false,
  onLogoutPress,
  showLogout = false,
}: AppHeaderProps) {
  const isAdmin = surface === "admin";
  const [leagueMenuOpen, setLeagueMenuOpen] = useState(false);
  const canAddLeague = Boolean(onCreateLeaguePress || onJoinLeaguePress);
  const { countdown, refetch: refetchCountdown } = useLockCountdown(
    accessToken ?? null,
    !isAdmin && showLeagueSelector && activeLeagueId ? activeLeagueId : null,
  );

  function openLeagueAction(action: (() => void) | undefined) {
    setLeagueMenuOpen(false);
    action?.();
  }

  return (
    <View
      style={[styles.header, isAdmin ? styles.headerAdmin : styles.headerApp]}
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
          style={[styles.brandButton, !isAdmin && styles.brandButtonApp]}
          testID="app-brand-button"
        >
          {isAdmin ? (
            <View style={styles.adminBrand}>
              <BrandLogo variant="mark" size="md" />
              <Text style={styles.brandAdmin} numberOfLines={1}>
                Operazioni
              </Text>
            </View>
          ) : (
            <BrandLogo variant="mark" size="md" />
          )}
        </Pressable>

        {!isAdmin && onProfilePress ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Profilo di ${userDisplayName}`}
            onPress={onProfilePress}
            style={styles.profileButton}
            testID="header-profile-button"
          >
            <NavIcon id="profile" color={colors.foreground} size={20} />
          </Pressable>
        ) : null}

        {!isAdmin && (showLeagueSelector || canAddLeague) ? (
          <View style={styles.leagueInline}>
            {showLeagueSelector && activeLeagueId && onLeagueChange && leagues.length > 0 ? (
              <LeagueSelector
                label="Lega"
                showLabel={false}
                leagues={leagues}
                value={activeLeagueId}
                onChange={onLeagueChange}
              />
            ) : null}
            {countdown ? (
              <LockCountdown
                state={countdown.state}
                nextLockAt={countdown.nextLockAt}
                onExpire={refetchCountdown}
                testID="header-lock-countdown"
              />
            ) : null}
            {canAddLeague ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Crea o unisciti a una lega"
                onPress={() => setLeagueMenuOpen(true)}
                style={styles.addLeagueButton}
                testID="header-add-league"
              >
                <Feather name="plus" size={22} color={colors.accent} />
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {isAdmin ? (
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
        ) : null}
      </View>
      <Modal
        visible={!isAdmin && leagueMenuOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setLeagueMenuOpen(false)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setLeagueMenuOpen(false)}>
          <Pressable
            style={styles.modalCard}
            onPress={() => undefined}
            testID="header-league-menu"
          >
            <Text style={styles.modalTitle}>Lega</Text>
            <Text style={styles.modalHint}>Crea una lega nuova oppure entra con un codice invito.</Text>
            {onCreateLeaguePress ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Crea lega"
                onPress={() => openLeagueAction(onCreateLeaguePress)}
                style={styles.modalPrimary}
                testID="header-create-league-link"
              >
                <Text style={styles.modalPrimaryLabel}>Crea lega</Text>
              </Pressable>
            ) : null}
            {onJoinLeaguePress ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Unisciti con codice"
                onPress={() => openLeagueAction(onJoinLeaguePress)}
                style={styles.modalSecondary}
                testID="header-join-league-link"
              >
                <Text style={styles.modalSecondaryLabel}>Unisciti con codice</Text>
              </Pressable>
            ) : null}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Annulla"
              onPress={() => setLeagueMenuOpen(false)}
              style={styles.modalSecondary}
            >
              <Text style={styles.modalSecondaryLabel}>Annulla</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  header: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    gap: spacing.sm,
  },
  headerApp: {
    paddingVertical: spacing.xs,
  },
  headerAdmin: {
    borderBottomColor: colors.warning,
    borderBottomWidth: 2,
  },
  profileButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.backgroundSubtle,
    borderWidth: 1,
    borderColor: colors.border,
    flexShrink: 0,
  },
  leagueInline: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: spacing.xs,
    minWidth: 0,
  },
  addLeagueButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalCard: {
    width: "100%",
    maxWidth: 360,
    borderRadius: radius.lg,
    backgroundColor: colors.backgroundElevated,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  modalTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  modalHint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.xs,
  },
  modalPrimary: {
    minHeight: 44,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
  },
  modalPrimaryLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  modalSecondary: {
    minHeight: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
  },
  modalSecondaryLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
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
  brandButtonApp: {
    flexGrow: 0,
  },
  adminBrand: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flexShrink: 1,
    minWidth: 0,
  },
  brandAdmin: {
    color: colors.warning,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    flexShrink: 1,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    flexShrink: 1,
    flexGrow: 0,
    minWidth: 0,
    gap: spacing.xs,
  },
  linkButton: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
    flexShrink: 0,
  },
  linkText: {
    color: colors.accent,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  userChip: {
    flexShrink: 1,
    minWidth: 0,
    maxWidth: 112,
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
  leagueRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  leagueActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
}));
