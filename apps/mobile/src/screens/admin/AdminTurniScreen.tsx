import type { AdminLeagueTurnStatus } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import {
  calculateCurrentRoundsAllLeagues,
  fetchAdminLeagueTurnStatus,
  generateAllAiLineups,
  repairHistoricalRounds,
  syncAllLeagueTurns,
  syncCalendarForAllLeagues,
} from "../../api/admin";
import { ApiError } from "../../api/client";
import {
  calculateCurrentRound,
  openFantasyTurn,
  recalculateFantasyTurnCutoff,
  runAiLineups,
} from "../../api/leagues";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

const { colors } = theme;

const ROUND_STATUS_LABEL: Record<string, string> = {
  scheduled: "Programmato",
  open: "Aperto",
  locked: "Chiuso",
  skipped: "Non disputato",
};

const HOMOLOGATION_LABEL: Record<string, string> = {
  provisional: "Provvisorio",
  homologated: "Omologato",
};

const COMMAND_LEGEND: { label: string; description: string }[] = [
  {
    label: "Sincronizza turni",
    description: "Apre i turni pronti e ricalcola i cutoff per tutte le leghe attive.",
  },
  {
    label: "Genera calendario",
    description:
      "Sincronizza partite, date e Turni Europei con il provider e riallinea il calendario della lega.",
  },
  {
    label: "Genera formazioni IA",
    description:
      "Genera automaticamente le formazioni esclusivamente per gli utenti/squadre gestiti dall'AI secondo le regole previste.",
  },
  {
    label: "Calcola giornata corrente",
    description:
      "Calcola punteggi, risultati e classifica della giornata corrente utilizzando le formazioni disponibili (con fallback per quelle mancanti).",
  },
  {
    label: "Ricalcola storico",
    description:
      "Riapre (se serve, motivo obbligatorio) e ricalcola i turni con formazioni mai risolte nello storico. Può correggere turni già omologati.",
  },
];

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

/**
 * Pannello operatore — turni, calendario, formazioni IA, calcolo giornata
 * (EP-turni-automazione / EP-turni-calcolo). Mobile port di
 * `apps/web/src/pages/AdminTurniPage.tsx`.
 */
