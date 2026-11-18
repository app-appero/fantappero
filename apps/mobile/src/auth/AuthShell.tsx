import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import type { ReactNode } from "react";
import Feather from "@expo/vector-icons/Feather";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { BrandLogo } from "../components/BrandLogo";

const { colors, spacing } = theme;

/**
 * Cornice delle schermate di accesso come nei mockup: sfondo con aloni blu e viola,
 * logo in alto, contenuto a sinistra e, in basso, le azioni alternative (Google, link).
 */
export function AuthShell({
  children,
  footer,
  badge,
  onBack,
  testID,
}: {
  children: ReactNode;
  footer?: ReactNode;
  /** Etichetta a destra del logo (es. «Passo 1 di 3»). */
  badge?: ReactNode;
  /** Freccia indietro a sinistra del logo (schermate secondarie: verifica email, password). */
  onBack?: () => void;
  testID?: string;
}) {
  const insets = useSafeAreaInsets();
  return (
    <View style={styles.root} testID={testID}>
      <View pointerEvents="none" style={[styles.glow, styles.glowBlue]} />
      <View pointerEvents="none" style={[styles.glow, styles.glowViolet]} />
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView
          contentContainerStyle={[styles.content, { paddingTop: insets.top + spacing.md, paddingBottom: insets.bottom + spacing.lg }]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.header}>
            <View style={styles.headerStart}>
              {onBack ? (
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Indietro"
                  hitSlop={12}
                  onPress={onBack}
                  style={styles.back}
                  testID="auth-back"
                >
                  <Feather name="chevron-left" size={26} color={colors.foreground} />
                </Pressable>
              ) : null}
              <BrandLogo variant="full" size="md" />
            </View>
            {badge}
          </View>
          <View style={styles.body}>{children}</View>
          {footer ? <View style={styles.footer}>{footer}</View> : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

// Colori letti a ogni cambio di tema: con StyleSheet.create statico lo sfondo
// restava quello dell'avvio e i testi del tema chiaro sparivano (QA 18/11).
const styles = lazyStyles(() => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background, overflow: "hidden" },
  flex: { flex: 1 },
  glow: { position: "absolute", borderRadius: 999 },
  glowBlue: { top: -140, left: -120, width: 380, height: 380, backgroundColor: "rgba(53,96,240,0.22)" },
  glowViolet: { bottom: -160, right: -140, width: 420, height: 420, backgroundColor: "rgba(155,107,255,0.18)" },
  content: { flexGrow: 1, paddingHorizontal: spacing.lg },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg },
  headerStart: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  back: { width: 36, height: 44, alignItems: "flex-start", justifyContent: "center" },
  body: { gap: spacing.xs },
  footer: { marginTop: "auto", paddingTop: spacing.xl, gap: spacing.sm },
}));
