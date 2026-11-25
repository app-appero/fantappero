/**
 * Formazione salvata con chi non è più in rosa (QA 19/11).
 *
 * Nei turni ancora aperti il server toglie dalla formazione e dalla bozza restituite chi non è
 * più in rosa (scambio, svincolo, asta, rimozione dell'admin), lascia vuoto il suo posto e lo
 * dice in un avviso tra le `issues` del contesto.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Sul web lo stesso criterio è in `@fantappero/contracts`
 * (`savedStarterSlotIds`, `rosterDepartureNotices`, `rosterBlockNotice`).
 */
import type { LineupIssue, LineupPlayer } from "@fantappero/contracts";

export const LINEUP_ATHLETE_LEFT_ROSTER_CODE = "lineup_athlete_left_roster";

/** Messaggi degli avvisi «non è più nella tua rosa» tra le `issues` del contesto. */
export function rosterDepartureNotices(issues: readonly LineupIssue[] | null | undefined): string[] {
  return (issues ?? [])
    .filter((item) => item.code === LINEUP_ATHLETE_LEFT_ROSTER_CODE)
    .map((item) => item.message);
}

/** Rosa che non può schierare (es. 34/35 dopo uno scambio 2 per 1): primo elemento delle `issues`. */
export const ROSTER_NOT_VALIDATED_CODE = "roster_not_validated";

/** Messaggio del server sulla rosa che non può schierare, `null` se la rosa è a posto. */
export function rosterBlockNotice(issues: readonly LineupIssue[] | null | undefined): string | null {
  return (issues ?? []).find((item) => item.code === ROSTER_NOT_VALIDATED_CODE)?.message ?? null;
}

/**
 * Titolari della formazione salvata nei posti del modulo, secondo `sortOrder`.
 *
 * Chi resta tiene il suo `sortOrder`: in fila per indice scalerebbe di un posto dopo un posto
 * vuoto (es. un centrocampista nello slot di un difensore). Un `sortOrder` fuori dal modulo o già
 * occupato va nel primo posto libero.
 */
export function savedStarterSlotIds(
  starters: readonly Pick<LineupPlayer, "athleteId" | "sortOrder">[],
  slotCount: number,
): string[] {
  const slots = Array.from({ length: slotCount }, () => "");
  const unplaced: string[] = [];
  for (const player of starters) {
    const index = player.sortOrder;
    if (Number.isInteger(index) && index >= 0 && index < slotCount && !slots[index]) {
      slots[index] = player.athleteId;
    } else {
      unplaced.push(player.athleteId);
    }
  }
  for (const athleteId of unplaced) {
    const free = slots.indexOf("");
    if (free < 0) {
      break;
    }
    slots[free] = athleteId;
  }
  return slots;
}
