import { useNavigation, type NavigationProp } from "@react-navigation/core";
import {
  FAQ_HELP_ALL_LABEL,
  FAQ_HELP_CLOSE_LABEL,
  faqHelpItem,
  type FaqHelpId,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { RootStackParamList } from "../navigation/types";
import { lazyStyles } from "../theme/lazyStyles";
import {
  FAQ_HELP_GLYPH_SIZE,
  FAQ_HELP_LINK_HINT,
  FAQ_HELP_TOUCH_SIZE,
  faqHelpButtonAccessibility,
  faqHelpLinkTarget,
} from "./faqHelpA11y";

const { colors, spacing, typography, radius } = theme;

export type FaqHelpButtonProps = {
  /** La domanda da aprire: uno degli id di `FAQ_HELP`. */
  faqId: FaqHelpId;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

/**
 * Il piccolo «?» accanto a una scritta (1.4, canvas approvato da Rosario il 22/11): un tocco
 * apre dal basso la risposta della domanda frequente, con «Tutte le domande frequenti» (la
 * schermata con quella risposta aperta) e «Ho capito». Testo da `@fantappero/contracts`,
 * lo stesso del sito. Il cerchio è di 22px, l'area di tocco di 44px; il foglio non ha altezze
 * fisse e regge il testo grande.
 */
export function FaqHelpButton({ faqId, style, testID }: FaqHelpButtonProps) {
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const item = faqHelpItem(faqId);
  const a11y = faqHelpButtonAccessibility(item);
  const baseTestID = testID ?? `faq-help-${faqId}`;
  const close = () => setOpen(false);
  const openAll = () => {
    const target = faqHelpLinkTarget(item);
    setOpen(false);
    navigation.navigate(target.screen, target.params);
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={a11y.label}
        accessibilityHint={a11y.hint}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(true)}
        hitSlop={4}
        style={({ pressed }) => [styles.touch, style, pressed ? styles.pressed : null]}
        testID={baseTestID}
      >
        <View style={styles.glyph}>
          <Text style={styles.glyphText} importantForAccessibility="no" accessibilityElementsHidden>
            ?
          </Text>
        </View>
      </Pressable>
      <Modal visible={open} transparent animationType="slide" onRequestClose={close} statusBarTranslucent>
        <View style={styles.backdrop}>
          {/* Il velo chiude il foglio; per il lettore di schermo c'è «Ho capito». */}
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={close}
            accessible={false}
            importantForAccessibility="no"
            testID={`${baseTestID}-backdrop`}
          />
          <View
            style={[styles.sheet, { paddingBottom: spacing.lg + insets.bottom }]}
            accessibilityViewIsModal
            testID={`${baseTestID}-sheet`}
          >
            <View style={styles.grip} />
            <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
              <Text style={styles.title} accessibilityRole="header">
                {item.question}
              </Text>
              {item.answer.map((paragraph) => (
                <Text key={paragraph} style={styles.answer}>
                  {paragraph}
                </Text>
              ))}
            </ScrollView>
            <Pressable
              accessibilityRole="link"
              accessibilityLabel={FAQ_HELP_ALL_LABEL}
              accessibilityHint={FAQ_HELP_LINK_HINT}
              onPress={openAll}
              style={({ pressed }) => [styles.link, pressed ? styles.pressed : null]}
              testID={`${baseTestID}-all`}
            >
              <Text style={styles.linkText}>{FAQ_HELP_ALL_LABEL} ›</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={close}
              style={({ pressed }) => [styles.close, pressed ? styles.pressed : null]}
              testID={`${baseTestID}-close`}
            >
              <Text style={styles.closeText}>{FAQ_HELP_CLOSE_LABEL}</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    touch: {
      minWidth: FAQ_HELP_TOUCH_SIZE,
      minHeight: FAQ_HELP_TOUCH_SIZE,
      alignItems: "center",
      justifyContent: "center",
    },
    pressed: {
      opacity: 0.7,
    },
    glyph: {
      width: FAQ_HELP_GLYPH_SIZE,
      height: FAQ_HELP_GLYPH_SIZE,
      borderRadius: FAQ_HELP_GLYPH_SIZE / 2,
      borderWidth: 1.5,
      borderColor: colors.accent,
      alignItems: "center",
      justifyContent: "center",
    },
    glyphText: {
      color: colors.accent,
      fontSize: 12,
      lineHeight: 14,
      fontWeight: "700",
      // Il cerchio è fisso: il «?» non cresce con il testo grande (resta il nome accessibile).
      includeFontPadding: false,
    },
    backdrop: {
      flex: 1,
      justifyContent: "flex-end",
      backgroundColor: "rgba(0,0,0,0.6)",
    },
    sheet: {
      maxHeight: "85%",
      gap: spacing.sm,
      paddingHorizontal: spacing.md,
      paddingTop: spacing.sm,
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    grip: {
      alignSelf: "center",
      width: 44,
      height: 5,
      borderRadius: 3,
      backgroundColor: colors.border,
    },
    scroll: {
      flexGrow: 0,
    },
    scrollContent: {
      gap: spacing.sm,
      paddingTop: spacing.xs,
    },
    title: {
      color: colors.foreground,
      fontSize: typography.fontSize.md,
      fontWeight: typography.fontWeight.semibold,
    },
    answer: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.md,
    },
    link: {
      alignSelf: "flex-start",
      minHeight: FAQ_HELP_TOUCH_SIZE,
      justifyContent: "center",
    },
    linkText: {
      color: colors.accent,
      fontSize: typography.fontSize.md,
      fontWeight: typography.fontWeight.semibold,
      textDecorationLine: "underline",
    },
    close: {
      minHeight: FAQ_HELP_TOUCH_SIZE,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      borderRadius: radius.pill,
      backgroundColor: colors.brand,
    },
    closeText: {
      color: colors.onBrand,
      fontSize: typography.fontSize.md,
      fontWeight: typography.fontWeight.semibold,
    },
  }),
);
