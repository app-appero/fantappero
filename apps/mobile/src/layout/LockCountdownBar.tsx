import { lazyStyles } from "../theme/lazyStyles";
import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import type { ComponentType } from "react";
import { StyleSheet, View } from "react-native";
import { LockCountdown } from "../components/LockCountdown";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, radius } = theme;

/**
 * Conto alla rovescia del prossimo blocco formazioni.
 * Sta sotto l'header, staccato, e resta visibile su ogni schermata autenticata.
 */
export function LockCountdownBar() {
  const { accessToken, activeLeagueId } = useAuthSession();
  const { countdown, refetch } = useLockCountdown(accessToken, activeLeagueId);

  if (!countdown) {
    return null;
  }

  return (
    <View style={styles.bar}>
      <View style={styles.pill} testID="header-lock-strip">
        <Feather name="lock" size={14} color={colors.accentSecondary} />
        <LockCountdown
          state={countdown.state}
          nextLockAt={countdown.nextLockAt}
          onExpire={refetch}
          testID="header-lock-countdown"
        />
      </View>
    </View>
  );
}

/** Sotto l'header nativo delle schermate fuori dal tab: il countdown resta in cima al contenuto. */
export function withLockCountdown<P extends object>(Screen: ComponentType<P>) {
  function ScreenWithLockCountdown(props: P) {
    return (
      <View style={styles.screen}>
        <LockCountdownBar />
        <View style={styles.screen}>
          <Screen {...props} />
        </View>
      </View>
    );
  }
  ScreenWithLockCountdown.displayName = `WithLockCountdown(${Screen.displayName ?? Screen.name ?? "Screen"})`;
  return ScreenWithLockCountdown;
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    bar: {
      alignItems: "flex-end",
      paddingHorizontal: spacing.md,
      paddingTop: spacing.lg,
      paddingBottom: spacing.sm,
      backgroundColor: colors.background,
    },
    pill: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.xs,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    screen: {
      flex: 1,
      backgroundColor: colors.background,
    },
  }),
);
