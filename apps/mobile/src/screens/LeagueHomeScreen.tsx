import type {
  LeagueCalendar,
  LeagueDetail,
  LeagueMember,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  fetchLeague,
  fetchLeagueCalendar,
  fetchLeagueMembersPublic,
} from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { LEAGUE_STATE_LABELS } from "../leagues/leagueLabels";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

/** Home lega minima M1 read-only (EP03-UX-02). */
export function LeagueHomeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const route = useRoute<RouteProp<RootStackParamList, "LeagueHome">>();
  const { accessToken, activeLeagueId, can, setActiveLeagueId } = useAuthSession();

  const leagueId = route.params?.leagueId ?? activeLeagueId;

  useEffect(() => {
    if (route.params?.leagueId) {
      setActiveLeagueId(route.params.leagueId);
    }
  }, [route.params?.leagueId, setActiveLeagueId]);

  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [members, setMembers] = useState<LeagueMember[]>([]);
  const [calendar, setCalendar] = useState<LeagueCalendar | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadHome = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!leagueId) {
        setLoading(false);
        setLeague(null);
        setMembers([]);
        setCalendar(null);
        setLoadError(null);
        return;
      }

      if (!accessToken) {
        setLoading(false);
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const [detail, roster, cal] = await Promise.all([
          fetchLeague(accessToken, leagueId),
          fetchLeagueMembersPublic(accessToken, leagueId),
          fetchLeagueCalendar(accessToken, leagueId),
        ]);
        setLeague(detail);
        setMembers(roster);
        setCalendar(cal);
      } catch (error) {
        setLoadError(getApiErrorMessage(error, "Impossibile caricare la home della lega."));
        setLeague(null);
        setMembers([]);
        setCalendar(null);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, leagueId],
  );

  const { refreshing, onRefresh } = useScreenData(loadHome);

  const isAdmin = league?.viewerRole === "league_admin" || can(["league:admin"]);

  return (
    <PageContainer
      title={league?.name ?? "Home lega"}
      testID="screen-league-home"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento home lega"
          message="Recupero contesto, regolamento e partecipanti…"
          testID="league-home-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <View style={styles.section}>
          <UiStatePanel
            state="error"
            title="Home non disponibile"
            message={loadError}
            testID="league-home-error"
          />
          <Pressable
            accessibilityRole="button"
            onPress={() => void loadHome()}
            style={styles.ghostButton}
          >
            <Text style={styles.ghostLabel}>Riprova</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !loadError && !league ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Seleziona una lega dall'elenco oppure entra con un invito."
          testID="league-home-empty"
        />
      ) : null}

      {!loading && !loadError && league ? (
        <View style={styles.content} testID="league-home-content">
          <Text style={styles.heading}>Contesto</Text>
          <Text style={styles.body}>Stato: {LEAGUE_STATE_LABELS[league.state]}</Text>
          <Text style={styles.body}>
            Ruolo:{" "}
            {league.viewerRole === "league_admin" ? "Amministratore" : "Partecipante"}
          </Text>
          <Text style={styles.body}>Stagione: {league.seasonYear}</Text>
          {isAdmin ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("LeagueAdmin", { leagueId: league.id })}
              style={styles.secondaryButton}
              testID="league-home-admin-link"
            >
              <Text style={styles.secondaryLabel}>Amministrazione lega</Text>
            </Pressable>
          ) : null}

          <Text style={styles.heading}>Regolamento</Text>
          {league.rules ? (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Preset {league.rules.presetName}</Text>
              <Text style={styles.body}>
                Partecipanti previsti: {league.rules.participantCount}
              </Text>
              <Text style={styles.body}>Crediti iniziali: {league.rules.totalCredits}</Text>
              <Text style={styles.body}>
                Rosa: {league.rules.roster.rosterSize} giocatori (
                {league.rules.roster.goalkeepers}P-{league.rules.roster.defenders}D-
                {league.rules.roster.midfielders}C-{league.rules.roster.forwards}A)
              </Text>
              <Text style={styles.body}>
                Campionati:{" "}
                {league.competitions.map((row) => row.name).join(", ") || "—"}
              </Text>
            </View>
          ) : (
            <UiStatePanel
              state="empty"
              title="Regolamento non impostato"
              message="L'amministratore deve ancora completare la configurazione."
              testID="league-home-rules-empty"
            />
          )}

          <Text style={styles.heading}>Partecipanti</Text>
          {members.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessun partecipante"
              message="Non risultano iscritti in questa lega."
              testID="league-home-members-empty"
            />
          ) : (
            <View style={styles.list} testID="league-home-members-list">
              {members.map((member) => (
                <Text key={member.userId} style={styles.body}>
                  {member.displayName} ·{" "}
                  {member.role === "league_admin" ? "Amministratore" : "Partecipante"}
                </Text>
              ))}
            </View>
          )}

          <Text style={styles.heading}>Calendario</Text>
          {calendar ? (
            <UiStatePanel
              state="success"
              title="Calendario confermato"
              message={`${calendar.roundCount} giornate · ${calendar.matchupCount} scontri · formato a girone unico.`}
              testID="league-home-calendar"
            />
          ) : (
            <UiStatePanel
              state="empty"
              title="Calendario non disponibile"
              message="Il calendario scontri diretti non è ancora stato generato o confermato."
              testID="league-home-calendar-empty"
            />
          )}

          <Text style={styles.heading}>Prossime fasi</Text>
          <Text style={styles.body}>Funzioni di gioco disponibili dalla prossima fase.</Text>
          <Pressable
            accessibilityRole="button"
            disabled
            style={[styles.ghostButton, styles.disabled]}
            testID="league-home-roster-soon"
          >
            <Text style={styles.ghostLabel}>Rosa — disponibile dalla prossima fase</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled
            style={[styles.ghostButton, styles.disabled]}
            testID="league-home-formation-soon"
          >
            <Text style={styles.ghostLabel}>Formazione — disponibile dalla prossima fase</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled
            style={[styles.ghostButton, styles.disabled]}
            testID="league-home-matchday-soon"
          >
            <Text style={styles.ghostLabel}>Turni — disponibile dalla prossima fase</Text>
          </Pressable>
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.sm,
  },
  section: {
    gap: spacing.sm,
  },
  heading: {
    marginTop: spacing.md,
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: typography.fontWeight.semibold,
  },
  body: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  card: {
    gap: spacing.xs,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
  },
  cardTitle: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  list: {
    gap: spacing.xs,
  },
  secondaryButton: {
    marginTop: spacing.sm,
    minHeight: 44,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  ghostButton: {
    minHeight: 44,
    paddingVertical: spacing.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  ghostLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  disabled: {
    opacity: 0.5,
  },
});
