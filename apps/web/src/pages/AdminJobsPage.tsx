import type { SystemJob } from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  PageContainer,
  Select,
  Switch,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchSystemJobs, updateSystemJob } from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

type IntervalUnit = "minutes" | "hours" | "days";

const UNIT_SECONDS: Record<IntervalUnit, number> = {
  minutes: 60,
  hours: 3600,
  days: 86400,
};

const UNIT_OPTIONS = [
  { value: "minutes", label: "minuti" },
  { value: "hours", label: "ore" },
  { value: "days", label: "giorni" },
];

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

function splitInterval(seconds: number): { amount: number; unit: IntervalUnit } {
  if (seconds % UNIT_SECONDS.days === 0 && seconds >= UNIT_SECONDS.days) {
    return { amount: seconds / UNIT_SECONDS.days, unit: "days" };
  }
  if (seconds % UNIT_SECONDS.hours === 0 && seconds >= UNIT_SECONDS.hours) {
    return { amount: seconds / UNIT_SECONDS.hours, unit: "hours" };
  }
  return { amount: Math.max(1, Math.round(seconds / UNIT_SECONDS.minutes)), unit: "minutes" };
}

function formatBound(seconds: number): string {
  const { amount, unit } = splitInterval(seconds);
  const label = UNIT_OPTIONS.find((option) => option.value === unit)?.label ?? unit;
  return `${amount} ${label}`;
}

export function AdminJobsPage() {
  const [jobs, setJobs] = useState<SystemJob[]>([]);
  const [drafts, setDrafts] = useState<Record<string, { amount: string; unit: IntervalUnit }>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const applyJobs = useCallback((next: SystemJob[]) => {
    setJobs(next);
    setDrafts((current) => {
      const merged = { ...current };
      for (const job of next) {
        if (merged[job.key]) {
          continue;
        }
        const split = splitInterval(job.intervalSeconds);
        merged[job.key] = { amount: String(split.amount), unit: split.unit };
      }
      return merged;
    });
  }, []);

  const load = useCallback(async () => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setLoadError("Sessione operatore assente.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      applyJobs(await fetchSystemJobs(session.accessToken));
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i job automatici."));
    } finally {
      setLoading(false);
    }
  }, [applyJobs]);

  useEffect(() => {
    void load();
  }, [load]);

  function replaceJob(updated: SystemJob) {
    setJobs((current) => current.map((job) => (job.key === updated.key ? updated : job)));
    const split = splitInterval(updated.intervalSeconds);
    setDrafts((current) => ({
      ...current,
      [updated.key]: { amount: String(split.amount), unit: split.unit },
    }));
  }

  async function onToggle(job: SystemJob, enabled: boolean) {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setRowBusy(job.key);
    setRowError(null);
    try {
      replaceJob(await updateSystemJob(session.accessToken, job.key, { enabled }));
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Aggiornamento non riuscito."));
    } finally {
      setRowBusy(null);
    }
  }

  async function onSaveInterval(job: SystemJob) {
    const session = loadStoredSession();
    const draft = drafts[job.key];
    if (!session?.accessToken || !draft) {
      return;
    }
    const amount = Number(draft.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setRowError("Inserisci un numero maggiore di zero.");
      return;
    }
    const intervalSeconds = Math.round(amount * UNIT_SECONDS[draft.unit]);
    setRowBusy(job.key);
    setRowError(null);
    try {
      replaceJob(await updateSystemJob(session.accessToken, job.key, { intervalSeconds }));
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Frequenza non aggiornata."));
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <PageContainer
      title="Job automatici"
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Job automatici" }]} />
      }
    >
      <Card data-testid="admin-jobs">
        <CardHeader title="Cosa parte da solo" />
        <CardBody>
          <p>
            Questi giri non aspettano un pulsante. Puoi spegnerli o cambiare ogni quanto
            partono: il beat legge la modifica da solo, senza un nuovo deploy. La prossima
            partenza è calcolata dall’ultima esecuzione più la frequenza.
          </p>
          {loading ? (
            <UiStatePanel state="loading" title="Caricamento job" message="Lettura dello schedule…" testId="admin-jobs-loading" />
          ) : null}
          {loadError ? (
            <UiStatePanel state="error" title="Job non disponibili" message={loadError} testId="admin-jobs-error" />
          ) : null}
          {rowError ? (
            <UiStatePanel state="error" title="Modifica non salvata" message={rowError} testId="admin-jobs-row-error" />
          ) : null}
          {!loading && !loadError
            ? jobs.map((job) => {
                const draft = drafts[job.key] ?? splitInterval(job.intervalSeconds);
                const busy = rowBusy === job.key;
                return (
                  <article key={job.key} data-testid={`admin-job-${job.key}`} style={{ marginTop: 16 }}>
                    <h3 style={{ marginBottom: 4 }}>{job.title}</h3>
                    <p style={{ marginTop: 0 }}>{job.description}</p>
                    <Switch
                      checked={job.enabled}
                      disabled={busy}
                      onCheckedChange={(enabled) => void onToggle(job, enabled)}
                      statusLabel={job.enabled ? "Attivo" : "Spento"}
                      ariaLabel={`${job.title}: ${job.enabled ? "attivo" : "spento"}`}
                      testId={`admin-job-enabled-${job.key}`}
                    />
                    <p>
                      Ultima partenza: {formatDateTime(job.lastStartedAt)}
                      {" · "}
                      Prossima partenza: {job.enabled ? formatDateTime(job.nextRunAt) : "Spento"}
                    </p>
                    <div className="fa-ds-showcase__row">
                      <Input
                        label="Ogni"
                        name={`admin-job-amount-${job.key}`}
                        type="number"
                        min={1}
                        value={String(draft.amount)}
                        disabled={busy}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [job.key]: { ...draft, amount: event.target.value },
                          }))
                        }
                        data-testid={`admin-job-amount-${job.key}`}
                      />
                      <Select
                        label="Unità"
                        options={UNIT_OPTIONS}
                        value={draft.unit}
                        disabled={busy}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [job.key]: {
                              ...draft,
                              unit: event.target.value as IntervalUnit,
                            },
                          }))
                        }
                        data-testid={`admin-job-unit-${job.key}`}
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        loading={busy}
                        disabled={busy}
                        onClick={() => void onSaveInterval(job)}
                        data-testid={`admin-job-save-${job.key}`}
                      >
                        Salva frequenza
                      </Button>
                    </div>
                    <p className="fa-matchday-hint">
                      Ammesso tra {formatBound(job.minIntervalSeconds)} e {formatBound(job.maxIntervalSeconds)}.
                    </p>
                  </article>
                );
              })
            : null}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
