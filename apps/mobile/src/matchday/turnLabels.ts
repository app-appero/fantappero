/**
 * Etichette dei turni europei nelle schermate dell'app.
 *
 * Solo logica pura e import di tipo: le etichette (`TURN_DISPLAY_LABEL` di
 * `@fantappero/contracts`) arrivano dal chiamante, così gira nei test `node:test`.
 */
import type { FantasyTurnSummary, TurnDisplayState } from "@fantappero/contracts";

export type TurnDisplayLabels = Readonly<Record<TurnDisplayState, string>>;

/**
 * Motivo di un turno saltato (es. «Soglia non raggiunta: 20 partite eleggibili su 25»), come
 * lo mostra il sito. L'app scriveva solo «Stato: Turno saltato» (corsa M3, 22/11).
 * `null` se il turno non è saltato o l'API non manda il motivo.
 */
export function turnSkipReason(
  turn: Pick<FantasyTurnSummary, "skipReason">,
  state: TurnDisplayState,
): string | null {
  if (state !== "skipped") {
    return null;
  }
  const reason = turn.skipReason?.trim();
  return reason ? reason : null;
}

/** Voce del menù di Turni › Turni europei: «Turno 12 — Turno saltato (Soglia non raggiunta: …)». */
export function europeanTurnOptionLabel(
  turn: Pick<FantasyTurnSummary, "number" | "skipReason">,
  state: TurnDisplayState,
  labels: TurnDisplayLabels,
): string {
  const base = `Turno ${turn.number} — ${labels[state]}`;
  const reason = turnSkipReason(turn, state);
  return reason ? `${base} (${reason})` : base;
}
