import {
  PRIVACY_NOTICE_INTRO,
  PRIVACY_NOTICE_SECTIONS,
  PRIVACY_NOTICE_TITLE,
  PRIVACY_NOTICE_VERSION,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";
import { PageContainer } from "../layout/PageContainer";
import { lazyStyles } from "../theme/lazyStyles";

const { colors, spacing, typography } = theme;

/** Informativa privacy del pilota: raggiungibile anche prima di accedere. */
export function PrivacyScreen() {
  return (
    <PageContainer title={PRIVACY_NOTICE_TITLE} testID="privacy-screen">
      <Text style={styles.hint} testID="privacy-version">
        Versione {PRIVACY_NOTICE_VERSION}
      </Text>
      <Text style={styles.body}>{PRIVACY_NOTICE_INTRO}</Text>
      {PRIVACY_NOTICE_SECTIONS.map((section) => (
        <View key={section.id} style={styles.section} testID={`privacy-section-${section.id}`}>
          <Text style={styles.sectionTitle}>{section.title}</Text>
          {section.paragraphs?.map((text) => (
            <Text key={text} style={styles.body}>
              {text}
            </Text>
          ))}
          {section.bullets?.map((text) => (
            <Text key={text} style={styles.body}>
              {"•  "}
              {text}
            </Text>
          ))}
        </View>
      ))}
    </PageContainer>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    hint: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm },
    body: { color: colors.foreground, fontSize: typography.fontSize.md, lineHeight: 22 },
    section: { gap: spacing.xs, marginTop: spacing.md },
    sectionTitle: {
      color: colors.foreground,
      fontSize: typography.fontSize.lg,
      fontWeight: "700",
    },
  }),
);
