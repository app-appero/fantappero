import type { AdminSeasonHistoryEstimate, AdminSeasonHistoryProgress } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import {
  INVALID_SEASON_YEAR_MESSAGE,
  START_IMPORT_CANCEL_LABEL,
  START_IMPORT_CONFIRM_LABEL,
  START_IMPORT_CONFIRM_TITLE,
  currentSeasonYear,
  estimateHeadline,
  estimateSeasonLines,
  failedJobText,
  isSeasonHistoryJobActive,
  marketValuesText,
  parseSeasonYearInput,
  pollSeasonHistoryJob,
  progressFromStart,
  progressText,
  resultLines,
  startImportConfirmMessage,
  type SeasonHistoryApi,
} from "../../admin/seasonHistory";
import {
  estimateSeasonHistoryImport,
  fetchActiveSeasonHistoryImport,
  fetchSeasonHistoryImportProgress,
  refreshMarketValues,
  startSeasonHistoryImport,
} from "../../api/admin";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { ProgressBar } from "../../components/ProgressBar";
import { UiStatePanel } from "../../components/UiStatePanel";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import { lazyStyles } from "../../theme/lazyStyles";

/**
 * Pannello operatore → Listone → «Storico stagioni» (1.3): conto delle chiamate, import una
 * tantum delle due stagioni passate dal fornitore con avanzamento, ricalcolo di medie e Valore
 * (`docs/operations/valore_di_mercato_e_storico.md`). Solo operatori (`global:operate`), come
 * il resto del pannello. L'avanzamento si segue solo con la schermata in primo piano.
 */
