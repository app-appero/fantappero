import type {
  AdminMarketValuesRefreshResult,
  AdminSeasonHistoryEstimate,
  AdminSeasonHistoryProgress,
  AdminSeasonHistoryResult,
  AdminSeasonHistoryStopReason,
} from "@fantappero/contracts";
import { Button, Card, CardBody, CardHeader, Input, ProgressBar, UiStatePanel } from "@fantappero/ui";
import { useEffect, useState } from "react";
import {
  fetchActiveAdminSeasonHistory,
  fetchAdminSeasonHistoryProgress,
  importAdminSeasonHistory,
  refreshAdminMarketValues,
} from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { fullSeasonLabel } from "../market/athleteValue";

/** Ogni quanto si legge l'avanzamento mentre l'import gira (pochi secondi). */
export const SEASON_HISTORY_POLL_MS = 3000;

/** Migliaia col punto anche a 4 cifre («1.650», come nella documentazione). */
const NUMBER = {
  format: (value: number): string =>
    String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, "."),
};

const STOP_REASON_LABEL: Record<AdminSeasonHistoryStopReason, string> = {
  max_calls: "raggiunto il tetto di chiamate di questa esecuzione",
  quota_reserve:
    "la quota giornaliera del fornitore è scesa sotto il 15% (resta per i giri live): rilancia domani",
  too_many_errors: "troppi errori di fila dal fornitore: riprova più tardi",
};

function isRunning(progress: AdminSeasonHistoryProgress | null): boolean {
  return progress !== null && (progress.status === "queued" || progress.status === "running");
}

function seasonsLabel(estimate: AdminSeasonHistoryEstimate): string {
  return estimate.seasons.map((season) => fullSeasonLabel(season.seasonYear)).join(" e ");
}

function callsLabel(calls: number): string {
  return calls === 1 ? "1 chiamata" : `${NUMBER.format(calls)} chiamate`;
}

function minutesLabel(minutes: number): string {
  return minutes <= 1 ? "circa 1 minuto" : `circa ${NUMBER.format(minutes)} minuti`;
}

function resultSummary(result: AdminSeasonHistoryResult): string {
  const parts = [
    result.message,
    `Chiamate: ${NUMBER.format(result.calls)} · righe nuove: ${NUMBER.format(result.rowsCreated)} · aggiornate: ${NUMBER.format(result.rowsUpdated)} · errori: ${NUMBER.format(result.errors)}.`,
  ];
  if (result.marketValues) {
    parts.push(`Valori ricalcolati: ${NUMBER.format(result.marketValues.athletesValued)} calciatori.`);
  }
  return parts.filter(Boolean).join(" ");
}

function valuesSummary(result: AdminMarketValuesRefreshResult): string {
  if (result.skipped) {
    return "Niente da ricalcolare: voti, storico e listone non sono cambiati dall'ultima volta.";
  }
  return `Valore calcolato per ${NUMBER.format(result.athletesValued)} calciatori: ${NUMBER.format(result.athletesWithCurrentAverage)} con la media di quest'anno, ${NUMBER.format(result.athletesWithPreviousAverage)} con quella della stagione scorsa, ${NUMBER.format(result.athletesWithHistory)} con lo storico.`;
}

/**
 * «Storico stagioni» nel Listone del pannello operatore (1.3, `docs/operations/
 * valore_di_mercato_e_storico.md`): prima il conto delle chiamate al fornitore (nessuna
 * chiamata), poi l'import con conferma e l'avanzamento ogni pochi secondi; «Ricalcola valori»
 * rifà subito medie e Valore. La pagina è già solo per gli operatori (`global:operate`).
 */
