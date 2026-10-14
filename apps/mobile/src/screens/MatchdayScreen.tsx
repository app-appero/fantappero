import { lazyStyles } from "../theme/lazyStyles";
import type {
  FantasyTurnDetail,
  FantasyTurnSummary,
  H2HCalendar,
  PendingFixtureSummary,
} from "@fantappero/contracts";
import {
  TURN_DISPLAY_LABEL,
  mapFixtureMatchStatus,
  resolveDefaultEuropeanTurn,
  resolveTurnDisplayStates,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { liveStringMap } from "../theme/liveColors";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  excludeFantasyTurnFixture,
  fetchFantasyTurn,
  fetchFantasyTurns,
  fetchH2HCalendar,
  fetchPendingFixtures,
} from "../api/leagues";
import { OptionPicker } from "../components/OptionPicker";
import { LockCountdown } from "../components/LockCountdown";
import { StatusBadge } from "../components/StatusBadge";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useLiveH2HPolling } from "../matchday/useLiveH2HPolling";
import { useLiveTurnPolling } from "../matchday/useLiveTurnPolling";
import { useLockCountdown } from "../matchday/useLockCountdown";
import type { RootStackParamList } from "../navigation/types";
import { MatchdayH2HPanel } from "./matchday/MatchdayH2HPanel";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

function groupFixtures<T extends { competitionName?: string | null }>(fixtures: readonly T[]) {
  const groups = new Map<string, T[]>();
  for (const fixture of fixtures) {
    const key = fixture.competitionName ?? "Altre competizioni";
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(fixture);
    } else {
      groups.set(key, [fixture]);
    }
  }
  return groups;
}

const MATCH_STATUS_LABEL: Record<string, string> = {
  scheduled: "In programma",
  live: "In corso",
  finished: "Terminata",
  postponed: "Rinviata",
};

const MATCH_STATUS_COLOR = liveStringMap<string>(() => ({
  scheduled: colors.foregroundMuted,
  live: colors.accent,
  finished: colors.success,
  postponed: colors.warning,
}));

