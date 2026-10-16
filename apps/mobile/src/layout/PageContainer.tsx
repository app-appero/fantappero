import { lazyStyles } from "../theme/lazyStyles";
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
  /**
   * Padding orizzontale del contenuto. Default `spacing.lg`.
   * La classifica lo abbassa per usare quasi tutta la larghezza dello schermo.
   */
  contentInsetHorizontal?: number;
};

/** Scrollable page body with title — mobile equivalent of web PageContainer. */
export function PageContainer({
  title,
  children,
  style,
  testID,
  onRefresh,
  refreshing = false,
  contentInsetHorizontal = spacing.lg,
  ...rest
}: PageContainerProps) {
  return (
    <ScrollView
      style={[styles.scroll, style]}
      contentContainerStyle={[styles.content, { paddingHorizontal: contentInsetHorizontal }]}
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

const styles = lazyStyles(() => StyleSheet.create({
  scroll: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
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
}));
