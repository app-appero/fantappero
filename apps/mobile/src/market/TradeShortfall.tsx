import {
  REPLACEMENT_AUTO_LINEUP_NOTE,
  TRADE_SHORTFALL_CANCEL_LABEL,
  tradeAfterNoticeKey,
  type ReplacementBanner,
  type TradeAfterNotice,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { lazyStyles } from "../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

/**
 * Riquadro arancione «Dopo lo scambio avrai 34/35» (1.5): nelle conferme di chi accetta, di chi
 * propone e dell'admin che approva. Sotto, se servono, l'avviso dei crediti che non bastano e la
 * riga dei ruoli sotto quota; con i soli ruoli sotto quota il riquadro è giallo e più leggero
 * (`info`). Testi da `tradeAfterNotice` (`@fantappero/contracts`).
 */
export function TradeShortfallBox({ notice, testID }: { notice: TradeAfterNotice; testID?: string }) {
  const info = notice.tone === "info";
  const id = testID ?? "trade-shortfall-warning";
  return (
    <View
      style={[shortfallStyles.box, info && shortfallStyles.boxInfo]}
      accessibilityRole={info ? "text" : "alert"}
      testID={id}
    >
      <Text
        style={[shortfallStyles.icon, info && shortfallStyles.iconInfo]}
        accessibilityElementsHidden
        importantForAccessibility="no"
      >
        {info ? "ℹ" : "⚠"}
      </Text>
      <View style={shortfallStyles.boxText}>
        {notice.title ? <Text style={shortfallStyles.boxTitle}>{notice.title}</Text> : null}
        {notice.body ? <Text style={shortfallStyles.boxBody}>{notice.body}</Text> : null}
        {notice.creditsWarning ? (
          <Text style={[shortfallStyles.boxBody, shortfallStyles.boxStrong]} testID={`${id}-credits`}>
            {notice.creditsWarning}
          </Text>
        ) : null}
        {notice.quotaNote ? (
          <Text style={shortfallStyles.boxBody} testID={`${id}-quota`}>
            {notice.quotaNote}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

/**
 * Riquadro informativo giallo in Rosa: «Ruoli sotto quota: 9 Centrocampisti su 11. Puoi
 * completarli con uno scambio o agli svincolati.» Non blocca niente; con sostituti da scegliere
 * si vede il riquadro dei sostituti al suo posto.
 */
export function RosterQuotaNotice({ text, testID = "roster-under-quota" }: { text: string; testID?: string }) {
  return (
    <View style={[shortfallStyles.box, shortfallStyles.boxInfo]} accessibilityRole="text" testID={testID}>
      <Text
        style={[shortfallStyles.icon, shortfallStyles.iconInfo]}
        accessibilityElementsHidden
        importantForAccessibility="no"
      >
        ℹ
      </Text>
      <View style={shortfallStyles.boxText}>
        <Text style={shortfallStyles.boxBody}>{text}</Text>
      </View>
    </View>
  );
}

/** Riquadro in alto nel foglio «Scegli il sostituto» quando nessun libero è alla portata. */
export function ReplacementUnaffordableBox({ text }: { text: string }) {
  return (
    <View style={shortfallStyles.box} accessibilityRole="alert" testID="replacement-unaffordable">
      <Text style={shortfallStyles.icon} accessibilityElementsHidden importantForAccessibility="no">
        ⚠
      </Text>
      <View style={shortfallStyles.boxText}>
        <Text style={shortfallStyles.boxBody}>{text}</Text>
      </View>
    </View>
  );
}

/**
 * Riquadro «Rosa incompleta: 34/35» in Rosa e Formazione finché manca il sostituto, con il
 * pulsante che riapre la scelta. A turno in corso dice anche quando si potrà scegliere.
 */
export function RosterShortfallBanner({
  banner,
  onChoose,
  testID = "roster-shortfall-banner",
}: {
  banner: ReplacementBanner;
  onChoose: () => void;
  testID?: string;
}) {
  return (
    <View style={shortfallStyles.box} accessibilityRole="alert" testID={testID}>
      <Text style={shortfallStyles.icon} accessibilityElementsHidden importantForAccessibility="no">
        ⚠
      </Text>
      <View style={shortfallStyles.boxText}>
        <Text style={shortfallStyles.boxTitle}>{banner.title}</Text>
        <Text style={shortfallStyles.boxBody}>{banner.body}</Text>
        {banner.blockedMessage ? <Text style={shortfallStyles.boxBody}>{banner.blockedMessage}</Text> : null}
        <Pressable
          style={shortfallStyles.primary}
          onPress={onChoose}
          accessibilityRole="button"
          testID={`${testID}-choose`}
        >
          <Text style={shortfallStyles.primaryLabel}>{banner.action}</Text>
        </Pressable>
      </View>
    </View>
  );
}

/** Nota sotto «Salva formazione» (spento) finché manca il sostituto. */
export function ReplacementAutoLineupNote() {
  return (
    <Text style={shortfallStyles.note} testID="formation-replacement-note">
      {REPLACEMENT_AUTO_LINEUP_NOTE}
    </Text>
  );
}

/**
 * Conferma dal basso di uno scambio che lascia una rosa corta (o un ruolo sotto quota): riepilogo,
 * riquadri arancioni o gialli e i pulsanti «Annulla» / azione (es. «Accetta e scegli»). Si chiude
 * anche col tasto indietro.
 */
export function TradeShortfallConfirmSheet({
  visible,
  title,
  message,
  notices,
  confirmLabel,
  busy = false,
  onCancel,
  onConfirm,
  testID = "trade-shortfall-sheet",
}: {
  visible: boolean;
  title: string;
  message?: string | null;
  notices: TradeAfterNotice[];
  confirmLabel: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  testID?: string;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <Pressable style={shortfallStyles.backdrop} onPress={onCancel} accessibilityLabel={TRADE_SHORTFALL_CANCEL_LABEL}>
        <Pressable style={shortfallStyles.sheet} onPress={() => undefined} testID={testID}>
          <View style={shortfallStyles.grip} />
          <Text style={shortfallStyles.sheetTitle} accessibilityRole="header">
            {title}
          </Text>
          <ScrollView style={shortfallStyles.scroll} contentContainerStyle={shortfallStyles.scrollContent}>
            {message ? <Text style={shortfallStyles.message}>{message}</Text> : null}
            {notices.map((notice) => (
              <TradeShortfallBox key={tradeAfterNoticeKey(notice)} notice={notice} testID={`${testID}-warning`} />
            ))}
          </ScrollView>
          <View style={shortfallStyles.actions}>
            <Pressable
              style={[shortfallStyles.secondary, shortfallStyles.action]}
              onPress={onCancel}
              accessibilityRole="button"
              testID={`${testID}-cancel`}
            >
              <Text style={shortfallStyles.secondaryLabel}>{TRADE_SHORTFALL_CANCEL_LABEL}</Text>
            </Pressable>
            <Pressable
              style={[shortfallStyles.primary, shortfallStyles.action, busy && shortfallStyles.disabled]}
              disabled={busy}
              onPress={onConfirm}
              accessibilityRole="button"
              testID={`${testID}-confirm`}
            >
              <Text style={shortfallStyles.primaryLabel}>{confirmLabel}</Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

/** Stili dei riquadri e dei fogli dal basso del sostituto, riusati da `TradeReplacementSheet`. */
export const shortfallStyles = lazyStyles(() =>
  StyleSheet.create({
    box: {
      flexDirection: "row",
      gap: spacing.sm,
      alignItems: "flex-start",
      padding: spacing.md,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.warning,
      backgroundColor: colors.backgroundSubtle,
    },
    // Corsa Mercato del 25/11: ruoli sotto quota senza giocatori mancanti, giallo più leggero.
    boxInfo: { borderColor: colors.warningMuted, backgroundColor: colors.background },
    icon: { color: colors.warning, fontSize: 18, lineHeight: 22 },
    iconInfo: { color: colors.warningMuted },
    boxText: { flex: 1, minWidth: 0, gap: spacing.xs, alignItems: "flex-start" },
    boxTitle: { color: colors.warning, fontWeight: typography.fontWeight.bold },
    boxBody: { color: colors.foreground, lineHeight: 20 },
    boxStrong: { fontWeight: typography.fontWeight.semibold },
    note: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm, marginTop: spacing.xs },
    backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
    sheet: {
      maxHeight: "90%",
      gap: spacing.sm,
      padding: spacing.md,
      paddingBottom: spacing.lg,
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    grip: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: colors.border },
    sheetTitle: {
      color: colors.foreground,
      fontSize: typography.fontSize.lg,
      fontWeight: typography.fontWeight.bold,
    },
    scroll: { flexGrow: 0 },
    scrollContent: { gap: spacing.sm },
    message: { color: colors.foreground, lineHeight: 20 },
    actions: { flexDirection: "row", gap: spacing.sm },
    action: { flex: 1 },
    primary: {
      minHeight: 48,
      borderRadius: radius.lg,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      backgroundColor: colors.brand,
    },
    primaryLabel: { color: colors.onBrand, fontWeight: typography.fontWeight.bold },
    secondary: {
      minHeight: 48,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.borderStrong,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: spacing.md,
    },
    secondaryLabel: { color: colors.foreground, fontWeight: typography.fontWeight.semibold },
    disabled: { opacity: 0.5 },
  }),
);