/** Etichetta di stato per la riga lista: include il minuto quando la partita è live. */
function matchRowStatusLabel(statusShort: string, statusElapsed: number | null): string {
  const mapped = mapFixtureMatchStatus(statusShort);
  const base = MATCH_STATUS_LABEL[mapped] ?? statusShort;
  return mapped === "live" && statusElapsed !== null ? `${base} · ${statusElapsed}'` : base;
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

/** Turni — calendario H2H fantallenatori (con dettaglio scontro) + turni europei. */
export function MatchdayScreen() {
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const isAdmin = can(["league:admin"]);
  const canView = can(["matchday:view"]);

  const [tab, setTab] = useState<"calendario" | "europei">("calendario");
  const [h2h, setH2h] = useState<H2HCalendar | null>(null);
  const [h2hLoading, setH2hLoading] = useState(true);
  const [h2hError, setH2hError] = useState<string | null>(null);
  const [turns, setTurns] = useState<FantasyTurnSummary[]>([]);
  const [selected, setSelected] = useState<FantasyTurnDetail | null>(null);

  // Stato mostrato all'utente: posizione del turno rispetto ad adesso, non
  // stato interno del ciclo di vita formazioni.
  const turnDisplayStates = useMemo(() => resolveTurnDisplayStates(turns), [turns]);
  const selectedDisplayState = useMemo(() => {
    const index = turns.findIndex((turn) => turn.id === selected?.id);
    return index >= 0 ? (turnDisplayStates[index] ?? "upcoming") : "upcoming";
  }, [turns, turnDisplayStates, selected?.id]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [pendingFixtures, setPendingFixtures] = useState<PendingFixtureSummary[]>([]);
  const { countdown, refetch: refetchCountdown } = useLockCountdown(accessToken, activeLeagueId);

  const loadH2H = useCallback(async () => {
    if (!canView || !accessToken || !activeLeagueId) {
      setH2hLoading(false);
      setH2h(null);
      setH2hError(null);
      return;
    }
    setH2hLoading(true);
    try {
      setH2h(await fetchH2HCalendar(accessToken, activeLeagueId));
      setH2hError(null);
    } catch (error) {
      setH2h(null);
      setH2hError(getApiErrorMessage(error, "Calendario H2H non disponibile."));
    } finally {
      setH2hLoading(false);
    }
  }, [accessToken, activeLeagueId, canView]);

  const { degraded: h2hLiveDegraded } = useLiveH2HPolling(
    accessToken,
    activeLeagueId,
    h2h,
    setH2h,
    tab === "calendario",
  );

  useLiveTurnPolling(accessToken, activeLeagueId, selected, setSelected, tab === "europei");

  const loadTurns = useCallback(async () => {
    if (!canView) {
      setLoading(false);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
      setTurns([]);
      setSelected(null);
      return;
    }
    if (!accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const list = await fetchFantasyTurns(accessToken, activeLeagueId);
      setTurns(list);
      const defaultTurn = resolveDefaultEuropeanTurn(list);
      if (!defaultTurn) {
        setSelected(null);
      } else {
        const detail = await fetchFantasyTurn(accessToken, activeLeagueId, defaultTurn.id);
        setSelected(detail);
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i turni."));
      setTurns([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId, canView]);

  const loadPendingFixtures = useCallback(async () => {
    if (!accessToken || !activeLeagueId) {
      setPendingFixtures([]);
      return;
    }
    try {
      setPendingFixtures(await fetchPendingFixtures(accessToken, activeLeagueId));
    } catch {
      setPendingFixtures([]);
    }
  }, [accessToken, activeLeagueId]);

  useEffect(() => {
    void loadH2H();
    void loadTurns();
    void loadPendingFixtures();
  }, [loadH2H, loadTurns, loadPendingFixtures]);

  if (!canView) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso alla consultazione dei turni."
          testID="matchday-forbidden"
        />
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="loading"
          title="Caricamento turni"
          message="Recupero del calendario europeo in corso…"
          testID="matchday-loading"
        />
      </PageContainer>
    );
  }

  if (loadError) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="error"
          title="Turni non disponibili"
          message={loadError}
          testID="matchday-error"
        />
        <Pressable style={styles.button} onPress={() => void loadTurns()} testID="matchday-reload">
          <Text style={styles.buttonLabel}>Ricarica</Text>
        </Pressable>
      </PageContainer>
    );
  }

  if (!activeLeagueId) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare i turni europei."
          testID="matchday-no-league"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Turni" testID="screen-matchday">
      <View style={styles.stack}>
        <View style={styles.chipRow} testID="matchday-tabs">
          <Pressable
            style={[styles.chip, tab === "calendario" ? styles.chipActive : null]}
            onPress={() => setTab("calendario")}
            testID="matchday-tab-calendario"
          >
            <Text style={styles.chipLabel}>Calendario fantallenatori</Text>
          </Pressable>
          <Pressable
            style={[styles.chip, tab === "europei" ? styles.chipActive : null]}
            onPress={() => setTab("europei")}
            testID="matchday-tab-europei"
          >
            <Text style={styles.chipLabel}>Turni europei</Text>
          </Pressable>
        </View>

        {tab === "calendario" ? (
          <View testID="matchday-h2h">
            <MatchdayH2HPanel
              calendar={h2h}
              loading={h2hLoading}
              error={h2hError}
              liveDegraded={h2hLiveDegraded}
              canAdmin={isAdmin}
              onRetry={() => void loadH2H()}
              onOpenAdmin={() =>
                navigation.navigate("LeagueAdmin", { leagueId: activeLeagueId ?? undefined })
              }
              onOpenMatchup={(slotId) => navigation.navigate("MatchupDetail", { slotId })}
            />
          </View>
        ) : null}

        {tab === "europei" ? (
          <>

        {turns.length === 0 ? (
          <UiStatePanel
            state="empty"
            title="Nessun turno ancora"
            message="I Turni Europei seguono le finestre del calendario multi-campionato. La copertura formazione resta obbligatoria quando le rose sono assegnate: completa le rose in Partecipanti per sbloccare il calendario fantallenatori."
            testID="matchday-empty"
          />
        ) : (
          <View style={styles.section} testID="matchday-turn-list">
            <OptionPicker
              label="Turno europeo"
              value={selected?.id ?? ""}
              options={turns.map((turn, index) => ({
                value: turn.id,
                label: `Turno ${turn.number} — ${TURN_DISPLAY_LABEL[turnDisplayStates[index] ?? "upcoming"]}`,
              }))}
              onChange={(turnId) => {
                if (!accessToken || !activeLeagueId) {
                  return;
                }
                setBusy(true);
                void fetchFantasyTurn(accessToken, activeLeagueId, turnId)
                  .then(setSelected)
                  .catch((error) =>
                    setActionError(getApiErrorMessage(error, "Dettaglio non disponibile.")),
                  )
                  .finally(() => setBusy(false));
              }}
              testID="matchday-turn-select"
            />
          </View>
        )}

        {selected ? (
          <View style={styles.section} testID="matchday-turn-detail">
            <Text style={styles.heading}>Turno {selected.number}</Text>
            <Text style={styles.body}>Stato: {TURN_DISPLAY_LABEL[selectedDisplayState]}</Text>
            <Text style={styles.body}>Cutoff: {formatDateTime(selected.cutoffAt)}</Text>
            {countdown && countdown.roundId === selected.id ? (
              <LockCountdown
                state={countdown.state}
                nextLockAt={countdown.nextLockAt}
                onExpire={refetchCountdown}
              />
            ) : null}
            {selected.fixtures.some((fixture) => fixture.lockLatchedAt) ? (
              <Text style={styles.body} testID="matchday-cutoff-latch">
                Un rinvio non sblocca le partite il cui kickoff originale è già trascorso. Le mosse
                già usate restano consumate.
              </Text>
            ) : null}
            {[...groupFixtures(selected.fixtures).entries()].map(([competition, fixtures]) => (
              <View key={competition} style={styles.competition} testID={`matchday-competition-${competition}`}>
                <Text style={styles.competitionTitle}>{competition}</Text>
                {fixtures.map((fixture) => {
                  const played = fixture.homeGoals !== null && fixture.awayGoals !== null;
                  const mapped = mapFixtureMatchStatus(fixture.statusShort);
                  return (
                    <View key={fixture.id} style={styles.fixtureCard}>
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={`${fixture.homeClubName} contro ${fixture.awayClubName}, dettaglio partita`}
                        onPress={() =>
                          navigation.navigate("FixtureDetail", {
                            turnId: selected.id,
                            fixtureId: fixture.fixtureId,
                          })
                        }
                        testID={`matchday-fixture-link-${fixture.fixtureId}`}
                      >
                        <View style={styles.fixtureTeams}>
                          <Text style={styles.fixtureTeam} numberOfLines={2}>
                            {fixture.homeClubName}
                          </Text>
                          <Text style={styles.fixtureScore}>
                            {played ? `${fixture.homeGoals} - ${fixture.awayGoals}` : "vs"}
                          </Text>
                          <Text style={[styles.fixtureTeam, styles.fixtureTeamAway]} numberOfLines={2}>
                            {fixture.awayClubName}
                          </Text>
                        </View>
                        <View style={styles.fixtureMeta}>
                          <Text style={styles.hint}>
                            {formatDateTime(fixture.kickoffAt)}
                            {fixture.lockLatchedAt ? " · bloccata" : ""}
                          </Text>
                          <StatusBadge
                            label={matchRowStatusLabel(fixture.statusShort, fixture.statusElapsed)}
                            color={MATCH_STATUS_COLOR[mapped] ?? colors.foregroundMuted}
                            textColor={colors.accentContrast}
                            testID={`matchday-fixture-status-${fixture.fixtureId}`}
                          />
                        </View>
                      </Pressable>
                      <Text style={styles.hint} testID={`matchday-fixture-feed-${fixture.fixtureId}`}>
                        {fixture.feedStateLabel}
                        {fixture.updatedAt
                          ? ` · aggiornata ${formatDateTime(fixture.updatedAt)}`
                          : ""}
                      </Text>
                      {isAdmin && selected.modificationAllowed ? (
                        <Pressable
                          style={styles.ghostButton}
                          disabled={busy}
                          onPress={() => {
                            if (!accessToken) {
                              return;
                            }
                            setBusy(true);
                            setActionError(null);
                            void excludeFantasyTurnFixture(accessToken, activeLeagueId, selected.id, {
                              fixtureId: fixture.fixtureId,
                            })
                              .then(async (detail) => {
                                setSelected(detail);
                                setActionMessage("Partita esclusa dal turno.");
                                await loadTurns();
                              })
                              .catch((error) =>
                                setActionError(getApiErrorMessage(error, "Esclusione non consentita.")),
                              )
                              .finally(() => setBusy(false));
                          }}
                          testID={`matchday-exclude-${fixture.fixtureId}`}
                        >
                          <Text style={styles.ghostLabel}>Escludi</Text>
                        </Pressable>
                      ) : null}
                    </View>
                  );
                })}
              </View>
            ))}
          </View>
        ) : null}

        {pendingFixtures.length > 0 ? (
          <View style={styles.section} testID="matchday-pending-fixtures">
            <Text style={styles.heading}>Partite da aggiornare</Text>
            <Text style={styles.body}>
              Il provider conosce già competizione e squadre di queste partite, ma non ancora
              data e ora definitive: verranno inserite automaticamente in un turno non appena
              pubblicate.
            </Text>
            {pendingFixtures.map((fixture) => (
              <Text
                key={fixture.fixtureId}
                style={styles.body}
                testID={`pending-fixture-${fixture.fixtureId}`}
              >
                {fixture.homeClubName} – {fixture.awayClubName}
                {fixture.competitionName ? ` · ${fixture.competitionName}` : ""}
                {fixture.roundLabel ? ` · ${fixture.roundLabel}` : ""}
              </Text>
            ))}
          </View>
        ) : null}

        {actionMessage ? <Text style={styles.success} testID="matchday-success">{actionMessage}</Text> : null}
        {actionError ? (
          <UiStatePanel
            state="error"
            title="Operazione non riuscita"
            message={actionError}
            testID="matchday-action-error"
          />
        ) : null}
          </>
        ) : null}
      </View>
    </PageContainer>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  stack: {
    gap: spacing.md,
  },
  section: {
    gap: spacing.sm,
  },
  heading: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: "700",
  },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
  },
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    padding: spacing.sm,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chipActive: {
    borderColor: colors.accent,
  },
  chipLabel: {
    color: colors.foreground,
  },
  button: {
    backgroundColor: colors.brand,
    borderRadius: radius.pill,
    padding: spacing.sm,
    alignItems: "center",
  },
  buttonLabel: {
    color: colors.onBrand,
    fontWeight: "600",
  },
  disabled: {
    opacity: 0.6,
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    padding: spacing.sm,
    alignItems: "center",
  },
  secondaryLabel: {
    color: colors.foreground,
  },
  competition: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  competitionTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
  },
  fixtureCard: {
    gap: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  fixtureTeams: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  fixtureTeam: {
    flex: 1,
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  fixtureTeamAway: {
    textAlign: "right",
  },
  fixtureScore: {
    minWidth: 52,
    textAlign: "center",
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
  },
  fixtureMeta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  ghostButton: {
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  ghostLabel: {
    color: colors.danger,
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    color: colors.foreground,
  },
  success: {
    color: colors.foreground,
  },
}));
