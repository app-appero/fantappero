import type { SystemJob } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { fetchSystemJobs, updateSystemJob } from "../../api/admin";
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

/** Job periodici — mobile port of `apps/web/src/pages/AdminJobsPage.tsx`. */
export function AdminJobsScreen() {
  const { accessToken } = useAuthSession();
  const [jobs, setJobs] = useState<SystemJob[]>([]);
  const [drafts, setDrafts] = useState<Record<string, { amount: string; unit: IntervalUnit }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

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
        <Text style={styles.meta}>
          Puoi spegnerli o cambiare ogni quanto partono. Il beat legge la modifica da solo.
        </Text>
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
                <View key={job.key} testID={`admin-job-${job.key}`}>
                  <Text style={styles.name}>{job.title}</Text>
                  <Text style={styles.meta}>{job.description}</Text>
                  <Pressable
                    style={[styles.secondaryButton, busy && styles.disabled]}
                    disabled={busy}
                    onPress={() => void onToggle(job)}
                    testID={`admin-job-enabled-${job.key}`}
                  >
                    <Text style={styles.secondaryButtonLabel}>{job.enabled ? "Attivo" : "Spento"}</Text>
                  </Pressable>
                  <Text style={styles.meta}>
                    Ultima partenza: {formatDateTime(job.lastStartedAt)}
                  </Text>
                  <Text style={styles.meta}>
                    Prossima partenza: {job.enabled ? formatDateTime(job.nextRunAt) : "Spento"}
                  </Text>
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
    </PageContainer>
  );
}
