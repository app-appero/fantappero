/**
 * Pannello operatore › Turni › «Esegui tutti» (release 1.5): l'app avvia il blocco di operazioni
 * sul server e ne rilegge l'avanzamento finché non è finito (bene o male).
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` con un'API finta e una pausa finta.
 */
import type { TurniBatch } from "@fantappero/contracts";

export interface TurniBatchApi {
  start(): Promise<TurniBatch>;
  fetch(batchId: string): Promise<TurniBatch>;
}

export interface PollTurniBatchOptions {
  onProgress?: (batch: TurniBatch) => void;
  /** Pausa tra una lettura e l'altra (millisecondi). */
  pollIntervalMs?: number;
  /** Per i test: sostituisce l'attesa vera. */
  sleep?: (ms: number) => Promise<void>;
}

export const DEFAULT_TURNI_BATCH_POLL_MS = 1500;

/** Il blocco è finito (bene o male): niente altro da aspettare. */
function isFinished(batch: TurniBatch): boolean {
  return batch.status === "completed" || batch.status === "failed";
}

/**
 * Avvia il blocco e lo segue: `onProgress` riceve ogni stato (anche il primo e l'ultimo), il
 * risultato è l'ultimo stato. Un 409 («già in corso») o un errore di rete arriva come eccezione
 * già alla prima chiamata o a una lettura: chi chiama mostra il messaggio.
 */
export async function pollTurniBatch(
  api: TurniBatchApi,
  options: PollTurniBatchOptions = {},
): Promise<TurniBatch> {
  const pollIntervalMs = options.pollIntervalMs ?? DEFAULT_TURNI_BATCH_POLL_MS;
  const sleep =
    options.sleep ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)));
  let batch = await api.start();
  for (;;) {
    options.onProgress?.(batch);
    if (isFinished(batch)) {
      return batch;
    }
    await sleep(pollIntervalMs);
    batch = await api.fetch(batch.batchId);
  }
}
