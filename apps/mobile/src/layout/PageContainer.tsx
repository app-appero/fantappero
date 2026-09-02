import { theme } from "@fantappero/ui/theme";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ViewProps,
} from "react-native";

const { colors, spacing, typography } = theme;

export type PageContainerProps = ViewProps & {
  title: string;
  children: React.ReactNode;
  /** Pull-to-refresh handler; se assente lo scroll non mostra il refresh. */
  onRefresh?: () => void | Promise<void>;
  refreshing?: boolean;
};

/** Scrollable page body with title — mobile equivalent of web PageContainer. */
export function PageContainer({
  title,
  children,
  style,
  testID,
  onRefresh,
  refreshing = false,
  ...rest
}: PageContainerProps) {
  return (
    <ScrollView
      style={[styles.scroll, style]}
      contentContainerStyle={styles.content}
      testID={testID}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              void onRefresh();
            }}
            tintColor={colors.accent}
            colors={[colors.accent]}
            progressBackgroundColor={colors.backgroundElevated}
          />
        ) : undefined
      }
      {...rest}
    >
      <Text style={styles.title} accessibilityRole="header">
        {title}
      </Text>
      <View style={styles.body}>{children}</View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    paddingBottom: spacing.xl,
    backgroundColor: colors.background,
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize["2xl"],
    fontWeight: typography.fontWeight.semibold,
    marginBottom: spacing.md,
  },
  body: {
    gap: spacing.md,
  },
});
