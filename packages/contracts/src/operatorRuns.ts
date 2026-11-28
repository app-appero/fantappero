/**
 * Pannello operatore › Turni e Job: «Esegui tutti» nei Turni, «Esegui» e «Esegui tutti» nei Job
 * (release 1.5, richiesta di Rosario del 28/11). Stesse etichette, stesse finestre «Sei sicuro?»
 * e stessi testi di esito sul sito e nell'app.
 *
 * Solo logica pura e import di tipo: i test `node:test` dell'app caricano questo file dal
 * sorgente. Le operazioni dei Turni sono le stesse del server (`admin.turni_batch`): l'ordine è
 * quello di esecuzione.
 */
import type {
  SystemJob,
  SystemJobRunAllResult,
  SystemJobRunResult,
  TurniBatch,
  TurniBatchOperation,
} from "./admin.js";
import type { ConfirmCopy } from "./confirmations.js";

/** Uguali a `CONFIRM_TITLE` e `CONFIRM_CANCEL_LABEL` di `confirmations.ts` (lo controlla un test). */
const TITLE = "Sei sicuro?";
const CANCEL = "Annulla";

export const RUN_ALL_LABEL = "Esegui tutti";
export const RUN_JOB_LABEL = "Esegui";

/** Il fornitore sportivo ha una quota di chiamate: chi la usa lo dice prima di partire. */
export const PROVIDER_QUOTA_NOTE = "usano la quota del fornitore sportivo";

export interface TurniBatchOperationInfo {
  /** Chiave dell'operazione, uguale a quella del server. */
  key: string;
  label: string;
  description: string;
  usesProviderQuota: boolean;
}

/**
 * Le operazioni dei Turni che «Esegui tutti» lancia, nell'ordine in cui girano. Restano fuori
 * apposta, perché a senso unico o per singola lega: «Calcola giornata corrente» e «Recupera
 * risultati» (omologano i turni), «Ricalcola storico» (riapre turni già omologati e avvisa gli
 * utenti), «Apri turno», «Ricalcola cutoff» (già incluso in «Sincronizza turni») e «Formazioni
 * IA» di una singola lega.
 */
export const TURNI_BATCH_OPERATIONS: readonly TurniBatchOperationInfo[] = [
  {
    key: "importa-stagione",
    label: "Importa calendario stagione",
    description: "Catalogo e partite di tutti i campionati.",
    usesProviderQuota: true,
  },
  {
    key: "genera-calendario",
    label: "Genera calendario",
    description: "Riallinea partite e turni di ogni lega attiva.",
    usesProviderQuota: true,
  },
  {
    key: "sincronizza-turni",
    label: "Sincronizza turni",
    description: "Apre i turni pronti e ricalcola i cutoff.",
    usesProviderQuota: false,
  },
  {
    key: "formazioni-probabili",
    label: "Aggiorna probabili",
    description: "Formazioni probabili e indisponibili delle partite non iniziate.",
    usesProviderQuota: true,
  },
  {
    key: "formazioni-ia",
    label: "Genera formazioni IA",
    description: "Solo le squadre gestite dall'IA, mai quelle dei fantallenatori.",
    usesProviderQuota: false,
  },
];

function bullets(lines: readonly string[]): string {
  return lines.map((line) => `• ${line}`).join("\n");
}

function joinNames(names: readonly string[]): string {
  return names.join(", ");
}

/** «Esegui tutti» nei Turni: elenca le operazioni e avvisa della quota del fornitore. */
export function turniBatchConfirmation(): ConfirmCopy {
  const withQuota = TURNI_BATCH_OPERATIONS.filter((op) => op.usesProviderQuota).map(
    (op) => op.label,
  );
  return {
    title: TITLE,
    message:
      "Lancio una dopo l'altra queste operazioni, per tutte le leghe attive:\n" +
      `${bullets(TURNI_BATCH_OPERATIONS.map((op) => op.label))}\n\n` +
      `${withQuota.length === 1 ? "Questa usa" : "Alcune usano"} la quota del fornitore ` +
      `sportivo: ${joinNames(withQuota)}. ` +
      "Se una non riesce, le altre vanno avanti. " +
      "Non omologa nessun turno e non ricalcola lo storico.",
    confirmLabel: RUN_ALL_LABEL,
    cancelLabel: CANCEL,
  };
}

