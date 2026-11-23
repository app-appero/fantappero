import { useRoute, type RouteProp } from "@react-navigation/core";
import {
  FAQ_GROUPS,
  FAQ_INTRO,
  FAQ_TITLE,
  findFaqItem,
  toggleFaqItem,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { lazyStyles } from "../theme/lazyStyles";
import { faqItemAccessibility } from "./faqA11y";

const { colors, spacing, typography, radius } = theme;

/**
 * «Domande frequenti» (release 1.4, canvas approvato da Rosario il 22/11): stesse domande e
 * stessi gruppi del sito, testo da `@fantappero/contracts`. Si legge la domanda, un tocco
 * apre la risposta. Niente altezze fisse né righe troncate: regge il testo grande.
 */
export function FaqScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "Faq">>();
  const linkedId = findFaqItem(route.params?.domanda)?.id ?? null;
  const [openIds, setOpenIds] = useState<string[]>(() => (linkedId ? [linkedId] : []));

  useEffect(() => {
    if (linkedId) {
      setOpenIds((current) => (current.includes(linkedId) ? current : [...current, linkedId]));
    }
  }, [linkedId]);

  return (
    <PageContainer title={FAQ_TITLE} testID="screen-faq">
      <Text style={styles.intro}>{FAQ_INTRO}</Text>
      {FAQ_GROUPS.map((group) => (
        <View key={group.id} style={styles.group} testID={`faq-group-${group.id}`}>
          <Text style={styles.groupTitle} accessibilityRole="header">
            {group.title}
          </Text>
          {group.items.map((item) => {
            const expanded = openIds.includes(item.id);
            const a11y = faqItemAccessibility(item, expanded);
            return (
              <View key={item.id} style={styles.card} testID={`faq-item-${item.id}`}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={a11y.label}
                  accessibilityHint={a11y.hint}
                  accessibilityState={{ expanded }}
                  onPress={() => setOpenIds((current) => toggleFaqItem(current, item.id))}
                  style={({ pressed }) => [styles.question, pressed && styles.questionPressed]}
                  testID={`faq-toggle-${item.id}`}
                >
                  <Text style={styles.questionText}>{item.question}</Text>
                  <Text style={styles.sign} importantForAccessibility="no" accessibilityElementsHidden>
                    {expanded ? "−" : "+"}
                  </Text>
                </Pressable>
                {expanded ? (
                  <View style={styles.answer} testID={`faq-answer-${item.id}`}>
                    {item.answer.map((paragraph) => (
                      <Text key={paragraph} style={styles.answerText}>
                        {paragraph}
                      </Text>
                    ))}
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>
      ))}
    </PageContainer>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    intro: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.md,
    },
    group: {
      gap: spacing.sm,
      marginTop: spacing.sm,
    },
    groupTitle: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
      fontWeight: "700",
      letterSpacing: 0.8,
      textTransform: "uppercase",
    },
    card: {
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    question: {
      flexDirection: "row",
      alignItems: "flex-start",
      justifyContent: "space-between",
      gap: spacing.md,
      minHeight: 48,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm + 2,
    },
    questionPressed: {
      opacity: 0.7,
    },
    questionText: {
      flex: 1,
      flexShrink: 1,
      color: colors.foreground,
      fontSize: typography.fontSize.md,
      fontWeight: "600",
    },
    sign: {
      color: colors.accent,
      fontSize: typography.fontSize.lg,
      fontWeight: "700",
    },
    answer: {
      gap: spacing.sm,
      paddingHorizontal: spacing.md,
      paddingBottom: spacing.md,
    },
    answerText: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.md,
    },
  }),
);
