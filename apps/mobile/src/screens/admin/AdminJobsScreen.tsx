import type { ConfirmCopy, RunOutcomeLine, RunTone, SystemJob } from "@fantappero/contracts";
import {
  JOBS_INTRO,
  JOBS_POLL_MS,
  RUN_ALL_LABEL,
  RUN_JOB_LABEL,
  jobLastRunLabel,
  jobRunConfirmation,
  jobRunOutcome,
  jobsRunAllConfirmation,
  jobsRunAllSummary,
  jobsRunAllTone,
  jobsSummaryTiles,
  runnableJobs,
} from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { lazyStyles } from "../../theme/lazyStyles";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { fetchSystemJobs, runAllSystemJobs, runSystemJob, updateSystemJob } from "../../api/admin";
import { ApiError } from "../../api/client";
import { RunOutcomeList } from "../../admin/RunOutcomeList";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

type IntervalUnit = "minutes" | "hours" | "days";

const UNIT_SECONDS: Record<IntervalUnit, number> = {
  minutes: 60,
  hours: 3600,
  days: 86400,
};

const UNIT_LABEL: Record<IntervalUnit, string> = {
  minutes: "minuti",
  hours: "ore",
  days: "giorni",
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Mai eseguito";
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

function splitInterval(seconds: number): { amount: string; unit: IntervalUnit } {
  if (seconds % UNIT_SECONDS.days === 0 && seconds >= UNIT_SECONDS.days) {
    return { amount: String(seconds / UNIT_SECONDS.days), unit: "days" };
  }
  if (seconds % UNIT_SECONDS.hours === 0 && seconds >= UNIT_SECONDS.hours) {
    return { amount: String(seconds / UNIT_SECONDS.hours), unit: "hours" };
  }
  return {
    amount: String(Math.max(1, Math.round(seconds / UNIT_SECONDS.minutes))),
    unit: "minutes",
  };
}

const { colors, spacing, typography, radius } = theme;

function progressPercent(job: SystemJob): number {
  if (!job.enabled || !job.lastStartedAt || !job.nextRunAt) {
    return 0;
  }
  const start = new Date(job.lastStartedAt).getTime();
  const end = new Date(job.nextRunAt).getTime();
  if (!(end > start)) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round(((Date.now() - start) / (end - start)) * 100)));
}

type PendingRun = { kind: "one"; job: SystemJob } | { kind: "all" };

type RunReport = {
  title: string;
  summary: string | null;
  tone: RunTone;
  lines: RunOutcomeLine[];
};

/** Un lancio rifiutato o non partito: «già in esecuzione» (409) è un avviso, il resto un errore. */
function runErrorLine(job: SystemJob, error: unknown): RunOutcomeLine {
  const conflict = error instanceof ApiError && error.status === 409;
  return {
    key: job.key,
    title: job.title,
    tone: conflict ? "warning" : "error",
    text: getApiErrorMessage(error, `«${job.title}» non lanciato.`),
  };
}

