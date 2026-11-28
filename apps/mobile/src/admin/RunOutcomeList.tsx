import { lazyStyles } from "../theme/lazyStyles";
import type { RunOutcomeLine, RunTone } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors, spacing, typography, radius } = theme;

export type RunOutcomeListProps = {
  title: string;
  /** Riga di riepilogo sopra l'elenco (es. «Avviati 8 job su 9»). */
  summary?: string | null;
  tone: RunTone;
  lines: RunOutcomeLine[];
  testID: string;
};

function toneColor(tone: RunTone): string {
  switch (tone) {
    case "success":
      return colors.success;
    case "warning":
      return colors.warning;
    case "error":
      return colors.danger;
    default:
      return colors.border;
  }
}

/**
 * Esito di «Esegui» e «Esegui tutti» (1.5): una riga per job o per operazione, con il colore
 * dell'esito (verde riuscito, giallo avviso o saltato, rosso errore). Gli stessi testi del sito
 * (`@fantappero/contracts`).
 */
export function RunOutcomeList({ title, summary, tone, lines, testID }: RunOutcomeListProps) {
  return (
    <View
      style={[styles.box, { borderLeftColor: toneColor(tone) }]}
      accessibilityLiveRegion="polite"
      testID={testID}
    >
      <Text style={styles.title} accessibilityRole="header">
        {title}
      </Text>
      {summary ? (
        <Text style={styles.summary} testID={`${testID}-summary`}>
          {summary}
        </Text>
      ) : null}
      {lines.map((line) => (
        <View
          key={line.key}
          style={[styles.line, { borderLeftColor: toneColor(line.tone) }]}
          testID={`${testID}-${line.key}`}
        >
          <Text style={styles.lineTitle}>{line.title}</Text>
          <Text style={styles.lineText}>{line.text}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    box: {
      gap: spacing.sm,
      padding: spacing.md,
      borderRadius: radius.xl,
      borderWidth: 1,
      borderLeftWidth: 4,
      borderColor: colors.border,
      backgroundColor: colors.background,
    },
    title: {
      color: colors.foreground,
      fontSize: typography.fontSize.md,
      fontWeight: typography.fontWeight.semibold,
    },
    summary: {
      color: colors.foreground,
      fontWeight: typography.fontWeight.semibold,
    },
    line: {
      gap: 2,
      paddingVertical: spacing.xs,
      paddingHorizontal: spacing.sm,
      borderLeftWidth: 3,
      borderRadius: radius.md,
      backgroundColor: colors.backgroundElevated,
    },
    lineTitle: {
      color: colors.foreground,
      fontWeight: typography.fontWeight.semibold,
    },
    lineText: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
  }),
);
