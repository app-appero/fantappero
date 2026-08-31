import type { H2HMatchupDetail, H2HPlayerScore, H2HSideLineup } from "@fantappero/contracts";
import {
  H2H_GOALS_LABEL,
  H2H_POINTS_LABEL,
  describeH2HResult,
  fantasyBadgesFromBonusMalus,
  formatFantasyGoals,
  formatFantasyPoints,
  layoutFromModule,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { fetchH2HMatchup } from "../api/leagues";
import { PitchView } from "../components/match/PitchView";
import { StatusBadge } from "../components/StatusBadge";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useLiveMatchupPolling } from "../matchday/useLiveMatchupPolling";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

/** `"7.5"`, `"7.5 LIVE"` mentre la partita reale del giocatore è in corso (§21). */
function playerScoreLabel(player: H2HPlayerScore): string | null {
  if (player.fantasyScore === null) {
    return null;
  }
  const base = formatFantasyPoints(player.fantasyScore);
  return player.fixtureStatusLabel === "LIVE" ? `${base} LIVE` : base;
}

function toFantasyPitchPlayers(players: readonly H2HPlayerScore[]) {
  return players.map((player) => ({
    id: player.athleteId,
    name: player.name,
    role: player.role,
    badges: fantasyBadgesFromBonusMalus(player.bonusMalus ?? []),
    scoreLabel: playerScoreLabel(player),
    photoUrl: player.photoUrl,
  }));
}

function PlayerBreakdown({ player }: { player: H2HPlayerScore }) {
  const componentText = (player.bonusMalus ?? [])
    .map((item) => `${item.id} ${item.contribution > 0 ? "+" : ""}${item.contribution.toFixed(1)}`)
    .join(" · ");
  return (
    <View style={styles.playerScore} testID={`matchup-player-score-${player.athleteId}`}>
      <Text style={styles.body}>
        <Text style={styles.playerName}>{player.name}</Text> ({player.role}) ·{" "}
        {player.realTeamName ?? "Squadra reale non associata"}
      </Text>
      <Text style={styles.meta}>
        {player.fixtureStatusLabel ?? "Partita non associata"} · Voto{" "}
        {formatFantasyPoints(player.baseScore ?? null)} · Bonus +
        {(player.bonusTotal ?? 0).toFixed(1)} · Malus {(player.malusTotal ?? 0).toFixed(1)} · Totale{" "}
        {formatFantasyPoints(player.fantasyScore)} · {player.scoreFinal ? "definitivo" : "provvisorio"}
      </Text>
      <Text style={styles.meta}>{componentText || "Nessun bonus o malus"}</Text>
    </View>
  );
}

function outcomeLabel(outcome: "home" | "away" | "draw" | null): string {
  if (outcome === "home") {
    return "Vittoria casa";
  }
  if (outcome === "away") {
    return "Vittoria trasferta";
  }
  if (outcome === "draw") {
    return "Pareggio";
  }
  return "Esito non disponibile";
}

function SideBlock({ side, title }: { side: H2HSideLineup; title: string }) {
  const teamLabel = side.teamName ?? side.displayName;
  return (
    <View style={styles.side} testID={`matchup-side-${title}`}>
      <Text style={styles.heading}>
        {teamLabel}
        {side.module ? ` · ${side.module}` : ""}
      </Text>
      <Text style={styles.body}>
        {H2H_POINTS_LABEL}: {formatFantasyPoints(side.totalScore)} · {H2H_GOALS_LABEL}:{" "}
        {formatFantasyGoals(side.fantasyGoals)} · Fonte:{" "}
        {side.lineupSource === "effective"
          ? "formazione effettiva"
          : side.lineupSource === "submitted"
            ? "formazione schierata"
            : "non disponibile"}
      </Text>
      {side.starters.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Formazione assente"
          message="Questa squadra non ha ancora una formazione per il turno."
          testID={`matchup-lineup-empty-${title}`}
        />
      ) : (
        <View style={styles.lineupGroup}>
          <PitchView
            title={`Titolari — ${teamLabel}`}
            players={toFantasyPitchPlayers(side.starters)}
            positions={layoutFromModule(
              side.starters,
              side.module,
              (player) => player.role,
              (player) => player.athleteId,
              (player) => side.starters.indexOf(player),
            )}
            testID={`matchup-pitch-${title}`}
          />
          <Text style={styles.subheading}>Dettaglio punteggi titolari</Text>
          {side.starters.map((player) => (
            <PlayerBreakdown key={player.athleteId} player={player} />
          ))}
          {side.bench.length > 0 ? (
            <>
              <Text style={styles.subheading}>Panchina</Text>
              {side.bench.map((player) => (
                <PlayerBreakdown key={player.athleteId} player={player} />
              ))}
            </>
          ) : null}
        </View>
      )}
    </View>
  );
}