export function SeasonHistoryPanel({ defaultSeasonYear }: { defaultSeasonYear: number }) {
  const [seasonYear, setSeasonYear] = useState(String(defaultSeasonYear));
  const [estimate, setEstimate] = useState<AdminSeasonHistoryEstimate | null>(null);
  const [busy, setBusy] = useState<"estimate" | "start" | "values" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [progress, setProgress] = useState<AdminSeasonHistoryProgress | null>(null);
  const [valuesResult, setValuesResult] = useState<AdminMarketValuesRefreshResult | null>(null);

  const running = isRunning(progress);
  const jobId = progress?.jobId ?? null;

  // Un import già in corso (avviato anche da un altro operatore) si vede subito.
  useEffect(() => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    let cancelled = false;
    Promise.resolve()
      .then(() => fetchActiveAdminSeasonHistory(session.accessToken))
      .then((active) => {
        if (!cancelled && active) {
          setProgress(active);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Avanzamento ogni pochi secondi finché il job è in coda o in corso.
  useEffect(() => {
    if (!jobId || !running) {
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      fetchAdminSeasonHistoryProgress(session.accessToken, jobId)
        .then((next) => {
          if (!cancelled) {
            setProgress(next);
          }
        })
        .catch((pollError: unknown) => {
          if (!cancelled) {
            setError(getApiErrorMessage(pollError, "Impossibile leggere l'avanzamento dell'import."));
            setProgress((current) => (current ? { ...current, status: "failed" } : current));
          }
        });
    }, SEASON_HISTORY_POLL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [jobId, running, progress]);

  function parsedYear(): number | null {
    const year = Number(seasonYear);
    return Number.isInteger(year) && year >= 2000 && year <= 2100 ? year : null;
  }

  async function onEstimate() {
    const year = parsedYear();
    const session = loadStoredSession();
    if (year === null) {
      setError("Inserisci un anno stagione valido (es. 2026).");
      return;
    }
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy("estimate");
    setError(null);
    setConfirming(false);
    try {
      const response = await importAdminSeasonHistory(session.accessToken, { seasonYear: year, dryRun: true });
      setEstimate(response.estimate);
    } catch (estimateError) {
      setError(getApiErrorMessage(estimateError, "Impossibile calcolare le chiamate."));
    } finally {
      setBusy(null);
    }
  }

  async function onStart() {
    const year = parsedYear();
    const session = loadStoredSession();
    if (year === null || !session?.accessToken) {
      setError(year === null ? "Inserisci un anno stagione valido (es. 2026)." : "Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy("start");
    setError(null);
    try {
      const response = await importAdminSeasonHistory(session.accessToken, {
        seasonYear: year,
        dryRun: false,
      });
      setEstimate(response.estimate);
      if (response.job) {
        setProgress({
          jobId: response.job.jobId,
          status: response.job.status === "running" ? "running" : "queued",
          percent: 0,
          stage: response.job.status,
          message: response.job.message,
          errorCode: null,
          result: null,
        });
      }
    } catch (startError) {
      setError(getApiErrorMessage(startError, "Impossibile avviare l'import dello storico."));
    } finally {
      setBusy(null);
      setConfirming(false);
    }
  }

  async function onRefreshValues() {
    const year = parsedYear();
    const session = loadStoredSession();
    if (year === null || !session?.accessToken) {
      setError(year === null ? "Inserisci un anno stagione valido (es. 2026)." : "Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy("values");
    setError(null);
    setValuesResult(null);
    try {
      setValuesResult(await refreshAdminMarketValues(session.accessToken, { seasonYear: year }));
    } catch (valuesError) {
      setError(getApiErrorMessage(valuesError, "Ricalcolo dei valori non riuscito."));
    } finally {
      setBusy(null);
    }
  }

  const result = progress?.status === "completed" ? progress.result : null;
  const failed = progress?.status === "failed" && !error;

  return (
    <Card className="fa-admin-listone-restore fa-season-history" data-testid="admin-season-history">
      <CardHeader>
        <h2 className="fa-admin-listone-restore__title">Storico stagioni</h2>
      </CardHeader>
      <CardBody>
        <p className="fa-admin-listone-restore__intro">
          Scarica una volta dal fornitore le statistiche delle due stagioni passate: servono alla
          media stagionale, al Valore di mercato e alla carriera nella scheda del calciatore.
          Prima calcola quante chiamate servono (non chiama il fornitore), poi avvia l'import.
          Rilanciato, riparte da dove si era fermato.
        </p>
        <div className="fa-admin-listone-restore__form">
          <Input
            label="Stagione in corso"
            name="admin-season-history-year"
            type="number"
            value={seasonYear}
            onChange={(event) => {
              setSeasonYear(event.target.value);
              setEstimate(null);
              setConfirming(false);
            }}
            data-testid="admin-season-history-year"
          />
          <Button
            type="button"
            variant="secondary"
            loading={busy === "estimate"}
            disabled={busy !== null || running}
            onClick={() => void onEstimate()}
            data-testid="admin-season-history-estimate-button"
          >
            Calcola chiamate
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={busy === "values"}
            disabled={busy !== null}
            onClick={() => void onRefreshValues()}
            data-testid="admin-season-history-values"
          >
            Ricalcola valori
          </Button>
        </div>

        {error ? (
          <UiStatePanel
            state="error"
            title="Operazione non riuscita"
            message={error}
            testId="admin-season-history-error"
          />
        ) : null}

        {valuesResult ? (
          <UiStatePanel
            state="success"
            title="Valori ricalcolati"
            message={valuesSummary(valuesResult)}
            testId="admin-season-history-values-done"
          />
        ) : null}

        {estimate && !running ? (
          <div className="fa-admin-listone-restore__preview" data-testid="admin-season-history-estimate">
            <p className="fa-season-history__summary" data-testid="admin-season-history-summary">
              {estimate.estimatedCalls === 0 ? (
                <>Lo storico di {seasonsLabel(estimate)} è completo: nessuna chiamata da fare.</>
              ) : (
                <>
                  Stagioni {seasonsLabel(estimate)}: <strong>{callsLabel(estimate.estimatedCalls)}</strong>,{" "}
                  {minutesLabel(estimate.estimatedMinutes)} ({NUMBER.format(estimate.requestsPerMinute)} al
                  minuto).
                </>
              )}
            </p>
            <ul className="fa-season-history__seasons">
              {estimate.seasons.map((season) => (
                <li key={season.seasonYear} data-testid={`admin-season-history-season-${season.seasonYear}`}>
                  <strong>{fullSeasonLabel(season.seasonYear)}</strong>: {callsLabel(season.estimatedCalls)} ·{" "}
                  {NUMBER.format(season.leaguePagesRemaining)} pagine di campionato
                  {season.leaguePagesExact ? "" : " (stima)"} · {NUMBER.format(season.athletesToFill)}{" "}
                  calciatori da cercare uno per uno{season.athletesToFillExact ? "" : " (stima)"} · righe già
                  salvate: {NUMBER.format(season.rowsStored)}
                </li>
              ))}
            </ul>
            {!confirming ? (
              <Button
                type="button"
                variant="primary"
                disabled={busy !== null}
                onClick={() => setConfirming(true)}
                data-testid="admin-season-history-start"
              >
                Avvia import
              </Button>
            ) : (
              <div
                className="fa-admin-listone-restore__confirm"
                role="alertdialog"
                aria-labelledby="admin-season-history-confirm-text"
                data-testid="admin-season-history-confirm"
              >
                <p id="admin-season-history-confirm-text">
                  Avvii l'import di {seasonsLabel(estimate)}: {callsLabel(estimate.estimatedCalls)} al
                  fornitore, {minutesLabel(estimate.estimatedMinutes)}. Si ferma da solo prima di
                  togliere quota ai giri live e si riprende rilanciandolo. Confermi?
                </p>
                <div className="fa-admin-listone-restore__actions">
                  <Button
                    type="button"
                    variant="primary"
                    loading={busy === "start"}
                    onClick={() => void onStart()}
                    data-testid="admin-season-history-confirm-yes"
                  >
                    Sì, avvia l'import
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy !== null}
                    onClick={() => setConfirming(false)}
                    data-testid="admin-season-history-confirm-no"
                  >
                    Annulla
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : null}

        {running && progress ? (
          <div className="fa-season-history__progress" data-testid="admin-season-history-progress">
            <ProgressBar percent={progress.percent} label={`Import dello storico: ${progress.percent}%`} />
            <p role="status">
              Import in corso: {progress.message || "in coda…"} ({progress.percent}%)
            </p>
          </div>
        ) : null}

        {result ? (
          <UiStatePanel
            state={result.stoppedReason ? "empty" : "success"}
            title={result.stoppedReason ? "Import fermato prima della fine" : "Storico importato"}
            message={
              result.stoppedReason
                ? `${resultSummary(result)} Fermato: ${STOP_REASON_LABEL[result.stoppedReason] ?? result.stoppedReason}. Calcola di nuovo le chiamate e avvia l'import per continuare${
                    result.remaining ? `: restano ${callsLabel(result.remaining.estimatedCalls)}` : ""
                  }.`
                : resultSummary(result)
            }
            testId="admin-season-history-done"
          />
        ) : null}

        {failed && progress ? (
          <UiStatePanel
            state="error"
            title="Import non riuscito"
            message={
              progress.errorCode === "provider_key_missing"
                ? "Manca la chiave del fornitore: l'import non può partire."
                : progress.message || "L'import dello storico si è fermato con un errore."
            }
            testId="admin-season-history-failed"
          />
        ) : null}
      </CardBody>
    </Card>
  );
}
