import type { SystemJob } from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
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

/** Quanto manca alla prossima partenza, in percentuale tra ultima e prossima esecuzione. */
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

function formatTimeUntil(value: string | null): string {
  if (!value) {
    return "—";
  }
  const minutes = Math.round((new Date(value).getTime() - Date.now()) / 60000);
  if (minutes <= 0) {
    return "ora";
  }
  if (minutes < 60) {
    return `${minutes} min`;
  }
  if (minutes < 1440) {
    return `${Math.round(minutes / 60)} h`;
  }
  return `${Math.round(minutes / 1440)} g`;
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
      <div className="fa-jobs" data-testid="admin-jobs">
        <p className="fa-jobs__intro">
          Questi giri non aspettano un pulsante. Puoi spegnerli o cambiare ogni quanto partono: il
          beat legge la modifica da solo, senza un nuovo deploy. La prossima partenza è calcolata
          dall’ultima esecuzione più la frequenza.
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
        {!loading && !loadError && jobs.length > 0 ? (
          <ul className="fa-jobs__tiles" aria-label="Riepilogo job">
            <li>
              <span>Attivi</span>
              <strong>
                {jobs.filter((job) => job.enabled).length} / {jobs.length}
              </strong>
              <small>{jobs.filter((job) => !job.enabled).length === 1 ? "1 spento" : `${jobs.filter((job) => !job.enabled).length} spenti`}</small>
            </li>
            {(() => {
              const next = jobs
                .filter((job) => job.enabled && job.nextRunAt)
                .sort((x, y) => new Date(x.nextRunAt as string).getTime() - new Date(y.nextRunAt as string).getTime())[0];
              return (
                <li>
                  <span>Prossimo giro</span>
                  <strong>{next ? formatTimeUntil(next.nextRunAt) : "—"}</strong>
                  <small>{next ? next.title : "Nessun job attivo"}</small>
                </li>
              );
            })()}
          </ul>
        ) : null}
        <div className="fa-jobs__grid">
          {!loading && !loadError
            ? jobs.map((job) => {
                const fallback = splitInterval(job.intervalSeconds);
                const draft = drafts[job.key] ?? { amount: String(fallback.amount), unit: fallback.unit };
                const busy = rowBusy === job.key;
                return (
                  <article
                    key={job.key}
                    data-testid={`admin-job-${job.key}`}
                    className={job.enabled ? "fa-job" : "fa-job fa-job--off"}
                  >
                    <header className="fa-job__head">
                      <div>
                        <h3 className="fa-job__title">
                          {job.title}{" "}
                          <span className={job.enabled ? "fa-job__chip fa-job__chip--on" : "fa-job__chip"}>
                            {job.enabled ? "Attivo" : "Spento"}
                          </span>
                        </h3>
                        <p className="fa-job__desc">{job.description}</p>
                      </div>
                      <Switch
                        checked={job.enabled}
                        disabled={busy}
                        onCheckedChange={(enabled) => void onToggle(job, enabled)}
                        statusLabel={job.enabled ? "Attivo" : "Spento"}
                        ariaLabel={`${job.title}: ${job.enabled ? "attivo" : "spento"}`}
                        testId={`admin-job-enabled-${job.key}`}
                      />
                    </header>
                    <div className="fa-job__times">
                      <div>
                        <span>Ultima partenza</span>
                        <strong>{formatDateTime(job.lastStartedAt)}</strong>
                      </div>
                      <div className={job.enabled ? "fa-job__next" : undefined}>
                        <span>Prossima partenza</span>
                        <strong>{job.enabled ? formatDateTime(job.nextRunAt) : "Spento"}</strong>
                      </div>
                    </div>
                    {job.enabled ? (
                      <div
                        className="fa-job__bar"
                        role="progressbar"
                        aria-label="Tempo alla prossima partenza"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={progressPercent(job)}
                      >
                        <span style={{ width: `${progressPercent(job)}%` }} />
                      </div>
                    ) : null}
                    <div className="fa-job__form">
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
                    <p className="fa-job__range">
                      Ammesso tra {formatBound(job.minIntervalSeconds)} e {formatBound(job.maxIntervalSeconds)}.
                    </p>
                  </article>
                );
              })
            : null}
        </div>
      </div>
    </PageContainer>
  );
}
