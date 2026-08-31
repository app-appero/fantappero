import { MaterialCommunityIcons } from "@expo/vector-icons";
import type {
  FixtureLineup,
  FixtureLineupPlayer,
  FixtureLiveDetail,
  FixtureTimelineEvent,
  MatchBadge,
  ProviderFeedState,
} from "@fantappero/contracts";
import { layoutFromGrid, mapFixtureMatchStatus, realMatchBadgesByAthlete } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useRoute, type RouteProp } from "@react-navigation/core";
import { useCallback, useState, type ReactNode } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { fetchFixtureLiveDetail } from "../api/leagues";
import { MatchTimeline, type TimelineEntry } from "../components/match/MatchTimeline";
import { PitchView } from "../components/match/PitchView";
import { RoleBadge } from "../components/match/RoleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { useLiveFixturePolling } from "../matchday/useLiveFixturePolling";
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

function pitchPlayerId(player: FixtureLineupPlayer): string {
  return player.athleteId ?? `${player.name}-${player.shirtNumber ?? ""}`;
}

function toPitchPlayers(players: readonly FixtureLineupPlayer[], badgesByAthlete: Map<string, MatchBadge[]>) {
  return players.map((player) => ({
    id: pitchPlayerId(player),
    shirtNumber: player.shirtNumber,
    name: player.name,
    role: player.position,
    badges: player.athleteId ? badgesByAthlete.get(player.athleteId) : undefined,
    photoUrl: player.photoUrl,
  }));
}

/** Stato reale del panchinaro (§14): non un fisso "può subentrare" a partita finita. */
function benchStatusLabel(player: FixtureLineupPlayer, events: readonly FixtureTimelineEvent[]): string {
  if (!player.athleteId) {
    return "Non utilizzato";
  }
  const entered = events.find(
    (event) => event.eventType.toLowerCase() === "subst" && event.relatedAthleteId === player.athleteId,
  );
  if (entered) {
    return `Entrato al ${entered.minuteLabel}`;
  }
  const sentOff = events.find(
    (event) =>
      event.athleteId === player.athleteId &&
      event.eventType.toLowerCase() === "card" &&
      (event.eventDetail ?? "").toLowerCase().includes("red"),
  );
  if (sentOff) {
    return `Espulso dalla panchina al ${sentOff.minuteLabel}`;
  }
  return "Non utilizzato";
}

function BenchList({ players, events, side }: { players: readonly FixtureLineupPlayer[]; events: readonly FixtureTimelineEvent[]; side: string }) {
  if (players.length === 0) {
    return null;
  }
  return (
    <View testID={`fixture-bench-${side}`}>
      {players.map((player) => (
        <View key={pitchPlayerId(player)} style={styles.playerRow} testID={`fixture-bench-player-${pitchPlayerId(player)}`}>
          <RoleBadge code={player.position} />
          <Text style={styles.body}>
            {player.shirtNumber !== null ? `${player.shirtNumber}. ` : ""}
            {player.name} — <Text style={styles.benchStatus}>{benchStatusLabel(player, events)}</Text>
          </Text>
        </View>
      ))}
    </View>
  );
}