/** Job periodici — mobile port of `apps/web/src/pages/AdminJobsPage.tsx`. */
export function AdminJobsScreen() {
  const { accessToken } = useAuthSession();
  const [jobs, setJobs] = useState<SystemJob[]>([]);
  const [drafts, setDrafts] = useState<Record<string, { amount: string; unit: IntervalUnit }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pendingRun, setPendingRun] = useState<PendingRun | null>(null);
  const [runBusy, setRunBusy] = useState<string | null>(null);
  const [runReport, setRunReport] = useState<RunReport | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Sessione operatore assente.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await fetchSystemJobs(accessToken);
      setJobs(next);
      setDrafts((current) => {
        const merged = { ...current };
        for (const job of next) {
          if (!merged[job.key]) {
            merged[job.key] = splitInterval(job.intervalSeconds);
          }
        }
        return merged;
      });
    } catch (loadError) {
      setError(getApiErrorMessage(loadError, "Impossibile caricare i job automatici."));
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Rilegge l'elenco senza il «Caricamento…»: serve a vedere «In esecuzione» e l'esito. */
  const refreshJobs = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const next = await fetchSystemJobs(accessToken);
      setJobs(next);
    } catch {
      // L'elenco già a schermo resta com'è: il prossimo giro riprova.
    }
  }, [accessToken]);

  const anyRunning = jobs.some((job) => job.running);
  useEffect(() => {
    if (!anyRunning) {
      return;
    }
    const timer = setInterval(() => void refreshJobs(), JOBS_POLL_MS);
    return () => clearInterval(timer);
  }, [anyRunning, refreshJobs]);

  async function confirmRun() {
    const request = pendingRun;
    setPendingRun(null);
    if (!request || !accessToken) {
      return;
    }
    setRunReport(null);
    if (request.kind === "one") {
      const { job } = request;
      const title = `Lancio di «${job.title}»`;
      setRunBusy(job.key);
      try {
        const line = jobRunOutcome(await runSystemJob(accessToken, job.key));
        setRunReport({ title, summary: null, tone: line.tone, lines: [line] });
      } catch (runError) {
        const line = runErrorLine(job, runError);
        setRunReport({ title, summary: null, tone: line.tone, lines: [line] });
      } finally {
        setRunBusy(null);
      }
    } else {
      setRunBusy("all");
      try {
        const result = await runAllSystemJobs(accessToken);
        setRunReport({
          title: RUN_ALL_LABEL,
          summary: jobsRunAllSummary(result),
          tone: jobsRunAllTone(result),
          lines: result.results.map(jobRunOutcome),
        });
      } catch (runError) {
        setRunReport({
          title: RUN_ALL_LABEL,
          summary: null,
          tone: "error",
          lines: [
            {
              key: "esegui-tutti",
              title: RUN_ALL_LABEL,
              tone: "error",
              text: getApiErrorMessage(runError, "Lancio dei job non riuscito."),
            },
          ],
        });
      } finally {
        setRunBusy(null);
      }
    }
    await refreshJobs();
  }

  const pendingCopy: ConfirmCopy | null =
    pendingRun === null
      ? null
      : pendingRun.kind === "one"
        ? jobRunConfirmation(pendingRun.job)
        : jobsRunAllConfirmation(jobs);

  function replaceJob(updated: SystemJob) {
    setJobs((current) => current.map((job) => (job.key === updated.key ? updated : job)));
    setDrafts((current) => ({ ...current, [updated.key]: splitInterval(updated.intervalSeconds) }));
  }

  async function onToggle(job: SystemJob) {
    if (!accessToken) {
      return;
    }
    setBusyKey(job.key);
    setError(null);
    try {
      replaceJob(await updateSystemJob(accessToken, job.key, { enabled: !job.enabled }));
    } catch (toggleError) {
      setError(getApiErrorMessage(toggleError, "Aggiornamento non riuscito."));
    } finally {
      setBusyKey(null);
    }
  }

  async function onSave(job: SystemJob) {
    if (!accessToken) {
      return;
    }
    const draft = drafts[job.key] ?? splitInterval(job.intervalSeconds);
    const amount = Number(draft.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Inserisci un numero maggiore di zero.");
      return;
    }
    setBusyKey(job.key);
    setError(null);
    try {
      replaceJob(
        await updateSystemJob(accessToken, job.key, {
          intervalSeconds: Math.round(amount * UNIT_SECONDS[draft.unit]),
        }),
      );
    } catch (saveError) {
      setError(getApiErrorMessage(saveError, "Frequenza non aggiornata."));
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <PageContainer title="Job automatici" refreshing={loading} onRefresh={() => void load()}>
      <View style={styles.section} testID="admin-jobs">
        <Text style={styles.sectionTitle}>Cosa parte da solo</Text>
        <Text style={styles.meta}>{JOBS_INTRO}</Text>
        {/* Riepilogo come sul sito (1.5): quanti job sono accesi e quando parte il prossimo. */}
        {!loading && !error && jobs.length > 0 ? (
          <View style={local.tiles} accessibilityLabel="Riepilogo job" testID="admin-jobs-summary">
            {jobsSummaryTiles(jobs).map((tile) => (
              <View key={tile.label} style={local.tile}>
                <Text style={local.timeLabel}>{tile.label}</Text>
                <Text style={local.tileValue}>{tile.value}</Text>
                <Text style={styles.meta}>{tile.hint}</Text>
              </View>
            ))}
          </View>
        ) : null}
        {!loading && !error && jobs.length > 0 ? (
          <View style={styles.rowActions}>
            <Pressable
              style={[
                styles.button,
                (runBusy !== null || runnableJobs(jobs).length === 0) && styles.disabled,
              ]}
              disabled={runBusy !== null || runnableJobs(jobs).length === 0}
              accessibilityRole="button"
              onPress={() => setPendingRun({ kind: "all" })}
              testID="admin-jobs-run-all"
            >
              <Text style={styles.buttonLabel}>{RUN_ALL_LABEL}</Text>
            </Pressable>
          </View>
        ) : null}
        {!loading && !error && jobs.length > 0 ? (
          <Text style={styles.meta}>Lancia ora, una volta sola, tutti i job attivi.</Text>
        ) : null}
        {runReport ? (
          <RunOutcomeList
            title={runReport.title}
            summary={runReport.summary}
            tone={runReport.tone}
            lines={runReport.lines}
            testID="admin-jobs-run-result"
          />
        ) : null}
        {loading ? (
          <UiStatePanel state="loading" title="Caricamento job" message="Lettura dello schedule…" testID="admin-jobs-loading" />
        ) : null}
        {error ? (
          <UiStatePanel state="error" title="Job non disponibili" message={error} testID="admin-jobs-error" />
        ) : null}
        {!loading
          ? jobs.map((job) => {
              const draft = drafts[job.key] ?? splitInterval(job.intervalSeconds);
              const busy = busyKey === job.key;
              return (
                <View
                  key={job.key}
                  style={[local.card, !job.enabled && local.cardOff]}
                  testID={`admin-job-${job.key}`}
                >
                  <View style={local.head}>
                    <View style={local.headText}>
                      <View style={local.titleRow}>
                        <Text style={local.title}>{job.title}</Text>
                        <Text style={[local.chip, job.enabled && local.chipOn]}>
                          {job.enabled ? "Attivo" : "Spento"}
                        </Text>
                      </View>
                      <Text style={styles.meta}>{job.description}</Text>
                    </View>
                    <Switch
                      value={job.enabled}
                      disabled={busy}
                      onValueChange={() => void onToggle(job)}
                      trackColor={{ true: colors.brand, false: colors.border }}
                      thumbColor="#ffffff"
                      accessibilityLabel={`${job.title}: ${job.enabled ? "attivo" : "spento"}`}
                      testID={`admin-job-enabled-${job.key}`}
                    />
                  </View>
                  <View style={local.times}>
                    <View style={local.time}>
                      <Text style={local.timeLabel}>Ultima partenza</Text>
                      <Text style={local.timeValue}>{formatDateTime(job.lastStartedAt)}</Text>
                    </View>
                    <View style={local.time}>
                      <Text style={local.timeLabel}>Prossima partenza</Text>
                      <Text style={[local.timeValue, job.enabled && local.timeNext]}>
                        {job.enabled ? formatDateTime(job.nextRunAt) : "Spento"}
                      </Text>
                    </View>
                  </View>
                  {job.enabled ? (
                    <View style={local.bar}>
                      <View style={[local.barFill, { width: `${progressPercent(job)}%` }]} />
                    </View>
                  ) : null}
                  <View style={local.runRow}>
                    <Pressable
                      style={[styles.secondaryButton, (runBusy !== null || job.running) && styles.disabled]}
                      disabled={runBusy !== null || job.running}
                      accessibilityRole="button"
                      onPress={() => setPendingRun({ kind: "one", job })}
                      testID={`admin-job-run-${job.key}`}
                    >
                      <Text style={styles.secondaryButtonLabel}>{RUN_JOB_LABEL}</Text>
                    </Pressable>
                    {jobLastRunLabel(job) ? (
                      <Text
                        style={[
                          styles.meta,
                          job.running && local.runStatusRunning,
                          !job.running && job.lastRun?.outcome === "failed" && local.runStatusFailed,
                        ]}
                        testID={`admin-job-last-run-${job.key}`}
                      >
                        {jobLastRunLabel(job)}
                        {!job.running && job.lastRun ? ` · ${formatDateTime(job.lastRun.finishedAt)}` : ""}
                      </Text>
                    ) : null}
                  </View>
                  <Text style={local.timeLabel}>Ogni</Text>
                  <TextInput
                    style={styles.input}
                    keyboardType="number-pad"
                    value={draft.amount}
                    editable={!busy}
                    onChangeText={(amount) =>
                      setDrafts((current) => ({ ...current, [job.key]: { ...draft, amount } }))
                    }
                    testID={`admin-job-amount-${job.key}`}
                  />
                  <View style={styles.rowActions}>
                    {(Object.keys(UNIT_LABEL) as IntervalUnit[]).map((unit) => (
                      <Pressable
                        key={unit}
                        style={draft.unit === unit ? styles.button : styles.secondaryButton}
                        disabled={busy}
                        onPress={() =>
                          setDrafts((current) => ({ ...current, [job.key]: { ...draft, unit } }))
                        }
                      >
                        <Text style={draft.unit === unit ? styles.buttonLabel : styles.secondaryButtonLabel}>
                          {UNIT_LABEL[unit]}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                  <Pressable
                    style={[styles.button, busy && styles.disabled]}
                    disabled={busy}
                    onPress={() => void onSave(job)}
                    testID={`admin-job-save-${job.key}`}
                  >
                    <Text style={styles.buttonLabel}>Salva frequenza</Text>
                  </Pressable>
                </View>
              );
            })
          : null}
      </View>
      <ConfirmDialog
        copy={pendingCopy}
        onCancel={() => setPendingRun(null)}
        onConfirm={() => void confirmRun()}
        testID="admin-jobs-confirm"
      />
    </PageContainer>
  );
}

const local = lazyStyles(() => StyleSheet.create({
  tiles: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  tile: {
    flexGrow: 1,
    flexBasis: 130,
    gap: 2,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  tileValue: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: "800",
  },
  card: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    marginTop: spacing.sm,
  },
  cardOff: {
    opacity: 0.8,
  },
  head: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  headText: {
    flex: 1,
    gap: spacing.xs,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
  },
  chip: {
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.pill,
    backgroundColor: colors.background,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    fontWeight: "600",
  },
  chipOn: {
    color: colors.success,
  },
  times: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  time: {
    flexGrow: 1,
    flexBasis: 130,
    padding: spacing.sm,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  timeLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  timeValue: {
    color: colors.foreground,
    fontWeight: "600",
  },
  timeNext: {
    color: colors.accent,
  },
  runRow: {
    gap: spacing.sm,
  },
  runStatusRunning: {
    color: colors.accent,
    fontWeight: "600",
  },
  runStatusFailed: {
    color: colors.danger,
  },
  bar: {
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.border,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    backgroundColor: colors.brand,
  },
}));
