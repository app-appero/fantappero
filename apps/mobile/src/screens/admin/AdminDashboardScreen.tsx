import {
  buildOperatorWatchItems,
  formatLeaguesByState,
  type AdminOverview,
  type OperatorWatchTone,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { fetchAdminOverview } from "../../api/admin";
import { ApiError } from "../../api/client";
import { UiStatePanel } from "../../components/UiStatePanel";
import { useScreenData } from "../../hooks/useScreenData";
import { PageContainer } from "../../layout/PageContainer";
import { adminScreenForWatchTarget } from "../../navigation/adminScreens";
import type { AdminStackParamList } from "../../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import { DISPLAY_FONT } from "../../theme/fonts";
import { lazyStyles } from "../../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

function toneColor(tone: OperatorWatchTone): string {
  switch (tone) {
    case "ok":
      return colors.success;
    case "warn":
      return colors.warning;
    case "bad":
      return colors.danger;
    default:
      return colors.foregroundSubtle;
  }
}

/**
 * «Riepilogo» del pannello operatore (release 1.4, canvas «Pannello operatore» approvato da
 * Rosario il 22/11), come sul sito: chi sei e l'ambiente, i numeri, le leghe per stato e
 * «Da guardare». Le sezioni si aprono dal menù in alto a sinistra: niente schede doppie.
 */
export function AdminDashboardScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AdminStackParamList>>();
  const { accessToken } = useAuthSession();

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setOverview(null);
      setLoading(false);
      return;
    }
    try {
      setOverview(await fetchAdminOverview(accessToken));
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 403) {
        setError("Non hai i permessi per consultare il pannello operatore.");
      } else {
        setError(getApiErrorMessage(loadError, "Impossibile caricare il pannello operatore."));
      }
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const { refreshing, onRefresh } = useScreenData(load);

  const leagueStates = overview ? formatLeaguesByState(overview.leaguesByState) : "";
  const watchItems = overview?.watch ? buildOperatorWatchItems(overview.watch, new Date()) : null;

  return (
    <PageContainer
      title="Riepilogo"
      testID="screen-admin-dashboard"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading && !overview ? (
        <UiStatePanel
          state="loading"
          title="Caricamento"
          message="Recupero i dati del pannello operatore…"
          testID="admin-dashboard-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Pannello non disponibile"
          message={error}
          testID="admin-dashboard-error"
        />
      ) : null}
      {!error && overview ? (
        <View style={styles.page} testID="admin-dashboard-success">
          <View style={styles.idLine}>
            <Text style={styles.idName} testID="admin-overview-name">
              {overview.operatorDisplayName}
            </Text>
            <Text style={styles.idRole}>operatore</Text>
            <View style={styles.envChip}>
              <Text style={styles.envLabel} testID="admin-overview-environment">
                {overview.environment}
              </Text>
            </View>
          </View>

          <View style={styles.kpis}>
            <View style={styles.kpi}>
              <Text style={styles.kpiValue}>{overview.usersCount}</Text>
              <Text style={styles.kpiLabel}>Utenti</Text>
            </View>
            <View style={styles.kpi}>
              <Text style={styles.kpiValue}>{overview.operatorsCount}</Text>
              <Text style={styles.kpiLabel}>Operatori</Text>
            </View>
            <View style={styles.kpi}>
              <Text style={styles.kpiValue}>{overview.leaguesCount}</Text>
              <Text style={styles.kpiLabel}>Leghe</Text>
            </View>
          </View>
          {leagueStates ? (
            <Text style={styles.states} testID="admin-overview-league-states">
              Leghe: {leagueStates}
            </Text>
          ) : null}

          <Text style={styles.sectionLabel} accessibilityRole="header">
            Da guardare
          </Text>
          {watchItems ? (
            <View style={styles.watch} testID="admin-watch">
              {watchItems.map((row, index) => (
                <Pressable
                  key={row.id}
                  accessibilityRole="link"
                  accessibilityLabel={`${row.title}. ${row.details.join(". ")}`}
                  accessibilityHint={`Apre ${row.targetLabel}`}
                  onPress={() => navigation.navigate(adminScreenForWatchTarget(row.target))}
                  style={({ pressed }) => [
                    styles.row,
                    index > 0 && styles.rowDivider,
                    pressed && styles.rowPressed,
                  ]}
                  testID={`admin-watch-${row.id}`}
                >
                  <View style={[styles.dot, { backgroundColor: toneColor(row.tone) }]} />
                  <View style={styles.rowText}>
                    <Text style={styles.rowTitle}>{row.title}</Text>
                    {row.details.map((detail) => (
                      <Text key={detail} style={styles.rowDetail}>
                        {detail}
                      </Text>
                    ))}
                    <Text style={styles.rowGo}>{row.targetLabel} ›</Text>
                  </View>
                </Pressable>
              ))}
            </View>
          ) : (
            <Text style={styles.states} testID="admin-watch-unavailable">
              Le cose da guardare non sono disponibili in questo momento. Le sezioni restano nel
              menù.
            </Text>
          )}
        </View>
      ) : null}
      {!loading && !error && !overview ? (
        <UiStatePanel
          state="empty"
          title="Nessun dato disponibile"
          message="Non è stato possibile calcolare i conteggi piattaforma."
          testID="admin-dashboard-empty"
        />
      ) : null}
    </PageContainer>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    page: {
      gap: spacing.md,
    },
    idLine: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: spacing.sm,
    },
    idName: {
      color: colors.foreground,
      fontSize: typography.fontSize.md,
      fontWeight: typography.fontWeight.semibold,
    },
    idRole: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
    envChip: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.warning,
    },
    envLabel: {
      color: colors.warning,
      fontSize: typography.fontSize.xs,
      fontWeight: typography.fontWeight.semibold,
    },
    kpis: {
      flexDirection: "row",
      gap: spacing.sm,
    },
    kpi: {
      flex: 1,
      minWidth: 0,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    kpiValue: {
      color: colors.foreground,
      fontFamily: DISPLAY_FONT,
      fontSize: typography.fontSize.xl,
    },
    kpiLabel: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
    states: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
    sectionLabel: {
      marginTop: spacing.xs,
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.xs,
      fontWeight: typography.fontWeight.semibold,
      letterSpacing: 1,
      textTransform: "uppercase",
    },
    watch: {
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
      overflow: "hidden",
    },
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: spacing.sm,
      minHeight: 44,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
    },
    rowDivider: {
      borderTopWidth: 1,
      borderTopColor: colors.border,
    },
    rowPressed: {
      backgroundColor: colors.background,
    },
    dot: {
      width: 10,
      height: 10,
      marginTop: 6,
      borderRadius: 5,
    },
    rowText: {
      flex: 1,
      minWidth: 0,
      gap: 2,
    },
    rowTitle: {
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
    rowDetail: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
    rowGo: {
      alignSelf: "flex-end",
      color: colors.accentMuted,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
  }),
);