function LineupBlock({
  lineup,
  events,
  side,
}: {
  lineup: FixtureLineup | null;
  events: readonly FixtureTimelineEvent[];
  side: string;
}) {
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

  const badgesByAthlete = realMatchBadgesByAthlete(events);
  const positions = layoutFromGrid(
    lineup.starters.map((player) => ({ id: pitchPlayerId(player), grid: player.grid })),
  );
  const title = [lineup.clubName, lineup.formation, lineup.coachName ? `All. ${lineup.coachName}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <View style={styles.section} testID={`fixture-lineup-${side}`}>
      <PitchView
        title={title}
        players={toPitchPlayers(lineup.starters, badgesByAthlete)}
        positions={positions}
        testID={`fixture-pitch-${side}`}
      />
      <Text style={styles.subheading}>Panchina</Text>
      <BenchList players={lineup.bench} events={events} side={side} />
    </View>
  );
}

function eventSide(event: FixtureTimelineEvent, detail: FixtureLiveDetail): "home" | "away" | null {
  if (!event.clubId) {
    return null;
  }
  if (event.clubId === detail.homeClubId) {
    return "home";
  }
  if (event.clubId === detail.awayClubId) {
    return "away";
  }
  return null;
}

function eventVisual(event: FixtureTimelineEvent): { icon: ReactNode; headline: ReactNode; detail?: ReactNode } {
  const type = event.eventType.toLowerCase();
  const detailText = (event.eventDetail ?? "").toLowerCase();
  const isOwnGoal = event.scoringKind === "own_goal" || detailText.includes("own");

  if (type === "goal") {
    if (isOwnGoal) {
      return {
        icon: <MaterialCommunityIcons name="soccer" size={16} color={colors.danger} />,
        headline: `${event.athleteName ?? "?"} (autogol)`,
      };
    }
    const isMissed = event.scoringKind === "penalty_missed" || detailText.includes("missed");
    if (isMissed) {
      return {
        icon: <MaterialCommunityIcons name="close-circle" size={16} color={colors.danger} />,
        headline: `${event.athleteName ?? "?"} — rigore sbagliato`,
      };
    }
    const isPenalty = event.scoringKind === "penalty_scored" || detailText.includes("penalty");
    return {
      icon: <MaterialCommunityIcons name="soccer" size={16} color="#fff" />,
      headline: `${event.athleteName ?? "?"}${isPenalty ? " (rigore)" : ""}`,
      detail: event.relatedAthleteName ? `Assist: ${event.relatedAthleteName}` : undefined,
    };
  }
  if (event.scoringKind === "penalty_saved" || type === "penalty_saved") {
    return {
      icon: <MaterialCommunityIcons name="hand-back-right" size={16} color="#fff" />,
      headline: `Rigore parato${event.athleteName ? ` — ${event.athleteName}` : ""}`,
    };
  }
  if (type === "card") {
    const isRed = detailText.includes("red");
    return {
      icon: <MaterialCommunityIcons name="card" size={16} color={isRed ? colors.danger : colors.warning} />,
      headline: event.athleteName ?? "?",
    };
  }
  if (type === "subst") {
    return {
      icon: <MaterialCommunityIcons name="arrow-down-bold-box" size={16} color={colors.danger} />,
      headline: event.athleteName ?? "?",
      detail: event.relatedAthleteName ? `↑ ${event.relatedAthleteName}` : undefined,
    };
  }
  if (type === "var") {
    return {
      icon: <MaterialCommunityIcons name="alert-decagram" size={16} color="#fff" />,
      headline: `VAR — ${event.eventDetail ?? "Revisione"}`,
      detail: event.athleteName ?? undefined,
    };
  }
  return { icon: undefined, headline: `${event.eventType}${event.eventDetail ? ` (${event.eventDetail})` : ""}` };
}

function buildTimelineEntries(detail: FixtureLiveDetail): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  let homeScore = 0;
  let awayScore = 0;
  let insertedHalftime = false;
  const hasFirstHalf = detail.events.some((e) => (e.minuteElapsed ?? 0) <= 45);
  const hasSecondHalf = detail.events.some((e) => (e.minuteElapsed ?? 0) > 45);

  if (detail.events.length > 0) {
    entries.push({ type: "marker", id: "start", label: "Inizio partita" });
  }

  for (const event of detail.events) {
    if (!insertedHalftime && hasFirstHalf && hasSecondHalf && (event.minuteElapsed ?? 0) > 45) {
      entries.push({ type: "marker", id: "halftime", label: `Intervallo · ${homeScore}-${awayScore}` });
      insertedHalftime = true;
    }

    const side = eventSide(event, detail);
    const detailText = (event.eventDetail ?? "").toLowerCase();
    const isOwnGoal = event.scoringKind === "own_goal" || detailText.includes("own");
    const isMissed = event.scoringKind === "penalty_missed" || detailText.includes("missed");
    const isGoal = event.eventType.toLowerCase() === "goal" && !isMissed;
    if (isGoal && side) {
      const scoringSide = isOwnGoal ? (side === "home" ? "away" : "home") : side;
      if (scoringSide === "home") {
        homeScore += 1;
      } else {
        awayScore += 1;
      }
    }

    if (!side) {
      continue;
    }
    const visual = eventVisual(event);
    entries.push({
      type: "event",
      id: event.id,
      side,
      minuteLabel: event.minuteLabel,
      icon: visual.icon,
      headline: visual.headline,
      detail: visual.detail,
    });
  }

  if (mapFixtureMatchStatus(detail.statusShort) === "finished") {
    entries.push({ type: "marker", id: "end", label: `Fine partita · ${homeScore}-${awayScore}` });
  }

  return entries;
}

/** Dettaglio partita del turno europeo — parità con il web (EP13-P04-quater). */
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

  useLiveFixturePolling(
    accessToken,
    activeLeagueId,
    turnId,
    fixtureId,
    detail,
    setDetail,
    !loading && !loadError,
  );

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

  const matchStatus = detail ? mapFixtureMatchStatus(detail.statusShort) : null;
  const isFinished = matchStatus === "finished";

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
          <View style={styles.scoreRow}>
            {detail.homeClubLogoUrl ? (
              <Image source={{ uri: detail.homeClubLogoUrl }} style={styles.clubLogo} />
            ) : null}
            <Text style={styles.score} testID="fixture-score">
              {detail.homeClubName} {detail.homeGoals ?? "—"} – {detail.awayGoals ?? "—"}{" "}
              {detail.awayClubName}
            </Text>
            {detail.awayClubLogoUrl ? (
              <Image source={{ uri: detail.awayClubLogoUrl }} style={styles.clubLogo} />
            ) : null}
          </View>
          <View style={styles.badgeRow}>
            <StatusBadge
              label={statusLabel(detail.statusShort, detail.statusElapsed)}
              color={isFinished ? colors.success : colors.accent}
              textColor={colors.accentContrast}
              testID="fixture-status"
            />
            {/* A partita finita "Aggiornato" non aggiunge informazione (§13). */}
            {!isFinished ? (
              <StatusBadge
                label={detail.feedStateLabel}
                color={FEED_COLORS[detail.feedState]}
                textColor={colors.accentContrast}
                testID="fixture-feed-state"
              />
            ) : null}
          </View>
          <Text style={styles.body}>
            {detail.competitionName ? `${detail.competitionName} · ` : ""}
            Inizio: {formatDateTime(detail.kickoffAt)}
          </Text>
          {detail.venueName || detail.referee ? (
            <Text style={styles.body} testID="fixture-venue-referee">
              {detail.venueName
                ? `${detail.venueName}${detail.venueCity ? ` (${detail.venueCity})` : ""}`
                : ""}
              {detail.venueName && detail.referee ? " · " : ""}
              {detail.referee ? `Arbitro: ${detail.referee}` : ""}
            </Text>
          ) : null}

          <LineupBlock lineup={detail.homeLineup} events={detail.events} side="home" />
          <LineupBlock lineup={detail.awayLineup} events={detail.events} side="away" />

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
              <MatchTimeline
                homeLabel={detail.homeClubName}
                awayLabel={detail.awayClubName}
                entries={buildTimelineEntries(detail)}
              />
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
  benchStatus: {
    fontStyle: "italic",
    color: colors.foregroundMuted,
  },
  playerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  scoreRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  clubLogo: {
    width: 24,
    height: 24,
    resizeMode: "contain",
  },
});
