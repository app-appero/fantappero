/**
 * Testo di stato del blocco nelle schermate Formazione e Turni (28/11, decisione di Rosario).
 *
 * Con il conto alla rovescia in corso c'è una sola riga «Prossimo blocco»: la fascia sotto
 * l'intestazione (`LockCountdownBar`), e la schermata non la ripete. Senza conto («Turno non
 * ancora aperto», «Turno saltato», «Formazione confermata», «Rosa non ancora assegnata»,
 * «Nessun turno attivo») la schermata mostra il testo di stato come prima, per il turno a cui
 * il conto si riferisce.
 *
 * Solo logica pura e import di tipo, così gira nei test `node:test`.
 */
import type { LineupLockCountdown } from "@fantappero/contracts";

export function showsPageLockNote(
  countdown: Pick<LineupLockCountdown, "roundId" | "state"> | null,
  roundId: string,
): boolean {
  return countdown != null && countdown.roundId === roundId && countdown.state !== "counting_down";
}
