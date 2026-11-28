/**
 * Pannello operatore → Job automatici: la fascia di riepilogo in cima («Attivi 3 / 5» e
 * «Prossimo giro»), uguale sul sito e nell'app (release 1.5, allineamento app ↔ sito).
 *
 * Solo logica pura e import di tipo: i test `node:test` dell'app caricano questo file dal
 * sorgente.
 */
import type { SystemJob } from "./admin.js";

export const JOBS_INTRO =
  "Questi giri non aspettano un pulsante. Puoi spegnerli o cambiare ogni quanto partono: il beat legge la modifica da solo, senza un nuovo deploy. La prossima partenza è calcolata dall’ultima esecuzione più la frequenza.";

/** Quanto manca a una data: «ora», «12 min», «3 h», «2 g»; «—» senza data. */
export function formatTimeUntil(value: string | null, now: number = Date.now()): string {
  if (!value) {
    return "—";
  }
  const minutes = Math.round((new Date(value).getTime() - now) / 60000);
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

export interface JobsSummaryTile {
  label: string;
  value: string;
  hint: string;
}

/** Il job acceso con la prossima partenza più vicina; `null` se nessuno ha una partenza. */
export function nextJobToRun(jobs: SystemJob[]): SystemJob | null {
  const upcoming = jobs
    .filter((job) => job.enabled && job.nextRunAt)
    .sort(
      (x, y) => new Date(x.nextRunAt as string).getTime() - new Date(y.nextRunAt as string).getTime(),
    );
  return upcoming[0] ?? null;
}

/** I due riquadri di riepilogo; nessuno se non ci sono job. */
export function jobsSummaryTiles(jobs: SystemJob[], now: number = Date.now()): JobsSummaryTile[] {
  if (jobs.length === 0) {
    return [];
  }
  const active = jobs.filter((job) => job.enabled).length;
  const off = jobs.length - active;
  const next = nextJobToRun(jobs);
  return [
    {
      label: "Attivi",
      value: `${active} / ${jobs.length}`,
      hint: off === 1 ? "1 spento" : `${off} spenti`,
    },
    {
      label: "Prossimo giro",
      value: next ? formatTimeUntil(next.nextRunAt, now) : "—",
      hint: next ? next.title : "Nessun job attivo",
    },
  ];
}
