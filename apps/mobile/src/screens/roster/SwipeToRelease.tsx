import { theme } from "@fantappero/ui/theme";
import { useMemo, useRef, type ReactNode } from "react";
import { Alert, Animated, PanResponder, StyleSheet, Text, View } from "react-native";

const THRESHOLD = 96;

/**
 * Riga che si elimina scorrendola da destra verso sinistra. Oltre la soglia chiede conferma
 * (un gesto accidentale non deve svincolare un calciatore) e poi chiama `onRelease`.
 */
export function SwipeToRelease({
  children,
  enabled,
  label,
  confirmTitle,
  onRelease,
  testID,
}: {
  children: ReactNode;
  enabled: boolean;
  label: string;
  confirmTitle: string;
  onRelease: () => void;
  testID?: string;
}) {
  const x = useRef(new Animated.Value(0)).current;
  const onReleaseRef = useRef(onRelease);
  onReleaseRef.current = onRelease;
  const titleRef = useRef(confirmTitle);
  titleRef.current = confirmTitle;

  const responder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_event, gesture) =>
          enabled && gesture.dx < -10 && Math.abs(gesture.dx) > Math.abs(gesture.dy) * 2,
        onPanResponderMove: (_event, gesture) => {
          x.setValue(Math.min(0, Math.max(-160, gesture.dx)));
        },
        onPanResponderRelease: (_event, gesture) => {
          Animated.spring(x, { toValue: 0, useNativeDriver: true, bounciness: 0 }).start();
          if (gesture.dx <= -THRESHOLD) {
            Alert.alert(titleRef.current, "Il calciatore tornerà libero nel listone.", [
              { text: "Annulla", style: "cancel" },
              { text: "Rimuovi", style: "destructive", onPress: () => onReleaseRef.current() },
            ]);
          }
        },
        onPanResponderTerminate: () => {
          Animated.spring(x, { toValue: 0, useNativeDriver: true, bounciness: 0 }).start();
        },
      }),
    [enabled, x],
  );

  if (!enabled) {
    return <View style={styles.wrap}>{children}</View>;
  }
  const revealOpacity = x.interpolate({ inputRange: [-THRESHOLD, -20, 0], outputRange: [1, 0.5, 0], extrapolate: "clamp" });
  return (
    <View style={styles.wrap} testID={testID}>
      <Animated.View style={[styles.reveal, { opacity: revealOpacity }]} pointerEvents="none">
        <Text style={styles.revealLabel}>{label}</Text>
      </Animated.View>
      <Animated.View style={{ transform: [{ translateX: x }] }} {...responder.panHandlers}>
        {children}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: theme.spacing.xs, borderRadius: theme.radius.lg, overflow: "hidden" },
  reveal: {
    ...StyleSheet.absoluteFill,
    alignItems: "flex-end",
    justifyContent: "center",
    paddingRight: theme.spacing.lg,
    backgroundColor: "#E5484D",
  },
  revealLabel: { color: "#fff", fontWeight: "700" },
});
