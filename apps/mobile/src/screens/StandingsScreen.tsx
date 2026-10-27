import { lazyStyles } from "../theme/lazyStyles";
import type { LeagueStanding } from "@fantappero/contracts";
import { formatFantasyPoints } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { fetchLeagueStandings, fetchMyFantasyTeam } from "../api/leagues";
import { TeamAvatar } from "../components/TeamAvatar";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

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

/** Classifica lega — porting mobile di StandingsPage (EP07-06 parity). */
export function StandingsScreen() {
  const { accessToken, activeLeagueId, activeLeague, can } = useAuthSession();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  const [standings, setStandings] = useState<LeagueStanding[]>([]);
  const [myTeamId, setMyTeamId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadStandings = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!activeLeagueId) {
        setLoading(false);
        setStandings([]);
        setMyTeamId(null);
        setLoadError(null);
        return;
      }
      if (!accessToken) {
        setLoading(false);
        setStandings([]);
        setMyTeamId(null);
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const [rows, myTeam] = await Promise.all([
          fetchLeagueStandings(accessToken, activeLeagueId),
          fetchMyFantasyTeam(accessToken, activeLeagueId).catch(() => null),
        ]);
        setStandings(rows);
        setMyTeamId(myTeam?.id ?? null);
      } catch (error) {
        setLoadError(getApiErrorMessage(error, "Impossibile caricare la classifica."));
        setStandings([]);
        setMyTeamId(null);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, activeLeagueId],
  );

  const { refreshing, onRefresh } = useScreenData(loadStandings);

  const computedAt = standings[0]?.computedAt ?? null;

  return (
    <PageContainer
      title="Classifica"
      testID="screen-standings"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <Text style={styles.meta}>
        {activeLeague ? `Lega: ${activeLeague.name}` : "Seleziona una lega dal selettore in alto."}
      </Text>

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento classifica"
          message="Recupero posizione, punti e gol fantasy…"
          testID="standings-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <View>
          <UiStatePanel
            state="error"
            title="Classifica non disponibile"
            message={loadError}
            testID="standings-error"
          />
          <Pressable style={styles.button} onPress={() => void loadStandings()} testID="standings-reload">
            <Text style={styles.buttonLabel}>Riprova</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Seleziona una lega dall'elenco per vedere la classifica."
          testID="standings-no-league"
        />
      ) : null}

      {!loading && !loadError && activeLeagueId && standings.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Classifica non ancora disponibile"
          message="La classifica si aggiorna automaticamente quando i risultati dei turni diventano finali."
          testID="standings-empty"
        />
      ) : null}

      {!loading && !loadError && standings.length > 0 ? (
        <View style={styles.stack} testID="standings-success">
          {computedAt ? (
            <Text style={styles.meta}>Aggiornata: {formatDateTime(computedAt)}</Text>
          ) : null}
          <StandingsTableBlock
            standings={standings}
            myTeamId={myTeamId}
            onManagerPress={
              activeLeagueId
                ? (managerUserId) =>
                    navigation.navigate("CoachProfile", {
                      userId: managerUserId,
                      leagueId: activeLeagueId,
                    })
                : undefined
            }
          />
        </View>
      ) : null}
    </PageContainer>
  );
}

