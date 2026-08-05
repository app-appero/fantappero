import { ScrollView, StyleSheet, Text, View, type ViewProps } from "react-native";
import { theme } from "@fantappero/ui/theme";

const { colors, spacing, typography } = theme;

export type PageContainerProps = ViewProps & {
  title: string;
  children: React.ReactNode;
};

/** Scrollable page body with title — mobile equivalent of web PageContainer. */
export function PageContainer({ title, children, style, testID, ...rest }: PageContainerProps) {
  return (
    <ScrollView
      style={[styles.scroll, style]}
      contentContainerStyle={styles.content}
      testID={testID}
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