export function AdminSeasonHistoryCard() {
  const { accessToken, can } = useAuthSession();
  const isOperator = can(["global:operate"]);
  const [seasonText, setSeasonText] = useState(() => String(currentSeasonYear()));
  const [estimate, setEstimate] = useState<AdminSeasonHistoryEstimate | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [progress, setProgress] = useState<AdminSeasonHistoryProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshingValues, setRefreshingValues] = useState(false);
  const [valuesMessage, setValuesMessage] = useState<string | null>(null);
  // Job da seguire; cambiando `watchToken` l'effetto di focus riparte e lo segue.
  const jobIdRef = useRef<string | null>(null);
  const [watchToken, setWatchToken] = useState(0);

  const api = useMemo<SeasonHistoryApi | null>(
    () =>
      accessToken
        ? {
            estimate: (seasonYear) => estimateSeasonHistoryImport(accessToken, seasonYear),
            start: (seasonYear) => startSeasonHistoryImport(accessToken, seasonYear),
            fetchActive: () => fetchActiveSeasonHistoryImport(accessToken),
            fetchProgress: (jobId) => fetchSeasonHistoryImportProgress(accessToken, jobId),
            refreshValues: (seasonYear) => refreshMarketValues(accessToken, seasonYear),
          }
        : null,
    [accessToken],
  );

  // Con la schermata in primo piano: riprende l'import in corso (anche avviato da un altro
  // operatore) e ne segue l'avanzamento; perdendo il focus smette di chiedere.
  useFocusEffect(
    useCallback(() => {
      if (!api || !isOperator) {
        return undefined;
      }
      let stopped = false;
      void (async () => {
        try {
          let jobId = jobIdRef.current;
          if (!jobId) {
            const active = await api.fetchActive();
            if (stopped || !active) {
              return;
            }
            setProgress(active);
            if (!isSeasonHistoryJobActive(active.status)) {
              return;
            }
            jobId = active.jobId;
            jobIdRef.current = jobId;
          }
          const final = await pollSeasonHistoryJob({
            jobId,
            fetchProgress: api.fetchProgress,
            onUpdate: setProgress,
            shouldStop: () => stopped,
          });
          if (final) {
            jobIdRef.current = null;
          }
        } catch (pollError) {
          if (!stopped) {
            jobIdRef.current = null;
            setError(getApiErrorMessage(pollError, "Impossibile leggere l'avanzamento dell'import."));
          }
        }
      })();
      return () => {
        stopped = true;
      };
    }, [api, isOperator, watchToken]),
  );

  if (!isOperator) {
    return null;
  }

  const running = progress !== null && isSeasonHistoryJobActive(progress.status);
  const busy = estimating || starting || running;

  function readSeasonYear(): number | null {
    const year = parseSeasonYearInput(seasonText);
    if (year === null) {
      setError(INVALID_SEASON_YEAR_MESSAGE);
    }
    return year;
  }

  async function loadEstimate(seasonYear: number): Promise<AdminSeasonHistoryEstimate | null> {
    if (!api) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return null;
    }
    setEstimating(true);
    setError(null);
    try {
      const response = await api.estimate(seasonYear);
      setEstimate(response.estimate);
      return response.estimate;
    } catch (estimateError) {
      setError(getApiErrorMessage(estimateError, "Impossibile calcolare le chiamate."));
      return null;
    } finally {
      setEstimating(false);
    }
  }

  async function onEstimate() {
    const seasonYear = readSeasonYear();
    if (seasonYear !== null) {
      await loadEstimate(seasonYear);
    }
  }

  async function startImport(seasonYear: number) {
    if (!api) {
      return;
    }
    setStarting(true);
    setError(null);
    setValuesMessage(null);
    try {
      const response = await api.start(seasonYear);
      setEstimate(response.estimate);
      const initial = progressFromStart(response);
      if (initial) {
        jobIdRef.current = initial.jobId;
        setProgress(initial);
        setWatchToken((token) => token + 1);
      }
    } catch (startError) {
      setError(getApiErrorMessage(startError, "Impossibile avviare l'import dello storico."));
    } finally {
      setStarting(false);
    }
  }

  async function onStart() {
    const seasonYear = readSeasonYear();
    if (seasonYear === null) {
      return;
    }
    // La conferma dice quante chiamate costa: se manca il conto di questa stagione, prima lo chiede.
    const known = estimate && estimate.seasonYear === seasonYear ? estimate : await loadEstimate(seasonYear);
    if (!known) {
      return;
    }
    Alert.alert(START_IMPORT_CONFIRM_TITLE, startImportConfirmMessage(seasonYear, known), [
      { text: START_IMPORT_CANCEL_LABEL, style: "cancel" },
      { text: START_IMPORT_CONFIRM_LABEL, onPress: () => void startImport(seasonYear) },
    ]);
  }

  async function onRefreshValues() {
    const seasonYear = readSeasonYear();
    if (seasonYear === null || !api) {
      return;
    }
    setRefreshingValues(true);
    setError(null);
    setValuesMessage(null);
    try {
      setValuesMessage(marketValuesText(await api.refreshValues(seasonYear)));
    } catch (refreshError) {
      setError(getApiErrorMessage(refreshError, "Impossibile ricalcolare i valori."));
    } finally {
      setRefreshingValues(false);
    }
  }

  return (
    <View style={styles.section} testID="admin-season-history-card">
      <Text style={styles.sectionTitle}>Storico stagioni</Text>
      <Text style={styles.meta}>
        Scarica una volta dal fornitore le due stagioni passate (medie, presenze, gol) per la scheda
        calciatore, la media stagionale e il Valore di mercato.
      </Text>
      <View style={local.seasonRow}>
        <View style={local.seasonField}>
          <Text style={styles.meta}>Stagione in corso</Text>
          <TextInput
            style={styles.input}
            value={seasonText}
            onChangeText={(value) => {
              setSeasonText(value);
              setError(null);
              // Il conto mostrato è di un'altra stagione: va rifatto.
              setEstimate(null);
            }}
            keyboardType="numeric"
            maxLength={4}
            accessibilityLabel="Anno della stagione in corso"
            testID="admin-season-history-year"
          />
        </View>
      </View>
      <View style={styles.rowActions}>
        <Pressable
          style={[styles.secondaryButton, busy && styles.disabled]}
          disabled={busy}
          onPress={() => void onEstimate()}
          testID="admin-season-history-estimate"
        >
          <Text style={styles.secondaryButtonLabel}>{estimating ? "Calcolo…" : "Calcola chiamate"}</Text>
        </Pressable>
        <Pressable
          style={[styles.button, busy && styles.disabled]}
          disabled={busy}
          onPress={() => void onStart()}
          testID="admin-season-history-start"
        >
          <Text style={styles.buttonLabel}>{starting ? "Avvio…" : "Avvia import"}</Text>
        </Pressable>
        <Pressable
          style={[styles.secondaryButton, (refreshingValues || running) && styles.disabled]}
          disabled={refreshingValues || running}
          onPress={() => void onRefreshValues()}
          testID="admin-season-history-refresh-values"
        >
          <Text style={styles.secondaryButtonLabel}>{refreshingValues ? "Ricalcolo…" : "Ricalcola valori"}</Text>
        </Pressable>
      </View>

      {estimate ? (
        <View style={local.estimate} testID="admin-season-history-estimate-result">
          <Text style={local.estimateHeadline}>{estimateHeadline(estimate)}</Text>
          {estimateSeasonLines(estimate).map((line) => (
            <Text key={line} style={styles.meta}>
              {line}
            </Text>
          ))}
        </View>
      ) : null}

      {running && progress ? (
        <View style={{ gap: 6 }} testID="admin-season-history-progress">
          <Text style={styles.meta}>{progressText(progress)}</Text>
          <ProgressBar percent={progress.percent} />
        </View>
      ) : null}
      {progress?.status === "completed" && progress.result ? (
        <UiStatePanel
          state="success"
          title="Storico importato"
          message={resultLines(progress.result).join("\n")}
          testID="admin-season-history-done"
        />
      ) : null}
      {progress?.status === "failed" ? (
        <UiStatePanel
          state="error"
          title="Import non riuscito"
          message={failedJobText(progress)}
          testID="admin-season-history-failed"
        />
      ) : null}
      {valuesMessage ? (
        <UiStatePanel state="success" title="Valori ricalcolati" message={valuesMessage} testID="admin-market-values-done" />
      ) : null}
      {error ? (
        <UiStatePanel state="error" title="Operazione non riuscita" message={error} testID="admin-season-history-error" />
      ) : null}
    </View>
  );
}

const local = lazyStyles(() =>
  StyleSheet.create({
    seasonRow: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: theme.spacing.sm,
    },
    seasonField: {
      width: 140,
      gap: theme.spacing.xs,
    },
    estimate: {
      gap: 2,
      padding: theme.spacing.sm,
      borderRadius: theme.radius.md,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    estimateHeadline: {
      color: theme.colors.foreground,
      fontSize: theme.typography.fontSize.sm,
      fontWeight: theme.typography.fontWeight.semibold,
    },
  }),
);
