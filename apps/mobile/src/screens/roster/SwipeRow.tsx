import { theme } from "@fantappero/ui/theme";
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { Animated, PanResponder, StyleSheet, Text, View } from "react-native";

const THRESHOLD = 96;
const MAX_PULL = 150;

/**
 * Riga con gesti orizzontali: da destra verso sinistra esegue `onSwipeLeft` (es. rimuovi),
 * da sinistra verso destra esegue `onSwipeRight` (es. assegna). Sotto la riga compare lo sfondo
 * colorato con l'etichetta, così il gesto si capisce mentre lo si fa. `nudge` fa «respirare»
 * la riga una volta all'apertura per far capire che si può scorrere.
 */
export function SwipeRow({
  children,
  onSwipeLeft,
  onSwipeRight,
  leftLabel = "Rimuovi",
  rightLabel = "Assegna",
  nudge,
  testID,
}: {
  children: ReactNode;
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  leftLabel?: string;
  rightLabel?: string;
  nudge?: "left" | "right";
  testID?: string;
}) {
  const x = useRef(new Animated.Value(0)).current;
  const leftRef = useRef(onSwipeLeft);
  const rightRef = useRef(onSwipeRight);
  leftRef.current = onSwipeLeft;
  rightRef.current = onSwipeRight;
  const canLeft = !!onSwipeLeft;
  const canRight = !!onSwipeRight;

  useEffect(() => {
    if (!nudge) {
      return;
    }
    const to = nudge === "left" ? -36 : 36;
    Animated.sequence([
      Animated.delay(600),
      Animated.timing(x, { toValue: to, duration: 260, useNativeDriver: true }),
      Animated.timing(x, { toValue: 0, duration: 320, useNativeDriver: true }),
    ]).start();
    // Solo all'apertura.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const responder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_event, gesture) =>
          Math.abs(gesture.dx) > 10 &&
          Math.abs(gesture.dx) > Math.abs(gesture.dy) * 2 &&
          ((gesture.dx < 0 && canLeft) || (gesture.dx > 0 && canRight)),
        onPanResponderMove: (_event, gesture) => {
          const min = canLeft ? -MAX_PULL : 0;
          const max = canRight ? MAX_PULL : 0;
          x.setValue(Math.max(min, Math.min(max, gesture.dx)));
        },
        onPanResponderRelease: (_event, gesture) => {
          Animated.spring(x, { toValue: 0, useNativeDriver: true, bounciness: 0 }).start();
          if (gesture.dx <= -THRESHOLD) {
            leftRef.current?.();
          } else if (gesture.dx >= THRESHOLD) {
            rightRef.current?.();
          }
        },
        onPanResponderTerminate: () => {
          Animated.spring(x, { toValue: 0, useNativeDriver: true, bounciness: 0 }).start();
        },
      }),
    [canLeft, canRight, x],
  );

  if (!canLeft && !canRight) {
    return <View style={styles.wrap}>{children}</View>;
  }
  const leftOpacity = x.interpolate({ inputRange: [-THRESHOLD, -12, 0], outputRange: [1, 0.6, 0], extrapolate: "clamp" });
  const rightOpacity = x.interpolate({ inputRange: [0, 12, THRESHOLD], outputRange: [0, 0.6, 1], extrapolate: "clamp" });
  return (
    <View style={styles.wrap} testID={testID}>
      {canLeft ? (
        <Animated.View style={[styles.reveal, styles.revealLeft, { opacity: leftOpacity }]} pointerEvents="none">
          <Text style={styles.revealLabel}>{leftLabel}</Text>
        </Animated.View>
      ) : null}
      {canRight ? (
        <Animated.View style={[styles.reveal, styles.revealRight, { opacity: rightOpacity }]} pointerEvents="none">
          <Text style={styles.revealLabel}>{rightLabel}</Text>
        </Animated.View>
      ) : null}
      <Animated.View style={{ transform: [{ translateX: x }] }} {...responder.panHandlers}>
        {children}
      </Animated.View>
    </View>
  );
}

/** Riga di suggerimento sopra una lista a righe scorrevoli. */
export function SwipeHint({ left, right }: { left?: string; right?: string }) {
  return (
    <View style={styles.hint}>
      {right ? <Text style={styles.hintText}>{`→ ${right}`}</Text> : null}
      {left ? <Text style={styles.hintText}>{`← ${left}`}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: theme.spacing.xs, borderRadius: theme.radius.lg, overflow: "hidden" },
  reveal: {
    ...StyleSheet.absoluteFill,
    justifyContent: "center",
    paddingHorizontal: theme.spacing.lg,
  },
  revealLeft: { alignItems: "flex-end", backgroundColor: "#E5484D" },
  revealRight: { alignItems: "flex-start", backgroundColor: "#22A06B" },
  revealLabel: { color: "#fff", fontWeight: "700" },
  hint: { flexDirection: "row", justifyContent: "space-between", gap: theme.spacing.sm, marginBottom: 6 },
  hintText: { color: theme.colors.foregroundMuted, fontSize: 12 },
});