/** In classifica si vede solo il nickname (se manca, il nome; in ultimo la squadra). */
function Stat({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>{label}</Text>
      <Text style={[styles.statValue, tone === "danger" ? styles.statValueDanger : null]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
        {value}
      </Text>
    </View>
  );
}

function standingLabel(row: LeagueStanding): string {
  return row.managerNickname?.trim() || row.managerDisplayName?.trim() || row.teamName;
}

function StandingsTableBlock({
  standings,
  myTeamId,
  onManagerPress,
}: {
  standings: LeagueStanding[];
  myTeamId: string | null;
  onManagerPress?: (managerUserId: string) => void;
}) {
  const rows = useMemo(
    () =>
      standings.map((row) => ({
        ...row,
        isCurrentUser: myTeamId !== null && row.fantasyTeamId === myTeamId,
      })),
    [myTeamId, standings],
  );

  const first = rows.find((row) => row.position === 1);
  const second = rows.find((row) => row.position === 2);
  const third = rows.find((row) => row.position === 3);
  // Podio: 2° · 1° · 3° affiancati, ognuno con una sola riga di nome.
  const podium = [second, first, third].filter((row): row is (typeof rows)[number] => Boolean(row));

  return (
    <View style={styles.stack}>
      {podium.length > 0 ? (
        <View style={styles.podium} testID="standings-podium">
          {podium.map((row) => {
            const isFirst = row.position === 1;
            return (
              <View
                key={row.fantasyTeamId}
                style={[
                  styles.podiumCard,
                  isFirst ? styles.podiumFirst : styles.podiumSide,
                  row.isCurrentUser ? styles.podiumCurrent : null,
                ]}
              >
                <Text style={[styles.podiumRank, isFirst ? styles.podiumRankFirst : null]}>
                  {row.position}°
                </Text>
                <TeamAvatar
                  name={row.managerNickname ?? row.managerDisplayName ?? row.teamName}
                  avatarUrl={row.managerAvatarUrl}
                  size={isFirst ? 46 : 38}
                />
                <Text style={styles.podiumName} numberOfLines={1}>
                  {standingLabel(row)}
                </Text>
                <Text style={styles.podiumPoints}>
                  {row.points}
                  <Text style={styles.podiumPointsUnit}> pt</Text>
                </Text>
              </View>
            );
          })}
        </View>
      ) : null}

      <View style={styles.listHead}>
        <Text style={styles.meta}>Pos. · Allenatore</Text>
        <Text style={styles.meta}>Punti classifica</Text>
      </View>

      <View style={styles.list} testID="standings-table">
        {rows.map((row) => {
          const label = standingLabel(row);
          const body = (
            <>
            <View style={styles.rowTop}>
              <Text style={styles.rowPos}>{row.position}</Text>
              <TeamAvatar
                name={row.managerNickname ?? row.managerDisplayName ?? row.teamName}
                avatarUrl={row.managerAvatarUrl}
                size={40}
              />
              <Text style={[styles.rowName, onManagerPress ? styles.teamNameLink : null]} numberOfLines={1}>
                {label}
              </Text>
              <View style={styles.rowPoints}>
                <Text style={styles.rowPointsValue}>{row.points}</Text>
                <Text style={styles.rowPointsUnit}>PUNTI</Text>
              </View>
            </View>
            <View style={styles.statsRow}>
              <Stat label="Gare" value={String(row.played)} />
              <Stat label="Gol fatti" value={String(row.fantasyGoalsFor)} />
              <Stat label="Gol subiti" value={String(row.fantasyGoalsAgainst)} tone="danger" />
              <Stat label="Fantapunti" value={formatFantasyPoints(row.fantasyPointsFor)} />
            </View>
          </>
        );
          const rowStyle = [styles.row, row.isCurrentUser ? styles.rowCurrent : null];
          return onManagerPress ? (
            <Pressable
              key={row.fantasyTeamId}
              accessibilityRole="button"
              accessibilityLabel={`Apri il profilo di ${label}`}
              onPress={() => onManagerPress(row.managerUserId)}
              style={rowStyle}
              testID={`standings-manager-${row.fantasyTeamId}`}
            >
              {body}
            </Pressable>
          ) : (
            <View key={row.fantasyTeamId} style={rowStyle} testID={row.isCurrentUser ? "standings-row-current" : undefined}>
              {body}
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  stack: {
    gap: spacing.sm,
  },
  button: {
    backgroundColor: colors.brand,
    borderRadius: radius.pill,
    padding: spacing.sm,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonLabel: {
    color: colors.onBrand,
    fontWeight: "600",
  },
  podium: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
  },
  podiumCard: {
    flex: 1,
    minWidth: 0,
    alignItems: "center",
    gap: 6,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  podiumSide: { marginBottom: 0, paddingTop: spacing.md },
  podiumFirst: {
    borderColor: colors.accentSecondary,
    borderWidth: 2,
    paddingVertical: spacing.md,
  },
  podiumCurrent: {
    backgroundColor: "rgba(79, 92, 245, 0.22)",
  },
  podiumRank: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
  },
  podiumRankFirst: {
    color: "#ffd23f",
  },
  podiumName: {
    width: "100%",
    textAlign: "center",
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  podiumPoints: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
  },
  podiumPointsUnit: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: "600",
  },
  listHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.xs,
  },
  list: {
    gap: spacing.sm,
  },
  rowTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  statsRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  stat: {
    flex: 1,
    minWidth: 0,
  },
  statLabel: {
    color: colors.foregroundMuted,
    fontSize: 9,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  statValue: {
    color: colors.foreground,
    fontWeight: "700",
  },
  statValueDanger: {
    color: "#FF8FA8",
  },
  row: {
    gap: 0,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  rowCurrent: {
    borderColor: colors.accentSecondary,
    backgroundColor: "rgba(79, 92, 245, 0.22)",
  },
  rowPos: {
    width: 22,
    textAlign: "center",
    color: colors.foregroundMuted,
    fontWeight: "800",
  },
  rowInfo: {
    flex: 1,
    minWidth: 0,
    gap: 1,
  },
  rowName: {
    flex: 1,
    minWidth: 0,
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  teamNameLink: {
    color: colors.accent,
  },
  rowMeta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  rowMetaSoft: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    opacity: 0.85,
  },
  rowPoints: {
    alignItems: "flex-end",
  },
  rowPointsValue: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
  },
  rowPointsUnit: {
    color: colors.foregroundMuted,
    fontSize: 11,
    letterSpacing: 1,
  },
}));
