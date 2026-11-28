/**
 * Passaggi della finestra «Genera/Conferma calendario» nell'app (1.5): la stessa logica del
 * pannello del sito (`LeagueCalendarPanel`), tenuta qui come funzioni pure per i test.
 *
 * 1. Si tocca «Genera/Conferma calendario»: la finestra si apre su «Verifica delle rose…».
 * 2. Il controllo delle rose risponde: finestra di conferma normale (rose in regola) o avviso con
 *    le squadre e «Genera/Conferma comunque». Se il controllo non riesce si va avanti con la
 *    conferma normale: se le rose non sono in regola lo dice l'azione stessa.
 * 3. L'azione parte; se il server risponde `league_rosters_invalid` la finestra passa
 *    all'avviso, per ogni altro errore si chiude e l'errore si legge nel pannello.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test`.
 */
import type {
  CalendarAction,
  CalendarActionModalState,
  CalendarRosterTeamIssues,
} from "@fantappero/contracts";

/** La finestra si apre subito, in attesa del controllo delle rose. */
export function calendarModalChecking(action: CalendarAction): CalendarActionModalState {
  return { action, phase: "checking", teams: [] };
}

/**
 * Risposta del controllo delle rose. Se nel frattempo la finestra è stata chiusa (o riaperta su
 * un'altra azione) la risposta si ignora.
 */
export function calendarModalAfterCheck(
  current: CalendarActionModalState | null,
  action: CalendarAction,
  teams: CalendarRosterTeamIssues[],
): CalendarActionModalState | null {
  if (!current || current.action !== action) {
    return current;
  }
  return { action, phase: "ready", teams };
}

/**
 * Errore dell'azione: con rose non in regola (`teams` non vuoto) la finestra passa all'avviso;
 * altrimenti si chiude (`null`) e l'errore va nel pannello.
 */
export function calendarModalAfterError(
  action: CalendarAction,
  issues: CalendarRosterTeamIssues[] | null,
): CalendarActionModalState | null {
  if (issues !== null && issues.length > 0) {
    return { action, phase: "ready", teams: issues };
  }
  return null;
}

/** Il pulsante «comunque» vale solo con l'avviso a schermo: l'azione parte con `force`. */
export function calendarProceedForce(state: CalendarActionModalState | null): boolean {
  return Boolean(state && state.phase === "ready" && state.teams.length > 0);
}

/** Pulsanti del pannello (Genera, Conferma) disattivati mentre una azione o la finestra è aperta. */
export function calendarButtonsDisabled(input: {
  working: boolean;
  modalOpen: boolean;
}): boolean {
  return input.working || input.modalOpen;
}
