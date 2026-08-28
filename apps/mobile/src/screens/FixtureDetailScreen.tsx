import type { FixtureLineup, FixtureLiveDetail, ProviderFeedState } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useRoute, type RouteProp } from "@react-navigation/core";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { fetchFixtureLiveDetail } from "../api/leagues";
import { StatusBadge } from "../components/StatusBadge";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

/** Stesse etichette del web: la parità è anche di copy. */
const STATUS_LABELS: Record<string, string> = {
  NS: "Non iniziata",
  "1H": "Primo tempo",
  HT: "Intervallo",
  "2H": "Secondo tempo",
  ET: "Supplementari",
  BT: "Pausa supplementari",
  P: "Rigori",
  LIVE: "In corso",
  INT: "Interrotta",
  SUSP: "Sospesa",
  FT: "Finita",
  AET: "Finita dopo i supplementari",
  PEN: "Finita ai rigori",
  PST: "Rinviata",
  CANC: "Annullata",
  ABD: "Abbandonata",
  AWD: "Vittoria a tavolino",
  WO: "Walkover",
};

const FEED_COLORS: Record<ProviderFeedState, string> = {
  fresh: colors.success,
  delayed: colors.warning,
  stale: colors.warning,
  degraded: colors.warning,
  unavailable: colors.foregroundMuted,
};

function statusLabel(statusShort: string, statusElapsed: number | null): string {
  const base = STATUS_LABELS[statusShort.toUpperCase()] ?? statusShort;
  return statusElapsed === null ? base : `${base} · ${statusElapsed}'`;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function LineupBlock({ lineup, side }: { lineup: FixtureLineup | null; side: string }) {
  if (lineup === null) {
    return (
      <View style={styles.section} testID={`fixture-lineup-${side}`}>
        <UiStatePanel
          state="empty"
          title="Formazione non disponibile"
          message="La formazione ufficiale non è ancora stata pubblicata per questa squadra."
          testID={`fixture-lineup-empty-${side}`}
        />
      </View>
    );
  }

  return (
    <View style={styles.section} testID={`fixture-lineup-${side}`}>
      <Text style={styles.heading}>
        {lineup.clubName}
        {lineup.formation ? ` · ${lineup.formation}` : ""}
      </Text>
      <Text style={styles.subheading}>Titolari</Text>
      {lineup.starters.map((player) => (
        <Text key={`s-${player.athleteId ?? player.name}`} style={styles.body}>
          {player.shirtNumber !== null ? `${player.shirtNumber}. ` : ""}
          {player.name}
          {player.position ? ` (${player.position})` : ""}
        </Text>
      ))}
      {lineup.bench.length > 0 ? (
        <>
          <Text style={styles.subheading}>Panchina</Text>
          {lineup.bench.map((player) => (
            <Text key={`b-${player.athleteId ?? player.name}`} style={styles.body}>
              {player.shirtNumber !== null ? `${player.shirtNumber}. ` : ""}
              {player.name}
            </Text>
          ))}
        </>
      ) : null}
    </View>
  );
}

/** Dettaglio partita del turno europeo — parità con il web (EP13-P04). */
export function FixtureDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "FixtureDetail">>();
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const { turnId, fixtureId } = route.params;

  const [detail, setDetail] = useState<FixtureLiveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!activeLeagueId || !accessToken) {
      setLoading(false);
      setDetail(null);
      setLoadError(!activeLeagueId ? null : "Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      setDetail(await fetchFixtureLiveDetail(accessToken, activeLeagueId, turnId, fixtureId));
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la partita."));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId, fixtureId, turnId]);

  const { refreshing, onRefresh } = useScreenData(load);

  if (!can(["matchday:view"])) {
    return (
      <PageContainer title="Partita" testID="screen-fixture-detail">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso ai turni di questa lega."
          testID="fixture-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={detail ? `${detail.homeClubName} – ${detail.awayClubName}` : "Partita"}
      testID="screen-fixture-detail"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento partita"
          message="Recupero formazioni ed eventi…"
          testID="fixture-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Partita non disponibile"
          message={loadError}
          testID="fixture-error"
        />
      ) : null}

      {!loading && !loadError && detail ? (
        <View style={styles.stack} testID="fixture-detail">
          <Text style={styles.score} testID="fixture-score">
            {detail.homeClubName} {detail.homeGoals ?? "—"} – {detail.awayGoals ?? "—"}{" "}
            {detail.awayClubName}
          </Text>
          <View style={styles.badgeRow}>
            <StatusBadge
              label={statusLabel(detail.statusShort, detail.statusElapsed)}
              color={colors.accent}
              textColor={colors.accentContrast}
              testID="fixture-status"
            />
            <StatusBadge
              label={detail.feedStateLabel}
              color={FEED_COLORS[detail.feedState]}
              textColor={colors.accentContrast}
              testID="fixture-feed-state"
            />
          </View>
          <Text style={styles.body}>
            {detail.competitionName ? `${detail.competitionName} · ` : ""}
            Inizio: {formatDateTime(detail.kickoffAt)}
          </Text>
          <Text style={styles.body}>
            Ultimo aggiornamento: {formatDateTime(detail.updatedAt)}
          </Text>

          <LineupBlock lineup={detail.homeLineup} side="home" />
          <LineupBlock lineup={detail.awayLineup} side="away" />

          <View style={styles.section}>
            <Text style={styles.heading}>Cronologia</Text>
            {detail.events.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun evento"
                message="Il provider non ha ancora pubblicato eventi per questa partita."
                testID="fixture-timeline-empty"
              />
            ) : (
              <View testID="fixture-timeline">
                {detail.events.map((event) => (
                  <Text key={event.id} style={styles.body}>
                    {event.minuteLabel} — {event.eventType}
                    {event.eventDetail ? ` (${event.eventDetail})` : ""}
                    {event.athleteName ? `: ${event.athleteName}` : ""}
                    {event.relatedAthleteName ? ` — assist ${event.relatedAthleteName}` : ""}
                  </Text>
                ))}
              </View>
            )}
          </View>
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: spacing.md,
  },
  section: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    backgroundColor: colors.backgroundElevated,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  score: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: "700",
  },
  heading: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "700",
  },
  subheading: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: "600",
    textTransform: "uppercase",
    marginTop: spacing.xs,
  },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
});