/** «Esegui» su un job: una volta sola, con l'avviso se è spento o usa la quota del fornitore. */
export function jobRunConfirmation(
  job: Pick<SystemJob, "title" | "enabled" | "usesProviderQuota" | "sendsNotifications">,
): ConfirmCopy {
  const parts = [`Lancio «${job.title}» adesso, una volta sola.`];
  if (!job.enabled) {
    parts.push("Il job è spento: parte lo stesso questa volta, poi resta spento.");
  }
  if (job.usesProviderQuota) {
    parts.push("Usa la quota del fornitore sportivo.");
  }
  if (job.sendsNotifications) {
    parts.push("Può mandare avvisi ai fantallenatori.");
  }
  return {
    title: TITLE,
    message: parts.join(" "),
    confirmLabel: RUN_JOB_LABEL,
    cancelLabel: CANCEL,
  };
}

/** I job che «Esegui tutti» lancia: solo quelli accesi. */
export function runnableJobs<T extends Pick<SystemJob, "enabled">>(jobs: readonly T[]): T[] {
  return jobs.filter((job) => job.enabled);
}

/**
 * «Esegui tutti» nei Job: elenca i job accesi e avvisa della quota del fornitore. `null` se non
 * c'è nessun job acceso (il pulsante resta spento).
 */
export function jobsRunAllConfirmation(
  jobs: readonly Pick<SystemJob, "title" | "enabled" | "usesProviderQuota" | "sendsNotifications">[],
): ConfirmCopy | null {
  const active = runnableJobs(jobs);
  if (active.length === 0) {
    return null;
  }
  const withQuota = active.filter((job) => job.usesProviderQuota).map((job) => job.title);
  const withNotices = active.filter((job) => job.sendsNotifications).map((job) => job.title);
  const lead =
    active.length === 1
      ? "Lancio ora il job attivo, una volta sola:"
      : `Lancio ora tutti i ${active.length} job attivi, una volta sola:`;
  const notes: string[] = [];
  if (withQuota.length > 0) {
    notes.push(
      `${withQuota.length === 1 ? "Questo usa" : "Alcuni usano"} la quota del fornitore sportivo: ` +
        `${joinNames(withQuota)}.`,
    );
  }
  if (withNotices.length > 0) {
    notes.push(
      `${withNotices.length === 1 ? "Questo può" : "Alcuni possono"} mandare avvisi ai ` +
        `fantallenatori: ${joinNames(withNotices)}.`,
    );
  }
  notes.push("Un job già in esecuzione non si rilancia. I job spenti restano fuori.");
  return {
    title: TITLE,
    message: `${lead}\n${bullets(active.map((job) => job.title))}\n\n${notes.join(" ")}`,
    confirmLabel: RUN_ALL_LABEL,
    cancelLabel: CANCEL,
  };
}

export type RunTone = "success" | "warning" | "error";

export interface RunOutcomeLine {
  key: string;
  title: string;
  tone: RunTone;
  text: string;
}

/** Esito di un lancio: avviato (con l'eventuale avviso del job spento), già in corso o fallito. */
export function jobRunOutcome(result: SystemJobRunResult): RunOutcomeLine {
  if (result.status === "started") {
    return {
      key: result.key,
      title: result.title,
      tone: result.warning ? "warning" : "success",
      text: result.warning ? `${result.message} ${result.warning}` : result.message,
    };
  }
  return {
    key: result.key,
    title: result.title,
    tone: result.status === "already_running" ? "warning" : "error",
    text: result.message,
  };
}

/** Riepilogo di «Esegui tutti» nei Job: «Avviati 8 job su 9 · 1 già in esecuzione · …». */
export function jobsRunAllSummary(result: SystemJobRunAllResult): string {
  const total = result.started + result.alreadyRunning + result.failed;
  const parts = [
    result.started === 1
      ? `Avviato 1 job su ${total}`
      : `Avviati ${result.started} job su ${total}`,
  ];
  if (result.alreadyRunning > 0) {
    parts.push(
      result.alreadyRunning === 1
        ? "1 già in esecuzione, non rilanciato"
        : `${result.alreadyRunning} già in esecuzione, non rilanciati`,
    );
  }
  if (result.failed > 0) {
    parts.push(result.failed === 1 ? "1 non partito" : `${result.failed} non partiti`);
  }
  return `${parts.join(" · ")}.`;
}

