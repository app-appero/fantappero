import type { LeagueStanding } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { fetchLeagueStandings, fetchMyFantasyTeam } from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
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
  const { accessToken, activeLeagueId, activeLeague } = useAuthSession();

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
          <StandingsTableBlock standings={standings} myTeamId={myTeamId} />
        </View>
      ) : null}
    </PageContainer>
  );
}

function StandingsTableBlock({
  standings,
  myTeamId,
}: {
  standings: LeagueStanding[];
  myTeamId: string | null;
}) {
  const rows = useMemo(
    () =>
      standings.map((row) => ({
        ...row,
        isCurrentUser: myTeamId !== null && row.fantasyTeamId === myTeamId,
      })),
    [myTeamId, standings],
  );

  return (
    <View style={styles.table} testID="standings-table">
      <View style={[styles.row, styles.headerRow]}>
        <Text style={[styles.cell, styles.posCell, styles.headerCell]}>Pos.</Text>
        <Text style={[styles.cell, styles.teamCell, styles.headerCell]}>Squadra</Text>
        <Text style={[styles.cell, styles.statCell, styles.headerCell]}>G</Text>
        <Text style={[styles.cell, styles.statCell, styles.headerCell]}>Pt</Text>
        <Text style={[styles.cell, styles.goalsCell, styles.headerCell]}>GF:GS</Text>
      </View>
      {rows.map((row) => (
        <View
          key={row.fantasyTeamId}
          style={[styles.row, row.isCurrentUser ? styles.rowCurrent : null]}
          testID={row.isCurrentUser ? "standings-row-current" : undefined}
        >
          <Text style={[styles.cell, styles.posCell]}>{row.position}</Text>
          <View style={[styles.teamCell, styles.teamCellInner]}>
            <Text style={styles.teamName}>{row.teamName}</Text>
            {row.isCurrentUser ? (
              <View style={styles.badge}>
                <Text style={styles.badgeLabel}>Tu</Text>
              </View>
            ) : null}
          </View>
          <Text style={[styles.cell, styles.statCell]}>{row.played}</Text>
          <Text style={[styles.cell, styles.statCell]}>{row.points}</Text>
          <Text style={[styles.cell, styles.goalsCell]}>
            {row.fantasyGoalsFor}:{row.fantasyGoalsAgainst}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  stack: {
    gap: spacing.sm,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: "600",
  },
  table: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: "hidden",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.xs,
  },
  headerRow: {
    backgroundColor: colors.backgroundElevated,
  },
  rowCurrent: {
    backgroundColor: colors.backgroundElevated,
  },
  cell: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  headerCell: {
    fontWeight: typography.fontWeight.semibold,
    color: colors.foregroundMuted,
  },
  posCell: {
    width: 32,
  },
  teamCell: {
    flex: 1,
  },
  teamCellInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  teamName: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    flexShrink: 1,
  },
  statCell: {
    width: 32,
    textAlign: "center",
  },
  goalsCell: {
    width: 64,
    textAlign: "right",
  },
  badge: {
    backgroundColor: colors.accent,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
  badgeLabel: {
    color: colors.accentContrast,
    fontSize: typography.fontSize.xs,
    fontWeight: typography.fontWeight.semibold,
  },
});
