import { lazyStyles } from "../theme/lazyStyles";
import { StyleSheet, Text, View, type ViewProps } from "react-native";
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

/** Brand mark + wordmark for mobile shell ("F" in corsa con il pallone, allineato all'identità web). */
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
      <View
        style={[
          styles.mark,
          { width: markSize, height: markSize, borderRadius: Math.round(markSize * 0.28) },
        ]}
      >
        <Text
          style={[styles.markLetter, { fontSize: Math.round(markSize * 0.66) }]}
          allowFontScaling={false}
        >
          F
        </Text>
        <View
          style={[
            styles.markBall,
            {
              width: Math.round(markSize * 0.22),
              height: Math.round(markSize * 0.22),
              right: Math.round(markSize * 0.12),
              bottom: Math.round(markSize * 0.12),
            },
          ]}
        />
      </View>
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
  mark: {
    flexShrink: 0,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
  },
  markLetter: {
    color: colors.onBrand,
    fontStyle: "italic",
    fontWeight: "800",
    includeFontPadding: false,
  },
  markBall: {
    position: "absolute",
    borderRadius: 999,
    borderWidth: 1.5,
    borderColor: colors.onBrand,
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
