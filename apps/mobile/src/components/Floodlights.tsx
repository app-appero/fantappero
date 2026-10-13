import { theme } from "@fantappero/ui/theme";
import { LinearGradient } from "expo-linear-gradient";
import { StyleSheet, View } from "react-native";

const { colors } = theme;

/** Due fasci di luce calda dagli angoli alti (visibili solo sul tema scuro: sul chiaro `beam` è trasparente). */
export function Floodlights() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} accessible={false}>
      <LinearGradient
        colors={[colors.beam, "rgba(255,241,201,0)"]}
        style={[styles.beam, styles.left]}
      />
      <LinearGradient
        colors={[colors.beam, "rgba(255,241,201,0)"]}
        style={[styles.beam, styles.right]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  beam: {
    position: "absolute",
    top: -50,
    width: 170,
    height: 430,
    borderRadius: 85,
  },
  left: {
    left: -40,
    transform: [{ rotate: "-17deg" }],
  },
  right: {
    right: -40,
    transform: [{ rotate: "17deg" }],
  },
});
