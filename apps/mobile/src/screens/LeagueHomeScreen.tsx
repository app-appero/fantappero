import { lazyStyles } from "../theme/lazyStyles";
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
import { ScreenTabs } from "../components/ScreenTabs";
import { TeamAvatar } from "../components/TeamAvatar";
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
  const leagueTabs = isAdmin
    ? [
        { id: "league-home", label: "Home lega" },
        { id: "league-admin", label: "Amministrazione lega" },
      ]
    : [{ id: "league-home", label: "Home lega" }];

  return (
    <PageContainer
      title={league?.name ?? "Home lega"}
      testID="screen-league-home"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <ScreenTabs
        items={leagueTabs}
        activeId="league-home"
        onSelect={(id) => {
          if (id === "league-admin" && leagueId) {
            navigation.replace("LeagueAdmin", { leagueId });
          }
        }}
        testID="league-hub-tabs"
      />
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
        <View style={styles.content}>
          <UiStatePanel
            state="empty"
            title="Nessuna lega selezionata"
            message="Scegli una lega dal selettore in alto, creane una o unisciti con un codice invito."
            testID="league-home-empty"
          />
        </View>
      ) : null}

      {!loading && !loadError && league ? (
        <View style={styles.content} testID="league-home-content">
          <View style={styles.hero}>
            <View style={styles.chips}>
              <Text style={[styles.chip, styles.chipState]}>{LEAGUE_STATE_LABELS[league.state]}</Text>
              <Text style={styles.chip}>Stagione {league.seasonYear}</Text>
              <Text style={styles.chip}>
                {league.viewerRole === "league_admin" ? "Amministratore" : "Partecipante"}
              </Text>
            </View>
            <Text style={styles.heroName}>{league.name}</Text>
            <Pressable
              accessibilityRole="button"
              style={styles.primaryButton}
              testID="league-home-formation-link"
              onPress={() => navigation.navigate("MainTabs", { screen: "Formation" })}
            >
              <Text style={styles.primaryLabel}>Imposta la formazione</Text>
            </Pressable>
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
          </View>

          {league.rules ? (
            <View style={styles.stats}>
              {[
                ["Partecipanti", `${members.length}/${league.rules.participantCount}`, `${league.rules.participantMin}–${league.rules.participantMax} consentiti`],
                ["Crediti", `${league.rules.totalCredits}`, "per squadra"],
                ["Rosa", `${league.rules.roster.rosterSize}`, `${league.rules.roster.goalkeepers}P·${league.rules.roster.defenders}D·${league.rules.roster.midfielders}C·${league.rules.roster.forwards}A`],
                ["Campionati", `${league.competitions.length}`, league.competitions.map((row) => row.name).join(" · ") || "—"],
              ].map(([label, value, hint]) => (
                <View key={label} style={styles.stat}>
                  <Text style={styles.statLabel}>{label}</Text>
                  <Text style={styles.statValue}>{value}</Text>
                  <Text style={styles.statHint} numberOfLines={1}>{hint}</Text>
                </View>
              ))}
            </View>
          ) : null}

          <Text style={styles.heading}>Partecipanti</Text>
          {members.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessun partecipante"
              message="Non risultano iscritti in questa lega."
              testID="league-home-members-empty"
            />
          ) : (
            <View style={styles.card} testID="league-home-members-list">
              {members.map((member) => (
                <View key={member.userId} style={styles.memberRow}>
                  <TeamAvatar name={member.displayName} size={40} />
                  <View style={styles.memberText}>
                    <Text style={styles.memberName}>{member.displayName}</Text>
                    <Text style={styles.body}>
                      {member.role === "league_admin" ? "Amministratore" : "Partecipante"}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          )}

          <Text style={styles.heading}>Regolamento</Text>
          {league.rules ? (
            <View style={styles.card}>
              {[
                ["Preset", league.rules.presetName],
                ["Rimborso svincolo", `${league.rules.voluntaryReleaseRefundPercent}%`],
                ["Lock formazione", `${league.rules.lineupLockMarginMinutes} min`],
                ["Scambi", league.rules.options.allowTrades ? "Attivi" : "Disattivati"],
              ].map(([label, value]) => (
                <View key={label} style={styles.ruleRow}>
                  <Text style={styles.body}>{label}</Text>
                  <Text style={styles.ruleValue}>{value}</Text>
                </View>
              ))}
            </View>
          ) : (
            <UiStatePanel
              state="empty"
              title="Regolamento non impostato"
              message="L'amministratore deve ancora completare la configurazione."
              testID="league-home-rules-empty"
            />
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
            style={styles.ghostButton}
            testID="league-home-roster-link"
            onPress={() => navigation.navigate("MainTabs", { screen: "Roster" })}
          >
            <Text style={styles.ghostLabel}>Vai alla rosa</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            style={styles.ghostButton}
            testID="league-home-matchday-link"
            onPress={() => navigation.navigate("MainTabs", { screen: "Matchday" })}
          >
            <Text style={styles.ghostLabel}>Vai ai turni</Text>
          </Pressable>
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
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
  hero: {
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.accentSecondary,
    backgroundColor: colors.backgroundElevated,
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  chip: {
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.background,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    fontWeight: typography.fontWeight.semibold,
  },
  chipState: {
    color: colors.warning,
  },
  heroName: {
    color: colors.foreground,
    fontSize: 40,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
    lineHeight: 42,
  },
  primaryButton: {
    minHeight: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.onBrand,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  stats: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  stat: {
    flexBasis: "47%",
    flexGrow: 1,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  statLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  statValue: {
    color: colors.foreground,
    fontSize: 30,
    fontStyle: "italic",
    fontWeight: "800",
  },
  statHint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  memberRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.xs,
  },
  memberText: {
    flex: 1,
  },
  memberName: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  ruleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
  },
  ruleValue: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  card: {
    gap: spacing.xs,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl,
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
    borderRadius: radius.pill,
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
}));
