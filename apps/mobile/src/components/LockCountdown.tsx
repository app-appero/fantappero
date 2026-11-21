import { lazyStyles } from "../theme/lazyStyles";
import {
  computeCountdown,
  formatCountdown,
  lockCountdownIdleLabel,
  type LineupLockCountdownState,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

const { colors, spacing, typography } = theme;

export type LockCountdownProps = {
  state: LineupLockCountdownState;
  nextLockAt: string | null;
  /** Stato del turno di riferimento (`roundStatus` della risposta): un turno saltato ha il suo testo. */
  roundStatus?: string | null;
  /** Injectable clock, for tests; defaults to the real clock, ticking every second. */
  now?: () => Date;
  /** Called once when the ticking countdown reaches zero, to trigger a data refetch. */
  onExpire?: () => void;
  testID?: string;
};

function defaultClock(): Date {
  return new Date();
}

/** Mobile port of `packages/ui/src/components/domain/LockCountdown.tsx` (EP-turni-automazione). */
export function LockCountdown({
  state,
  nextLockAt,
  roundStatus,
  now,
  onExpire,
  testID = "lock-countdown",
}: LockCountdownProps) {
  const clock = now ?? defaultClock;
  const active = state === "counting_down" && Boolean(nextLockAt);
  const [tick, setTick] = useState(() => clock());

  useEffect(() => {
    if (!active) {
      return;
    }
    setTick(clock());
    const interval = setInterval(() => setTick(clock()), 1_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, nextLockAt]);

  const parts = active ? computeCountdown(nextLockAt, tick) : null;

  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;
  useEffect(() => {
    if (parts?.expired) {
      onExpireRef.current?.();
    }
  }, [parts?.expired]);

  if (!active || !parts) {
    return (
      <View testID={testID} accessibilityRole="text">
        <Text style={styles.idleLabel}>{lockCountdownIdleLabel(state, roundStatus)}</Text>
      </View>
    );
  }

  return (
    <View testID={testID} style={styles.wrapper} accessibilityRole="text">
      <Text style={styles.label}>Prossimo blocco</Text>
      <Text style={styles.value}>{formatCountdown(parts)}</Text>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  wrapper: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: spacing.xs,
  },
  label: {
    color: colors.foregroundSubtle,
    fontSize: typography.fontSize.xs,
  },
  idleLabel: {
    color: colors.foregroundSubtle,
    fontSize: typography.fontSize.xs,
    fontStyle: "italic",
  },
  value: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
}));
