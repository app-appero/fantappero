import Feather from "@expo/vector-icons/Feather";
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

/** Brand mark + wordmark for mobile shell (Feather shield + wordmark, aligned with web identity). */
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
      <View style={styles.markWrap}>
        <Feather name="shield" size={markSize} color={colors.accent} />
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

const styles = StyleSheet.create({
  root: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flexShrink: 1,
    minWidth: 0,
  },
  markWrap: {
    flexShrink: 0,
  },
  wordmark: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    flexShrink: 1,
  },
});
