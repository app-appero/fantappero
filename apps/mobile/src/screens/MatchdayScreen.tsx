import type {
  AiLineupRun,
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
  openFantasyTurn,
  recalculateFantasyTurnCutoff,
  refreshFullCalendar,
  runAiLineups,
} from "../api/leagues";
import { StatusBadge } from "../components/StatusBadge";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useLiveH2HPolling } from "../matchday/useLiveH2HPolling";
import { useLiveTurnPolling } from "../matchday/useLiveTurnPolling";
import type { RootStackParamList } from "../navigation/types";
import { MatchdayH2HPanel } from "./matchday/MatchdayH2HPanel";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

const MATCH_STATUS_LABEL: Record<string, string> = {
  scheduled: "In programma",
  live: "In corso",
  finished: "Terminata",
  postponed: "Rinviata",
};

const MATCH_STATUS_COLOR: Record<string, string> = {
  scheduled: colors.foregroundMuted,
  live: colors.accent,
  finished: colors.success,
  postponed: colors.warning,
};

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
  const [aiLineupBusy, setAiLineupBusy] = useState(false);
  const [aiLineupRun, setAiLineupRun] = useState<AiLineupRun | null>(null);
  const [aiLineupError, setAiLineupError] = useState<string | null>(null);
  const [pendingFixtures, setPendingFixtures] = useState<PendingFixtureSummary[]>([]);
  const [refreshingCalendar, setRefreshingCalendar] = useState(false);
  const [calendarRefreshProgress, setCalendarRefreshProgress] = useState<{
    percent: number;
    stage: string;
    message: string;
  } | null>(null);
  const [calendarRefreshError, setCalendarRefreshError] = useState<string | null>(null);
  const [calendarRefreshSuccess, setCalendarRefreshSuccess] = useState<string | null>(null);

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

  async function generateAiLineups(roundId: string) {
    if (!accessToken || !activeLeagueId) {
      return;
    }
    setAiLineupBusy(true);
    setAiLineupError(null);
    try {
      setAiLineupRun(await runAiLineups(accessToken, activeLeagueId, roundId, false));
      await loadH2H();
    } catch (error) {
      setAiLineupError(getApiErrorMessage(error, "Generazione delle formazioni AI non riuscita."));
    } finally {
      setAiLineupBusy(false);
    }
  }

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
              aiLineupBusy={aiLineupBusy}
              aiLineupRun={aiLineupRun}
              aiLineupError={aiLineupError}
              onGenerateAiLineups={(roundId) => void generateAiLineups(roundId)}
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
        {isAdmin ? (
          <View style={styles.section} testID="matchday-admin">
            <Text style={styles.heading}>Calendario turni</Text>
            <Text style={styles.body}>
              Il sistema raggruppa automaticamente le partite dei campionati scelti in turni
              weekend e infrasettimanali, dall&apos;inizio alla fine della stagione. Usa il
              pulsante per sincronizzare il calendario dal provider e riallineare la numerazione
              dei turni.
            </Text>
            <Pressable
              style={[styles.button, refreshingCalendar && styles.disabled]}
              disabled={refreshingCalendar}
              onPress={() => {
                if (!accessToken) {
                  return;
                }
                setRefreshingCalendar(true);
                setCalendarRefreshError(null);
                setCalendarRefreshSuccess(null);
                setCalendarRefreshProgress({ percent: 0, stage: "queued", message: "Avvio in corso…" });
                void refreshFullCalendar(accessToken, activeLeagueId, {
                  onProgress: (progress) =>
                    setCalendarRefreshProgress({
                      percent: progress.percent,
                      stage: progress.stage,
                      message: progress.message,
                    }),
                })
                  .then(async (result) => {
                    setCalendarRefreshSuccess(result.message);
                    await loadTurns();
                    await loadPendingFixtures();
                  })
                  .catch((error) =>
                    setCalendarRefreshError(
                      getApiErrorMessage(error, "Aggiornamento calendario non riuscito."),
                    ),
                  )
                  .finally(() => {
                    setRefreshingCalendar(false);
                    setCalendarRefreshProgress(null);
                  });
              }}
              testID="matchday-refresh-calendar"
            >
              <Text style={styles.buttonLabel}>Aggiorna calendario</Text>
            </Pressable>
            {refreshingCalendar ? (
              <UiStatePanel
                state="loading"
                title="Aggiornamento in corso"
                message={
                  calendarRefreshProgress
                    ? `${calendarRefreshProgress.message} (${calendarRefreshProgress.percent}%)`
                    : "Avvio in corso…"
                }
                testID="matchday-refresh-progress"
              />
            ) : null}
            {!refreshingCalendar && calendarRefreshError ? (
              <UiStatePanel
                state="error"
                title="Aggiornamento non riuscito"
                message={calendarRefreshError}
                testID="matchday-refresh-error"
              />
            ) : null}
            {!refreshingCalendar && calendarRefreshSuccess ? (
              <UiStatePanel
                state="success"
                title="Calendario aggiornato"
                message={calendarRefreshSuccess}
                testID="matchday-refresh-success"
              />
            ) : null}
          </View>
        ) : null}

        {turns.length === 0 ? (
          <UiStatePanel
            state="empty"
            title="Nessun turno ancora"
            message="Un turno esiste solo se ogni fantallenatore può schierare la formazione con i giocatori della propria rosa. Finché le rose non sono assegnate (asta non ancora svolta) il calendario resta vuoto: si popolerà da solo subito dopo."
            testID="matchday-empty"
          />
        ) : (
          <View style={styles.section} testID="matchday-turn-list">
            {turns.map((turn, index) => (
              <Pressable
                key={turn.id}
                style={styles.chip}
                onPress={() => {
                  if (!accessToken) {
                    return;
                  }
                  setBusy(true);
                  void fetchFantasyTurn(accessToken, activeLeagueId, turn.id)
                    .then(setSelected)
                    .catch((error) =>
                      setActionError(getApiErrorMessage(error, "Dettaglio non disponibile.")),
                    )
                    .finally(() => setBusy(false));
                }}
                testID={`matchday-turn-${turn.number}`}
              >
                <Text style={styles.chipLabel}>
                  Turno {turn.number} —{" "}
                  {TURN_DISPLAY_LABEL[turnDisplayStates[index] ?? "upcoming"]}
                </Text>
              </Pressable>
            ))}
          </View>
        )}

        {selected ? (
          <View style={styles.section} testID="matchday-turn-detail">
            <Text style={styles.heading}>Turno {selected.number}</Text>
            <Text style={styles.body}>Stato: {TURN_DISPLAY_LABEL[selectedDisplayState]}</Text>
            <Text style={styles.body}>Cutoff: {formatDateTime(selected.cutoffAt)}</Text>
            {selected.fixtures.some((fixture) => fixture.lockLatchedAt) ? (
              <Text style={styles.body} testID="matchday-cutoff-latch">
                Un rinvio non sblocca le partite il cui kickoff originale è già trascorso. Le mosse
                già usate restano consumate.
              </Text>
            ) : null}
            {selected.fixtures.map((fixture) => (
              <View key={fixture.id} style={styles.fixtureRow}>
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
                  <Text style={styles.body}>
                    {fixture.homeClubName} – {fixture.awayClubName} (
                    {formatDateTime(fixture.kickoffAt)})
                    {fixture.homeGoals !== null && fixture.awayGoals !== null
                      ? ` · ${fixture.homeGoals}-${fixture.awayGoals}`
                      : ""}
                    {fixture.lockLatchedAt ? " — bloccata" : ""}
                  </Text>
                  <StatusBadge
                    label={matchRowStatusLabel(fixture.statusShort, fixture.statusElapsed)}
                    color={
                      MATCH_STATUS_COLOR[mapFixtureMatchStatus(fixture.statusShort)] ??
                      colors.foregroundMuted
                    }
                    textColor={colors.accentContrast}
                    testID={`matchday-fixture-status-${fixture.fixtureId}`}
                  />
                </Pressable>
                <Text style={styles.hint} testID={`matchday-fixture-feed-${fixture.fixtureId}`}>
                  {fixture.feedStateLabel}
                  {fixture.updatedAt
                    ? ` · ultimo aggiornamento ${formatDateTime(fixture.updatedAt)}`
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
            ))}
            {isAdmin && selected.status === "scheduled" ? (
              <Pressable
                style={styles.button}
                disabled={busy}
                onPress={() => {
                  if (!accessToken) {
                    return;
                  }
                  setBusy(true);
                  void openFantasyTurn(accessToken, activeLeagueId, selected.id)
                    .then((detail) => {
                      setSelected(detail);
                      setActionMessage(`Turno ${detail.number} aperto.`);
                      return loadTurns();
                    })
                    .catch((error) =>
                      setActionError(getApiErrorMessage(error, "Apertura non riuscita.")),
                    )
                    .finally(() => setBusy(false));
                }}
                testID="matchday-open"
              >
                <Text style={styles.buttonLabel}>Apri turno</Text>
              </Pressable>
            ) : null}
            {isAdmin && selected.status !== "skipped" ? (
              <Pressable
                style={styles.secondaryButton}
                disabled={busy}
                onPress={() => {
                  if (!accessToken) {
                    return;
                  }
                  setBusy(true);
                  void recalculateFantasyTurnCutoff(accessToken, activeLeagueId, selected.id)
                    .then((detail) => {
                      setSelected(detail);
                      setActionMessage("Cutoff aggiornato.");
                    })
                    .catch((error) =>
                      setActionError(getApiErrorMessage(error, "Ricalcolo non riuscito.")),
                    )
                    .finally(() => setBusy(false));
                }}
                testID="matchday-recalc"
              >
                <Text style={styles.secondaryLabel}>Ricalcola cutoff</Text>
              </Pressable>
            ) : null}
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

const styles = StyleSheet.create({
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
    borderRadius: radius.md,
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
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: "600",
  },
  disabled: {
    opacity: 0.6,
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
  fixtureRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  ghostButton: {
    borderRadius: radius.md,
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
});
