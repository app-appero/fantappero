import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { Image, StyleSheet, Text, View } from "react-native";
import { resolveAvatarUrl } from "../utils/avatar";

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
export function TeamAvatar({
  name,
  size = 44,
  avatarUrl,
}: {
  name: string;
  size?: number;
  avatarUrl?: string | null;
}) {
  const src = resolveAvatarUrl(avatarUrl ?? null);
  return (
    <View
      style={[styles.ring, { width: size, height: size, borderRadius: size / 2 }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {src ? (
        <Image source={{ uri: src }} style={styles.image} />
      ) : (
        <Text style={[styles.text, { fontSize: Math.round(size * 0.38) }]} allowFontScaling={false}>
          {initialsOf(name)}
        </Text>
      )}
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
  image: {
    width: "100%",
    height: "100%",
    borderRadius: 999,
  },
}));