export function AdminTurniScreen() {
  const { accessToken } = useAuthSession();

  const [leagues, setLeagues] = useState<AdminLeagueTurnStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");

  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [rowMessage, setRowMessage] = useState<string | null>(null);

  const [syncingTurns, setSyncingTurns] = useState(false);
  const [turnsResult, setTurnsResult] = useState<string | null>(null);
  const [turnsError, setTurnsError] = useState<string | null>(null);

  const [generatingLineups, setGeneratingLineups] = useState(false);
  const [lineupsResult, setLineupsResult] = useState<string | null>(null);
  const [lineupsError, setLineupsError] = useState<string | null>(null);

  const [syncingCalendar, setSyncingCalendar] = useState(false);
  const [calendarProgress, setCalendarProgress] = useState<{
    percent: number;
    message: string;
  } | null>(null);
  const [calendarResult, setCalendarResult] = useState<string | null>(null);
  const [calendarError, setCalendarError] = useState<string | null>(null);

  const [calculatingRounds, setCalculatingRounds] = useState(false);
  const [calculateResult, setCalculateResult] = useState<string | null>(null);
  const [calculateError, setCalculateError] = useState<string | null>(null);

  const [repairReason, setRepairReason] = useState("");
  const [repairingHistory, setRepairingHistory] = useState(false);
  const [repairProgress, setRepairProgress] = useState<{
    percent: number;
    message: string;
  } | null>(null);
  const [repairResult, setRepairResult] = useState<string | null>(null);
  const [repairError, setRepairError] = useState<string | null>(null);

  const visibleLeagues = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) {
      return leagues;
    }
    return leagues.filter(
      (league) =>
        league.leagueName.toLowerCase().includes(trimmed) ||
        league.leagueId.toLowerCase().includes(trimmed),
    );
  }, [leagues, query]);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      if (!accessToken) {
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        setLoading(false);
        return;
      }
      try {
        setLeagues(await fetchAdminLeagueTurnStatus(accessToken));
      } catch (error) {
        if (error instanceof ApiError && error.status === 403) {
          setLoadError("Non hai i permessi per consultare il pannello turni.");
        } else {
          setLoadError(getApiErrorMessage(error, "Impossibile caricare lo stato delle leghe."));
        }
        setLeagues([]);
      } finally {
        setLoading(false);
      }
    },
    [accessToken],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await load({ silent: true });
    } finally {
      setRefreshing(false);
    }
  }, [load]);

  async function onSyncTurns() {
    if (!accessToken) {
      return;
    }
    setSyncingTurns(true);
    setTurnsError(null);
    setTurnsResult(null);
    try {
      const result = await syncAllLeagueTurns(accessToken);
      setTurnsResult(
        `Leghe: ${result.leagues}. Turni creati: ${result.created}, aperti: ${result.opened}, ` +
          `aggiornati: ${result.upgraded}, in attesa: ${result.waiting}.`,
      );
      await load();
    } catch (error) {
      setTurnsError(getApiErrorMessage(error, "Sincronizzazione turni non riuscita."));
    } finally {
      setSyncingTurns(false);
    }
  }

  async function onGenerateLineups() {
    if (!accessToken) {
      return;
    }
    setGeneratingLineups(true);
    setLineupsError(null);
    setLineupsResult(null);
    try {
      const result = await generateAllAiLineups(accessToken);
      setLineupsResult(
        `Turni processati: ${result.rounds}. Squadre aggiornate: ${result.teamsUpdated}, ` +
          `invariate: ${result.teamsSkipped}.`,
      );
    } catch (error) {
      setLineupsError(getApiErrorMessage(error, "Generazione formazioni IA non riuscita."));
    } finally {
      setGeneratingLineups(false);
    }
  }

  async function onSyncCalendar() {
    if (!accessToken) {
      return;
    }
    setSyncingCalendar(true);
    setCalendarError(null);
    setCalendarResult(null);
    setCalendarProgress({ percent: 0, message: "Avvio in corso…" });
    try {
      const result = await syncCalendarForAllLeagues(accessToken, {
        onProgress: (progress) =>
          setCalendarProgress({ percent: progress.percent, message: progress.message }),
      });
      setCalendarResult(
        `Leghe attive: ${result.leagues}, aggiornate: ${result.refreshed}, fallite: ${result.failed}. ` +
          `Fixture nuove: ${result.fixturesCreated}, aggiornate: ${result.fixturesUpdated}.`,
      );
      await load();
    } catch (error) {
      setCalendarError(getApiErrorMessage(error, "Aggiornamento calendario massivo non riuscito."));
    } finally {
      setSyncingCalendar(false);
      setCalendarProgress(null);
    }
  }

  async function onCalculateRounds() {
    if (!accessToken) {
      return;
    }
    setCalculatingRounds(true);
    setCalculateError(null);
    setCalculateResult(null);
    try {
      const result = await calculateCurrentRoundsAllLeagues(accessToken);
      setCalculateResult(
        `Turni considerati: ${result.roundsConsidered}, elaborati: ${result.roundsProcessed}, ` +
          `omologati: ${result.roundsFinalized}. Partite valutate: ${result.fixturesScored}.`,
      );
      await load();
    } catch (error) {
      setCalculateError(getApiErrorMessage(error, "Calcolo giornata corrente non riuscito."));
    } finally {
      setCalculatingRounds(false);
    }
  }

  async function onRepairHistory() {
    if (!accessToken || !repairReason.trim()) {
      return;
    }
    setRepairingHistory(true);
    setRepairError(null);
    setRepairResult(null);
    setRepairProgress({ percent: 0, message: "Avvio in corso…" });
    try {
      const result = await repairHistoricalRounds(accessToken, repairReason.trim(), {
        onProgress: (progress) =>
          setRepairProgress({ percent: progress.percent, message: progress.message }),
      });
      setRepairResult(
        `Leghe attive: ${result.leagues}, turni con un buco storico: ${result.roundsConsidered}, ` +
          `riparati: ${result.roundsRepaired}, falliti: ${result.roundsFailed}.`,
      );
      await load();
    } catch (error) {
      setRepairError(getApiErrorMessage(error, "Ricalcolo storico non riuscito."));
    } finally {
      setRepairingHistory(false);
      setRepairProgress(null);
    }
  }

  async function onGenerateRoundLineups(leagueId: string, roundId: string) {
    if (!accessToken) {
      return;
    }
    setRowBusy(`lineups-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      const run = await runAiLineups(accessToken, leagueId, roundId, false);
      setRowMessage(run.summary);
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Generazione formazioni IA non riuscita."));
    } finally {
      setRowBusy(null);
    }
  }

  async function onCalculateRound(leagueId: string, roundId: string) {
    if (!accessToken) {
      return;
    }
    setRowBusy(`calculate-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      const result = await calculateCurrentRound(accessToken, leagueId, roundId);
      setRowMessage(
        result.homologated
          ? `Turno ${result.roundNumber} calcolato e omologato.`
          : `Turno ${result.roundNumber} calcolato (dati non ancora definitivi).`,
      );
      await load();
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Calcolo giornata non riuscito."));
    } finally {
      setRowBusy(null);
    }
  }

  async function onOpenRound(leagueId: string, roundId: string) {
    if (!accessToken) {
      return;
    }
    setRowBusy(`open-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      const detail = await openFantasyTurn(accessToken, leagueId, roundId);
      setRowMessage(`Turno ${detail.number} aperto.`);
      await load();
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Apertura turno non riuscita."));
    } finally {
      setRowBusy(null);
    }
  }

  async function onRecalculateCutoff(leagueId: string, roundId: string) {
    if (!accessToken) {
      return;
    }
    setRowBusy(`recalc-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      await recalculateFantasyTurnCutoff(accessToken, leagueId, roundId);
      setRowMessage("Cutoff aggiornato dagli orari correnti.");
      await load();
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Ricalcolo cutoff non riuscito."));
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <PageContainer
      title="Turni"
      testID="screen-admin-turni"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <View style={styles.section} testID="admin-turni-legend">
        <Text style={styles.sectionTitle}>Cosa fanno questi comandi?</Text>
        {COMMAND_LEGEND.map((item) => (
          <View key={item.label}>
            <Text style={styles.name}>{item.label}</Text>
            <Text style={styles.meta}>{item.description}</Text>
          </View>
        ))}
      </View>

      <View style={styles.section} testID="admin-turni-massive">
        <Text style={styles.sectionTitle}>Azioni massive — tutte le leghe attive</Text>
        <View style={styles.rowActions}>
          <Pressable
            style={[styles.button, syncingTurns && styles.disabled]}
            disabled={syncingTurns}
            onPress={() => void onSyncTurns()}
            testID="admin-turni-sync-all"
          >
            <Text style={styles.buttonLabel}>Sincronizza turni</Text>
          </Pressable>
          <Pressable
            style={[styles.secondaryButton, syncingCalendar && styles.disabled]}
            disabled={syncingCalendar}
            onPress={() => void onSyncCalendar()}
            testID="admin-turni-calendar-sync-all"
          >
            <Text style={styles.secondaryButtonLabel}>Genera calendario</Text>
          </Pressable>
          <Pressable
            style={[styles.secondaryButton, generatingLineups && styles.disabled]}
            disabled={generatingLineups}
            onPress={() => void onGenerateLineups()}
            testID="admin-turni-lineups-all"
          >
            <Text style={styles.secondaryButtonLabel}>Genera formazioni IA</Text>
          </Pressable>
          <Pressable
            style={[styles.secondaryButton, calculatingRounds && styles.disabled]}
            disabled={calculatingRounds}
            onPress={() => void onCalculateRounds()}
            testID="admin-turni-calculate-all"
          >
            <Text style={styles.secondaryButtonLabel}>Calcola giornata corrente</Text>
          </Pressable>
        </View>

        {turnsResult ? (
          <UiStatePanel state="success" title="Turni sincronizzati" message={turnsResult} testID="admin-turni-sync-all-success" />
        ) : null}
        {turnsError ? (
          <UiStatePanel state="error" title="Sincronizzazione non riuscita" message={turnsError} testID="admin-turni-sync-all-error" />
        ) : null}

        {syncingCalendar ? (
          <UiStatePanel
            state="loading"
            title="Aggiornamento calendario in corso"
            message={calendarProgress ? `${calendarProgress.message} (${calendarProgress.percent}%)` : "Avvio in corso…"}
            testID="admin-turni-calendar-sync-all-progress"
          />
        ) : null}
        {!syncingCalendar && calendarResult ? (
          <UiStatePanel state="success" title="Calendario aggiornato" message={calendarResult} testID="admin-turni-calendar-sync-all-success" />
        ) : null}
        {!syncingCalendar && calendarError ? (
          <UiStatePanel state="error" title="Aggiornamento non riuscito" message={calendarError} testID="admin-turni-calendar-sync-all-error" />
        ) : null}

        {lineupsResult ? (
          <UiStatePanel state="success" title="Formazioni IA generate" message={lineupsResult} testID="admin-turni-lineups-all-success" />
        ) : null}
        {lineupsError ? (
          <UiStatePanel state="error" title="Generazione non riuscita" message={lineupsError} testID="admin-turni-lineups-all-error" />
        ) : null}

        {calculateResult ? (
          <UiStatePanel state="success" title="Giornata calcolata" message={calculateResult} testID="admin-turni-calculate-all-success" />
        ) : null}
        {calculateError ? (
          <UiStatePanel state="error" title="Calcolo non riuscito" message={calculateError} testID="admin-turni-calculate-all-error" />
        ) : null}
      </View>

      <View style={styles.section} testID="admin-turni-repair">
        <Text style={styles.sectionTitle}>Ricalcola storico</Text>
        <Text style={styles.meta}>
          Riapre (se serve) e ricalcola i turni con formazioni mai risolte nello storico — azione
          rara, distinta dal calcolo di routine: può correggere turni già omologati e invia
          notifiche di correzione agli utenti coinvolti. Richiede un motivo.
        </Text>
        <TextInput
          style={styles.input}
          value={repairReason}
          onChangeText={setRepairReason}
          placeholder="Motivo della correzione"
          testID="admin-turni-repair-reason"
        />
        <Pressable
          style={[styles.secondaryButton, (repairingHistory || !repairReason.trim()) && styles.disabled]}
          disabled={repairingHistory || !repairReason.trim()}
          onPress={() => void onRepairHistory()}
          testID="admin-turni-repair-all"
        >
          <Text style={styles.secondaryButtonLabel}>Ricalcola storico</Text>
        </Pressable>

        {repairingHistory ? (
          <UiStatePanel
            state="loading"
            title="Ricalcolo storico in corso"
            message={repairProgress ? `${repairProgress.message} (${repairProgress.percent}%)` : "Avvio in corso…"}
            testID="admin-turni-repair-all-progress"
          />
        ) : null}
        {!repairingHistory && repairResult ? (
          <UiStatePanel state="success" title="Storico ricalcolato" message={repairResult} testID="admin-turni-repair-all-success" />
        ) : null}
        {!repairingHistory && repairError ? (
          <UiStatePanel state="error" title="Ricalcolo non riuscito" message={repairError} testID="admin-turni-repair-all-error" />
        ) : null}
      </View>

      <View style={styles.section} testID="admin-turni-leagues">
        <Text style={styles.sectionTitle}>Leghe attive</Text>

        {rowMessage ? (
          <UiStatePanel state="success" title="Azione completata" message={rowMessage} testID="admin-turni-row-success" />
        ) : null}
        {rowError ? (
          <UiStatePanel state="error" title="Azione non riuscita" message={rowError} testID="admin-turni-row-error" />
        ) : null}

        {loading ? (
          <UiStatePanel state="loading" title="Caricamento leghe" message="Recupero stato turni…" testID="admin-turni-loading" />
        ) : null}
        {!loading && loadError ? (
          <UiStatePanel
            state={loadError.includes("permessi") ? "forbidden" : "error"}
            title="Leghe non disponibili"
            message={loadError}
            testID="admin-turni-load-error"
          />
        ) : null}
        {!loading && !loadError && leagues.length === 0 ? (
          <UiStatePanel state="empty" title="Nessuna lega attiva" message="Non ci sono leghe in stato attivo al momento." testID="admin-turni-empty" />
        ) : null}
        {!loading && !loadError && leagues.length > 0 ? (
          <TextInput
            style={styles.input}
            value={query}
            onChangeText={setQuery}
            placeholder="Cerca per nome o id lega"
            autoCapitalize="none"
            autoCorrect={false}
            testID="admin-turni-search"
          />
        ) : null}
        {!loading && !loadError && leagues.length > 0 && visibleLeagues.length === 0 ? (
          <UiStatePanel state="empty" title="Nessuna lega corrisponde" message="Nessuna lega attiva corrisponde alla ricerca." testID="admin-turni-search-empty" />
        ) : null}

        {visibleLeagues.map((league) => (
          <View key={league.leagueId} style={styles.listRow} testID={`admin-turni-row-${league.leagueId}`}>
            <Text style={styles.name}>{league.leagueName}</Text>
            <Text style={styles.meta}>
              {league.currentRoundNumber != null ? `Turno ${league.currentRoundNumber}` : "—"}
            </Text>
            <View style={styles.rowActions}>
              {league.currentRoundStatus ? (
                <StatusBadge
                  label={ROUND_STATUS_LABEL[league.currentRoundStatus] ?? league.currentRoundStatus}
                  color={colors.foregroundMuted}
                  textColor={colors.accentContrast}
                />
              ) : null}
              {league.homologationStatus ? (
                <StatusBadge
                  label={HOMOLOGATION_LABEL[league.homologationStatus] ?? league.homologationStatus}
                  color={league.homologationStatus === "homologated" ? colors.success : colors.warning}
                  textColor={colors.accentContrast}
                />
              ) : null}
            </View>
            <Text style={styles.meta}>
              Calendario aggiornato: {formatDateTime(league.calendarUpdatedAt)}
            </Text>
            {league.currentRoundId ? (
              <View style={styles.rowActions}>
                <Pressable
                  style={[
                    styles.secondaryButton,
                    (rowBusy !== null || league.currentRoundStatus !== "scheduled") && styles.disabled,
                  ]}
                  disabled={rowBusy !== null || league.currentRoundStatus !== "scheduled"}
                  onPress={() => void onOpenRound(league.leagueId, league.currentRoundId as string)}
                  testID={`admin-turni-open-${league.leagueId}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Apri turno</Text>
                </Pressable>
                <Pressable
                  style={[
                    styles.secondaryButton,
                    (rowBusy !== null || league.currentRoundStatus === "skipped") && styles.disabled,
                  ]}
                  disabled={rowBusy !== null || league.currentRoundStatus === "skipped"}
                  onPress={() => void onRecalculateCutoff(league.leagueId, league.currentRoundId as string)}
                  testID={`admin-turni-recalc-${league.leagueId}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Ricalcola cutoff</Text>
                </Pressable>
                <Pressable
                  style={[styles.secondaryButton, rowBusy !== null && styles.disabled]}
                  disabled={rowBusy !== null}
                  onPress={() => void onGenerateRoundLineups(league.leagueId, league.currentRoundId as string)}
                  testID={`admin-turni-lineups-${league.leagueId}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Formazioni IA</Text>
                </Pressable>
                <Pressable
                  style={[styles.secondaryButton, rowBusy !== null && styles.disabled]}
                  disabled={rowBusy !== null}
                  onPress={() => void onCalculateRound(league.leagueId, league.currentRoundId as string)}
                  testID={`admin-turni-calculate-${league.leagueId}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Calcola giornata corrente</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        ))}
      </View>
    </PageContainer>
  );
}
