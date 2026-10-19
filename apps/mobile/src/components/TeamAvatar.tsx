import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors } = theme;

export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Avatar tondo con iniziali (brand + anello viola), usato per squadre e partecipanti. */
export function TeamAvatar({ name, size = 44 }: { name: string; size?: number }) {
  return (
    <View
      style={[styles.ring, { width: size, height: size, borderRadius: size / 2 }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Text style={[styles.text, { fontSize: Math.round(size * 0.38) }]} allowFontScaling={false}>
        {initialsOf(name)}
      </Text>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  ring: {
    backgroundColor: colors.brand,
    borderWidth: 2,
    borderColor: colors.accentSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  text: {
    textAlign: "center",
    paddingHorizontal: 3,
    color: colors.onBrand,
    fontStyle: "italic",
    fontWeight: "800",
  },
}));
