import { lazyStyles } from "../theme/lazyStyles";
import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import type { ComponentType } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useMovesDock } from "./movesDock";
import { LockCountdown } from "../components/LockCountdown";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, radius, typography } = theme;

/**
 * Conto alla rovescia del prossimo blocco formazioni.
 * Sta sotto l'header, staccato, e resta visibile su ogni schermata autenticata.
 */
export function LockCountdownBar() {
  const { accessToken, activeLeagueId } = useAuthSession();
  const { countdown, refetch } = useLockCountdown(accessToken, activeLeagueId);
  const dock = useMovesDock();

  if (!countdown) {
    return null;
  }

  // Formazione scorsa oltre la riga delle mosse: il countdown va a sinistra e le mosse restano a destra.
  if (dock) {
    return (
      <View style={styles.dockBar} pointerEvents="box-none">
        <View style={styles.dockPill} testID="header-lock-strip">
          <Feather name="lock" size={14} color={colors.accentSecondary} />
          <View style={styles.dockCountdown}>
            <LockCountdown
              state={countdown.state}
              nextLockAt={countdown.nextLockAt}
              onExpire={refetch}
              testID="header-lock-countdown"
            />
          </View>
          <View style={styles.dockMoves} testID="header-moves-dock">
            <View style={styles.dockChip}>
              <Text style={styles.dockChipText}>
                Mosse {dock.used}/{dock.max}
              </Text>
            </View>
            {dock.draft != null ? (
              <View style={[styles.dockChip, styles.dockChipDraft]}>
                <Text style={styles.dockChipText}>→ {dock.draft}/{dock.max}</Text>
              </View>
            ) : null}
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.bar} pointerEvents="box-none">
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
      alignSelf: "center",
      zIndex: 2,
      marginTop: spacing.sm,
      marginBottom: spacing.xs,
      backgroundColor: "transparent",
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
    dockBar: {
      alignSelf: "stretch",
      zIndex: 2,
      marginTop: spacing.sm,
      marginBottom: spacing.xs,
      paddingHorizontal: spacing.md,
    },
    dockPill: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.xs,
      paddingLeft: spacing.sm,
      paddingRight: 6,
      paddingVertical: 4,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    dockCountdown: { flexShrink: 1 },
    dockMoves: { flexDirection: "row", gap: 6, marginLeft: "auto", alignItems: "center" },
    dockChip: {
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.brand,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
    },
    dockChipDraft: { backgroundColor: colors.brand },
    dockChipText: { color: colors.foreground, fontSize: typography.fontSize.sm, fontWeight: "700" },
    screen: {
      flex: 1,
      backgroundColor: colors.background,
    },
  }),
);
