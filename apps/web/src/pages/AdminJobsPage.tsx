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
import { fetchSystemJobs, runAllSystemJobs, runSystemJob, updateSystemJob } from "../api/admin";
import { ApiError } from "../api/client";
import { RunConfirmModal } from "../admin/RunConfirmModal";
import { RunOutcomeList } from "../admin/RunOutcomeList";
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

/** «In esecuzione» / «Ultimo giro riuscito (data)» / «Ultimo giro non riuscito: motivo (data)». */
function runStatusLine(job: SystemJob) {
  const label = jobLastRunLabel(job);
  if (!label) {
    return null;
  }
  const when = !job.running && job.lastRun ? ` · ${formatDateTime(job.lastRun.finishedAt)}` : "";
  const modifier = job.running
    ? " fa-job__run-status--running"
    : job.lastRun?.outcome === "failed"
      ? " fa-job__run-status--failed"
      : "";
  return (
    <p
      className={`fa-job__run-status${modifier}`}
      data-testid={`admin-job-last-run-${job.key}`}
      role="status"
    >
      {label}
      {when}
    </p>
  );
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

export function AdminJobsPage() {
  const [jobs, setJobs] = useState<SystemJob[]>([]);
  const [pendingRun, setPendingRun] = useState<PendingRun | null>(null);
  const [runBusy, setRunBusy] = useState<string | null>(null);
  const [runReport, setRunReport] = useState<RunReport | null>(null);
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

  /** Rilegge l'elenco senza il «Caricamento…»: serve a vedere «In esecuzione» e l'esito. */
  const refresh = useCallback(async () => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    try {
      applyJobs(await fetchSystemJobs(session.accessToken));
    } catch {
      // L'elenco già a schermo resta com'è: il prossimo giro riprova.
    }
  }, [applyJobs]);

  const anyRunning = jobs.some((job) => job.running);
  useEffect(() => {
    if (!anyRunning) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), JOBS_POLL_MS);
    return () => window.clearInterval(timer);
  }, [anyRunning, refresh]);

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

  async function confirmRun() {
    const request = pendingRun;
    const session = loadStoredSession();
    setPendingRun(null);
    if (!request || !session?.accessToken) {
      return;
    }
    setRunReport(null);
    if (request.kind === "one") {
      const { job } = request;
      setRunBusy(job.key);
      try {
        const line = jobRunOutcome(await runSystemJob(session.accessToken, job.key));
        setRunReport({ title: `Lancio di «${job.title}»`, summary: null, tone: line.tone, lines: [line] });
      } catch (error) {
        const line = runErrorLine(job, error);
        setRunReport({ title: `Lancio di «${job.title}»`, summary: null, tone: line.tone, lines: [line] });
      } finally {
        setRunBusy(null);
      }
    } else {
      setRunBusy("all");
      try {
        const result = await runAllSystemJobs(session.accessToken);
        setRunReport({
          title: "Esegui tutti",
          summary: jobsRunAllSummary(result),
          tone: jobsRunAllTone(result),
          lines: result.results.map(jobRunOutcome),
        });
      } catch (error) {
        setRunReport({
          title: "Esegui tutti",
          summary: null,
          tone: "error",
          lines: [
            {
              key: "esegui-tutti",
              title: "Esegui tutti",
              tone: "error",
              text: getApiErrorMessage(error, "Lancio dei job non riuscito."),
            },
          ],
        });
      } finally {
        setRunBusy(null);
      }
    }
    await refresh();
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

  const runAllCopy: ConfirmCopy | null = jobsRunAllConfirmation(jobs);
  const pendingCopy: ConfirmCopy | null =
    pendingRun === null
      ? null
      : pendingRun.kind === "one"
        ? jobRunConfirmation(pendingRun.job)
        : runAllCopy;

  return (
    <PageContainer
      title="Job automatici"
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Job automatici" }]} />
      }
    >
      <div className="fa-jobs" data-testid="admin-jobs">
        <p className="fa-jobs__intro">{JOBS_INTRO}</p>
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
          <div className="fa-jobs__toolbar" data-testid="admin-jobs-toolbar">
            <Button
              type="button"
              loading={runBusy === "all"}
              disabled={runBusy !== null || runnableJobs(jobs).length === 0}
              onClick={() => setPendingRun({ kind: "all" })}
              data-testid="admin-jobs-run-all"
            >
              {RUN_ALL_LABEL}
            </Button>
            <span className="fa-jobs__toolbar-hint">
              Lancia ora, una volta sola, tutti i job attivi.
            </span>
          </div>
        ) : null}
        {runReport ? (
          <RunOutcomeList
            title={runReport.title}
            summary={runReport.summary}
            tone={runReport.tone}
            lines={runReport.lines}
            testId="admin-jobs-run-result"
          />
        ) : null}
        {!loading && !loadError && jobs.length > 0 ? (
          <ul className="fa-jobs__tiles" aria-label="Riepilogo job">
            {jobsSummaryTiles(jobs).map((tile) => (
              <li key={tile.label}>
                <span>{tile.label}</span>
                <strong>{tile.value}</strong>
                <small>{tile.hint}</small>
              </li>
            ))}
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
                    <div className="fa-job__run">
                      <Button
                        type="button"
                        variant="secondary"
                        loading={runBusy === job.key}
                        disabled={runBusy !== null || job.running}
                        onClick={() => setPendingRun({ kind: "one", job })}
                        data-testid={`admin-job-run-${job.key}`}
                      >
                        {RUN_JOB_LABEL}
                      </Button>
                      {runStatusLine(job)}
                    </div>
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
      <RunConfirmModal
        copy={pendingCopy}
        onConfirm={() => void confirmRun()}
        onCancel={() => setPendingRun(null)}
        testId="admin-jobs-confirm"
      />
    </PageContainer>
  );
}
