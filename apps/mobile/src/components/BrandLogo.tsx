import { lazyStyles } from "../theme/lazyStyles";
import { Image, StyleSheet, Text, View, type ViewProps } from "react-native";
import { theme } from "@fantappero/ui/theme";

const { colors, spacing, typography } = theme;

export type BrandLogoVariant = "mark" | "full";
export type BrandLogoSize = "sm" | "md" | "lg";

export type BrandLogoProps = ViewProps & {
  variant?: BrandLogoVariant;
  size?: BrandLogoSize;
};

const MARK_SIZES: Record<BrandLogoSize, number> = {
  sm: 22,
  md: 28,
  lg: 36,
};

const WORDMARK_SIZES: Record<BrandLogoSize, number> = {
  sm: typography.fontSize.md,
  md: typography.fontSize.lg,
  lg: typography.fontSize.xl,
};

/** Brand mark + wordmark for mobile shell (stessa icona dell'app sul telefono: F con pallone e accento (ò)). */
export function BrandLogo({ variant = "full", size = "md", style, testID, ...rest }: BrandLogoProps) {
  const markSize = MARK_SIZES[size];

  return (
    <View
      style={[styles.root, style]}
      accessibilityRole="image"
      accessibilityLabel="FantApperò"
      testID={testID ?? "brand-logo"}
      {...rest}
    >
      <Image
        source={require("../../assets/icon.png")}
        style={{ width: markSize, height: markSize, borderRadius: Math.round(markSize * 0.22) }}
        accessibilityIgnoresInvertColors
      />
      {variant === "full" ? (
        <Text
          style={[styles.wordmark, { fontSize: WORDMARK_SIZES[size] }]}
          numberOfLines={1}
          ellipsizeMode="tail"
        >
          FantApperò
        </Text>
      ) : null}
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  root: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flexShrink: 1,
    minWidth: 0,
  },
  wordmark: {
    color: colors.foreground,
    fontStyle: "italic",
    fontWeight: "800",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    flexShrink: 1,
  },
}));