/** Dettaglio scontro H2H — mobile port of `apps/web/src/pages/MatchupDetailPage.tsx`. */
export function MatchupDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const route = useRoute<RouteProp<RootStackParamList, "MatchupDetail">>();
  const slotId = route.params?.slotId ?? null;
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const canView = can(["matchday:view"]);

  const [detail, setDetail] = useState<H2HMatchupDetail | null>(null);
  const resultDisplay = describeH2HResult(detail?.result);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!canView) {
      setLoading(false);
      return;
    }
    if (!activeLeagueId || !slotId) {
      setLoading(false);
      setDetail(null);
      setError(slotId ? null : "Scontro non specificato.");
      return;
    }
    if (!accessToken) {
      setLoading(false);
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await fetchH2HMatchup(accessToken, activeLeagueId, slotId);
      setDetail(next);
    } catch (err) {
      setError(getApiErrorMessage(err, "Impossibile caricare lo scontro."));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId, canView, slotId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const { degraded: liveDegraded } = useLiveMatchupPolling(
    accessToken,
    activeLeagueId,
    slotId,
    detail,
    setDetail,
    true,
  );

  if (!canView) {
    return (
      <PageContainer title="Scontro diretto" testID="screen-matchup-detail">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso al dettaglio dello scontro."
          testID="matchup-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Scontro diretto" testID="screen-matchup-detail">
      <Pressable onPress={() => navigation.goBack()} testID="matchup-back">
        <Text style={styles.link}>← Torna al calendario fantallenatori</Text>
      </Pressable>

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento scontro"
          message="Recupero formazioni e punteggi…"
          testID="matchup-loading"
        />
      ) : null}

      {!loading && error ? (
        <View style={styles.stack} testID="matchup-error-wrap">
          <UiStatePanel
            state="error"
            title="Scontro non disponibile"
            message={error}
            testID="matchup-error"
          />
          <Pressable style={styles.secondaryButton} onPress={() => void loadDetail()}>
            <Text style={styles.secondaryLabel}>Ricarica</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !error && !detail ? (
        <UiStatePanel
          state="empty"
          title="Scontro non trovato"
          message="Lo scontro richiesto non è presente nel calendario confermato."
          testID="matchup-empty"
        />
      ) : null}

      {!loading && !error && detail ? (
        <View style={styles.stack} testID="matchup-detail">
          <View style={styles.badgeRow}>
            <Text style={styles.body}>Giornata {detail.roundNumber}</Text>
            {detail.live ? (
              <StatusBadge
                label="Live"
                color={colors.warning}
                textColor={colors.accentContrast}
                testID="matchup-live-badge"
              />
            ) : null}
            {detail.result ? (
              <StatusBadge
                label={resultDisplay.statusLabel}
                color={resultDisplay.status === "final" ? colors.success : colors.warning}
                textColor={colors.accentContrast}
                testID="matchup-result-status"
              />
            ) : null}
            {liveDegraded ? (
              <Text style={styles.degraded} testID="matchup-live-degraded">
                Aggiornamento live rallentato…
              </Text>
            ) : null}
          </View>

          {detail.isBye ? (
            <UiStatePanel
              state="empty"
              title="Riposo"
              message={`${detail.home.teamName ?? detail.home.displayName} è a riposo in questa giornata.`}
              testID="matchup-bye"
            />
          ) : (
            <>
              <View style={styles.stack} testID="matchup-result-summary">
                <Text style={styles.body}>
                  {detail.home.teamName ?? detail.home.displayName} contro{" "}
                  {detail.away?.teamName ?? detail.away?.displayName ?? "Avversario"}
                </Text>
                <View style={styles.scoreBox} testID="matchup-result-score">
                  <View style={styles.scoreRow}>
                    <Text style={styles.scoreTerm}>{H2H_GOALS_LABEL}</Text>
                    <Text style={styles.scoreValue} testID="matchup-result-goals">
                      {resultDisplay.goalsLine}
                    </Text>
                  </View>
                  <View style={styles.scoreRow}>
                    <Text style={styles.scoreTerm}>{H2H_POINTS_LABEL}</Text>
                    <Text style={styles.scoreValue} testID="matchup-result-points">
                      {resultDisplay.pointsLine}
                    </Text>
                  </View>
                </View>
                {resultDisplay.unavailableHint ? (
                  <Text style={styles.body} testID="matchup-result-hint">
                    {resultDisplay.unavailableHint}
                  </Text>
                ) : null}
                <Text style={styles.body}>
                  {resultDisplay.statusLabel} · {outcomeLabel(detail.result?.outcome ?? null)}
                </Text>
              </View>
              <View style={styles.sides}>
                <SideBlock side={detail.home} title="home" />
                {detail.away ? <SideBlock side={detail.away} title="away" /> : null}
              </View>
            </>
          )}
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
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
  stack: {
    gap: spacing.md,
  },
  sides: {
    gap: spacing.md,
  },
  side: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
    backgroundColor: colors.backgroundElevated,
  },
  lineupGroup: {
    gap: spacing.xs,
  },
  playerScore: {
    gap: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.xs,
  },
  playerName: {
    fontWeight: "700",
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  heading: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: "700",
  },
  subheading: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "600",
    marginTop: spacing.xs,
  },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  link: {
    color: colors.accent,
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