/** Il lancio dei job è finito senza errori né job fermi: tono del riepilogo. */
export function jobsRunAllTone(result: SystemJobRunAllResult): RunTone {
  if (result.failed > 0) {
    return "error";
  }
  return result.alreadyRunning > 0 ? "warning" : "success";
}

/** «In esecuzione», «Ultimo giro riuscito», «Ultimo giro non riuscito: motivo»; `null` se mai girato. */
export function jobLastRunLabel(job: Pick<SystemJob, "running" | "lastRun">): string | null {
  if (job.running) {
    return "In esecuzione";
  }
  if (!job.lastRun) {
    return null;
  }
  if (job.lastRun.outcome === "ok") {
    return "Ultimo giro riuscito";
  }
  return job.lastRun.reason
    ? `Ultimo giro non riuscito: ${job.lastRun.reason}`
    : "Ultimo giro non riuscito";
}

const OPERATION_STATUS_LABEL: Record<string, string> = {
  pending: "In attesa",
  running: "In corso",
  ok: "Riuscita",
  failed: "Non riuscita",
  skipped: "Saltata",
};

export function turniBatchOperationStatusLabel(status: string): string {
  return OPERATION_STATUS_LABEL[status] ?? status;
}

/** Esito di una operazione dei Turni: tono per colore e testo («Riuscita: …», «Non riuscita: …»). */
export function turniBatchOperationOutcome(operation: TurniBatchOperation): RunOutcomeLine {
  const tone: RunTone =
    operation.status === "ok"
      ? "success"
      : operation.status === "failed"
        ? "error"
        : operation.status === "skipped"
          ? "warning"
          : "success";
  const status = turniBatchOperationStatusLabel(operation.status);
  const text = operation.message ? `${status}: ${operation.message}` : status;
  return { key: operation.key, title: operation.label, tone, text };
}

/** Il blocco è finito (bene o male): niente altro da aspettare. */
export function isTurniBatchFinished(batch: Pick<TurniBatch, "status">): boolean {
  return batch.status === "completed" || batch.status === "failed";
}

/**
 * Riepilogo di «Esegui tutti» nei Turni. In corso: «In corso: 2 operazioni su 5 finite». A fine
 * blocco: «Riuscite 4 operazioni su 5 · 1 non riuscita · …».
 */
export function turniBatchSummary(batch: TurniBatch): string {
  const total = batch.operations.length;
  if (!isTurniBatchFinished(batch)) {
    const done = batch.ok + batch.failed + batch.skipped;
    return `In corso: ${done} ${done === 1 ? "operazione" : "operazioni"} su ${total} finite.`;
  }
  const parts = [
    batch.ok === 1
      ? `Riuscita 1 operazione su ${total}`
      : `Riuscite ${batch.ok} operazioni su ${total}`,
  ];
  if (batch.failed > 0) {
    parts.push(batch.failed === 1 ? "1 non riuscita" : `${batch.failed} non riuscite`);
  }
  if (batch.skipped > 0) {
    parts.push(batch.skipped === 1 ? "1 saltata" : `${batch.skipped} saltate`);
  }
  return `${parts.join(" · ")}.`;
}

/** Tono del riepilogo di «Esegui tutti» nei Turni. */
export function turniBatchTone(batch: TurniBatch): RunTone {
  if (batch.failed > 0 || batch.status === "failed") {
    return "error";
  }
  return batch.skipped > 0 ? "warning" : "success";
}

/** Ogni quanto si rilegge l'avanzamento di «Esegui tutti» nei Turni (millisecondi). */
export const TURNI_BATCH_POLL_MS = 1500;
/** Ogni quanto si rilegge l'elenco dei job mentre uno gira (millisecondi). */
export const JOBS_POLL_MS = 4000;
