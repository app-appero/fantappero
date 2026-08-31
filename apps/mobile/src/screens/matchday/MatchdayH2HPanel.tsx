import type { H2HCalendar, H2HCalendarMatchup, H2HCalendarRound } from "@fantappero/contracts";
import {
  H2H_GOALS_LABEL,
  H2H_POINTS_LABEL,
  describeH2HResult,
  h2hResultAriaLabel,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { OptionPicker } from "../../components/OptionPicker";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";

const { colors, spacing, typography, radius } = theme;

type Props = {
  calendar: H2HCalendar | null;
  loading: boolean;
  error: string | null;
  liveDegraded: boolean;
  canAdmin: boolean;
  onRetry: () => void;
  onOpenAdmin: () => void;
  onOpenMatchup: (slotId: string) => void;
};

/** Due grandezze nominate, come sul web (EP13-P02). */
function H2HScoreLines({
  display,
  slotId,
}: {
  display: ReturnType<typeof describeH2HResult>;
  slotId: string;
}) {
  return (
    <View style={styles.scoreBox} testID={`h2h-score-${slotId}`}>
      <View style={styles.scoreRow}>
        <Text style={styles.scoreTerm}>{H2H_GOALS_LABEL}</Text>
        <Text style={styles.scoreValue} testID={`h2h-score-goals-${slotId}`}>
          {display.goalsLine}
        </Text>
      </View>
      <View style={styles.scoreRow}>
        <Text style={styles.scoreTerm}>{H2H_POINTS_LABEL}</Text>
        <Text style={styles.scoreValue} testID={`h2h-score-points-${slotId}`}>
          {display.pointsLine}
        </Text>
      </View>
      {display.unavailableHint ? (
        <Text style={styles.scoreHint} testID={`h2h-score-hint-${slotId}`}>
          {display.unavailableHint}
        </Text>
      ) : null}
    </View>
  );
}

/** Prima giornata non ancora conclusa; se tutte finite, l'ultima. Port of the web helper. */
export function resolveDefaultH2HRound(calendar: H2HCalendar): number {
  for (const round of calendar.rounds) {
    if (round.beforeLeagueCreation || round.homologationStatus === "homologated") {
      continue;
    }
    const played = round.matchups.filter((matchup) => !matchup.isBye);
    const allFinal =
      played.length > 0 && played.every((matchup) => matchup.result?.resultFinal === true);
    if (!allFinal) {
      return round.roundNumber;
    }
  }
  const last = calendar.rounds[calendar.rounds.length - 1];
  return last?.roundNumber ?? 1;
}

function roundStatusHint(round: H2HCalendarRound): string {
  if (round.beforeLeagueCreation) {
    return "Lega creata dopo questo turno";
  }
  if (round.homologationStatus === "homologated") {
    return "Risultati finali (storico)";
  }
  const played = round.matchups.filter((matchup) => !matchup.isBye);
  if (played.some((matchup) => matchup.live)) {
    return "LIVE / risultati provvisori";
  }
  const hasResult = played.some((matchup) => matchup.result != null);
  if (hasResult) {
    return "Risultati provvisori / in attesa";
  }
  if (round.europeanTurnStatus) {
    return `Turno europeo: ${round.europeanTurnStatus}`;
  }
  return "Giornata da disputare";
}

function MatchupRow({
  matchup,
  onOpenMatchup,
}: {
  matchup: H2HCalendarMatchup;
  onOpenMatchup: (slotId: string) => void;
}) {
  const homeName = matchup.homeTeamName ?? matchup.homeDisplayName;

  if (matchup.isBye) {
    return (
      <View style={styles.matchup} testID={`h2h-matchup-${matchup.slotId}`}>
        <Text style={styles.teamLine}>{homeName}</Text>
        <Text style={styles.body}>Riposo in questa giornata.</Text>
      </View>
    );
  }

  const awayName = matchup.awayTeamName ?? matchup.awayDisplayName ?? "Avversario";
  const display = describeH2HResult(matchup.result);
  const statusLabel = matchup.live
    ? "LIVE / provvisorio"
    : display.status === "provisional"
      ? "Provvisorio / in attesa"
      : display.statusLabel;
  const statusColor =
    display.status === "final"
      ? colors.success
      : matchup.live
        ? colors.warning
        : colors.foregroundMuted;

  return (
    <Pressable
      style={styles.matchup}
      onPress={() => onOpenMatchup(matchup.slotId)}
      testID={`h2h-matchup-${matchup.slotId}`}
      accessibilityRole="button"
      accessibilityLabel={h2hResultAriaLabel(display, homeName, awayName)}
    >
      <View style={styles.matchupHeader}>
        <Text style={styles.teamLine}>
          {homeName} vs {awayName}
        </Text>
        <StatusBadge
          label={statusLabel}
          color={statusColor}
          textColor={colors.accentContrast}
        />
      </View>
      <H2HScoreLines display={display} slotId={matchup.slotId} />
    </Pressable>
  );
}

/** Tab "Calendario fantallenatori" — mobile port of `apps/web/src/pages/MatchdayH2HPanel.tsx`. */
export function MatchdayH2HPanel({
  calendar,
  loading,
  error,
  liveDegraded,
  canAdmin,
  onRetry,
  onOpenAdmin,
  onOpenMatchup,
}: Props) {
  const [selectedRound, setSelectedRound] = useState<number | null>(() =>
    calendar ? resolveDefaultH2HRound(calendar) : null,
  );

  useEffect(() => {
    if (!calendar || calendar.rounds.length === 0) {
      setSelectedRound(null);
      return;
    }
    setSelectedRound((current) => {
      if (current != null && calendar.rounds.some((round) => round.roundNumber === current)) {
        return current;
      }
      return resolveDefaultH2HRound(calendar);
    });
  }, [calendar]);

  const activeRoundNumber = selectedRound ?? (calendar ? resolveDefaultH2HRound(calendar) : null);

  const activeRound = useMemo(() => {
    if (!calendar || activeRoundNumber == null) {
      return null;
    }
    return calendar.rounds.find((round) => round.roundNumber === activeRoundNumber) ?? null;
  }, [calendar, activeRoundNumber]);

  if (loading) {
    return (
      <UiStatePanel
        state="loading"
        title="Caricamento calendario"
        message="Recupero degli scontri tra fantallenatori…"
        testID="h2h-loading"
      />
    );
  }

  if (error) {
    return (
      <View testID="h2h-error-wrap" style={styles.stack}>
        <UiStatePanel
          state="error"
          title="Calendario non disponibile"
          message={error}
          testID="h2h-error"
        />
        <Pressable style={styles.secondaryButton} onPress={onRetry} testID="h2h-retry">
          <Text style={styles.secondaryLabel}>Ricarica</Text>
        </Pressable>
      </View>
    );
  }

  if (!calendar) {
    return (
      <View testID="h2h-empty-wrap" style={styles.stack}>
        <UiStatePanel
          state="empty"
          title="Calendario non ancora confermato"
          message={
            canAdmin
              ? "Genera e conferma il calendario scontri diretti in Amministrazione lega."
              : "L'amministratore deve generare e confermare il calendario H2H prima che compaia qui."
          }
          testID="h2h-empty"
        />
        {canAdmin ? (
          <Pressable style={styles.secondaryButton} onPress={onOpenAdmin} testID="h2h-admin-link">
            <Text style={styles.secondaryLabel}>Vai ad Amministrazione lega</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  const roundOptions = calendar.rounds.map((round) => {
    if (round.beforeLeagueCreation) {
      return {
        value: String(round.roundNumber),
        label: `Giornata ${round.roundNumber} · lega creata dopo`,
      };
    }
    const played = round.matchups.filter((matchup) => !matchup.isBye);
    const finals = played.filter((matchup) => matchup.result?.resultFinal).length;
    const suffix =
      round.homologationStatus === "homologated"
        ? " · storico"
        : finals > 0
          ? ` · ${finals}/${played.length} finali`
          : "";
    return {
      value: String(round.roundNumber),
      label: `Giornata ${round.roundNumber}${suffix}`,
    };
  });

  return (
    <View style={styles.stack} testID="h2h-calendar">
      <View style={styles.header}>
        <Text style={styles.lede}>
          {calendar.roundCount} giornate · {calendar.matchupCount} scontri
          {calendar.byeCount > 0 ? ` · ${calendar.byeCount} riposi` : ""}
        </Text>
        <Text style={styles.hint}>
          Seleziona una giornata per vedere gli scontri. Le giornate già concluse restano
          disponibili come storico.
        </Text>
        <OptionPicker
          label="Giornata"
          options={roundOptions}
          value={activeRoundNumber != null ? String(activeRoundNumber) : ""}
          onChange={(value) => setSelectedRound(Number(value))}
          testID="h2h-round-select"
        />
        <View style={styles.badgeRow}>
          {calendar.live ? (
            <StatusBadge
              label="Aggiornamento live"
              color={colors.warning}
              textColor={colors.accentContrast}
              testID="h2h-live-badge"
            />
          ) : null}
          {liveDegraded ? (
            <Text style={styles.degraded} testID="h2h-live-degraded">
              Aggiornamento live rallentato…
            </Text>
          ) : null}
        </View>
      </View>

      {activeRound ? (
        <View style={styles.round} testID={`h2h-round-${activeRound.roundNumber}`}>
          <View style={styles.roundHeader}>
            <Text style={styles.heading}>Giornata {activeRound.roundNumber}</Text>
            <StatusBadge
              label={roundStatusHint(activeRound)}
              color={activeRound.homologationStatus === "homologated" ? colors.success : colors.warning}
              textColor={colors.accentContrast}
              testID="h2h-round-status"
            />
          </View>
          {activeRound.beforeLeagueCreation ? (
            <UiStatePanel
              state="empty"
              title="Lega creata dopo questo turno"
              message="Questo turno europeo è già trascorso al momento della creazione della lega: non ospita scontri fantasy."
              testID="h2h-round-before-creation"
            />
          ) : (
            <View style={styles.stack}>
              {activeRound.matchups.map((matchup) => (
                <MatchupRow key={matchup.slotId} matchup={matchup} onOpenMatchup={onOpenMatchup} />
              ))}
            </View>
          )}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: spacing.md,
  },
  header: {
    gap: spacing.sm,
  },
  lede: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
  },
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  degraded: {
    color: colors.warning,
    fontSize: typography.fontSize.sm,
  },
  round: {
    gap: spacing.sm,
  },
  adminBox: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    backgroundColor: colors.backgroundElevated,
  },
  primaryButton: {
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
    backgroundColor: colors.accent,
  },
  primaryLabel: {
    color: colors.accentContrast,
    fontWeight: "700",
  },
  disabled: {
    opacity: 0.5,
  },
  roundHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  heading: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: "700",
  },
  matchup: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    gap: spacing.xs,
    backgroundColor: colors.backgroundElevated,
  },
  matchupHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  teamLine: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "600",
    flexShrink: 1,
  },
  body: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  scoreBox: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  scoreRow: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  scoreTerm: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  scoreValue: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "700",
  },
  scoreHint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
  },
  secondaryLabel: {
    color: colors.foreground,
  },
});
