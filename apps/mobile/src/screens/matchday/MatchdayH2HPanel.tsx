import type {
  H2HCalendar,
  H2HCalendarMatchup,
  H2HCalendarRound,
  H2HMatchupScore,
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

function formatScore(score: number | null): string {
  if (score === null || Number.isNaN(score)) {
    return "—";
  }
  return score.toFixed(1);
}

function resultLabel(result: H2HMatchupScore): string {
  const homeGoals = result.homeFantasyGoals ?? 0;
  const awayGoals = result.awayFantasyGoals ?? 0;
  const points = `${formatScore(result.homeScore)} – ${formatScore(result.awayScore)}`;
  return `${homeGoals}–${awayGoals} (${points})`;
}

/** Prima giornata non ancora conclusa; se tutte finite, l'ultima. Port of the web helper. */
export function resolveDefaultH2HRound(calendar: H2HCalendar): number {
  for (const round of calendar.rounds) {
    if (round.homologationStatus === "homologated") {
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
  if (round.homologationStatus === "homologated") {
    return "Risultati finali (storico)";
  }
  const played = round.matchups.filter((matchup) => !matchup.isBye);
  const hasResult = played.some((matchup) => matchup.result != null);
  if (hasResult) {
    return "Risultati provvisori / in corso";
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
  const statusLabel = matchup.result
    ? matchup.result.resultFinal
      ? "Finale"
      : "Provvisorio"
    : "In attesa";
  const statusColor = matchup.result
    ? matchup.result.resultFinal
      ? colors.success
      : colors.warning
    : colors.foregroundMuted;

  return (
    <Pressable
      style={styles.matchup}
      onPress={() => onOpenMatchup(matchup.slotId)}
      testID={`h2h-matchup-${matchup.slotId}`}
      accessibilityRole="button"
    >
      <View style={styles.matchupHeader}>
        <Text style={styles.teamLine}>
          {homeName} vs {awayName}
        </Text>
        <StatusBadge label={statusLabel} color={statusColor} textColor={colors.accentContrast} />
      </View>
      <Text style={styles.body}>
        {matchup.result ? resultLabel(matchup.result) : "Risultato non ancora calcolato"}
      </Text>
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
          Girone di andata · {calendar.roundCount} giornate · {calendar.matchupCount} scontri
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
          <View style={styles.stack}>
            {activeRound.matchups.map((matchup) => (
              <MatchupRow key={matchup.slotId} matchup={matchup} onOpenMatchup={onOpenMatchup} />
            ))}
          </View>
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
