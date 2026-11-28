/**
 * «Genera/Conferma calendario» della lega (Rosario 22/11): conferma «Sei sicuro?» e controllo
 * delle rose con la scelta «Genera/Conferma comunque». Testi e logica uguali sul sito e
 * nell'app (release 1.5, allineamento app ↔ sito).
 *
 * Il testo segue il comportamento reale della formazione (`roster_allows_lineup`,
 * `drop_role_quota_excess_from_tribuna`): chi è in esubero di ruolo resta in rosa ma non si
 * schiera (né titolare né nei primi 10 della panchina), gli altri sì. Una rosa con slot vuoti
 * o meno di 3 campionati (`lineupBlocked`) invece non schiera proprio.
 *
 * Solo logica pura e import di tipo: i test `node:test` dell'app caricano questo file dal
 * sorgente.
 */
import type { CalendarRosterTeamIssues, LeagueCalendar } from "./leagues.js";

export type CalendarAction = "generate" | "confirm";

/** Stato della finestra: verifica delle rose in corso, poi conferma normale o avviso. */
export interface CalendarActionModalState {
  action: CalendarAction;
  phase: "checking" | "ready";
  teams: CalendarRosterTeamIssues[];
}

export interface CalendarActionCopy {
  title: string;
  verb: string;
  button: string;
  forceButton: string;
  working: string;
  prompt: string;
}

export const CALENDAR_ACTION_COPY: Record<CalendarAction, CalendarActionCopy> = {
  generate: {
    title: "Genera calendario",
    verb: "generare",
    button: "Genera calendario",
    forceButton: "Genera comunque",
    working: "Generazione…",
    prompt:
      "Vuoi generare il calendario? Le giornate seguono i Turni Europei della lega: dopo controlli l'anteprima e la confermi.",
  },
  confirm: {
    title: "Conferma calendario",
    verb: "confermare",
    button: "Conferma calendario",
    forceButton: "Conferma comunque",
    working: "Conferma…",
    prompt: "Vuoi confermare il calendario? Gli scontri diventano visibili a tutti i partecipanti.",
  },
};

export const CALENDAR_CANCEL_LABEL = "Annulla";
export const CALENDAR_CHECKING_TEXT = "Verifica delle rose in corso…";
export const CALENDAR_ISSUES_HEADING = "Alcune rose non sono in regola:";

/** «A, B e C»: i nomi delle squadre in una frase. */
export function joinTeamNames(names: string[]): string {
  if (names.length <= 1) {
    return names[0] ?? "";
  }
  return `${names.slice(0, -1).join(", ")} e ${names[names.length - 1]}`;
}

/** Testo del pulsante di conferma della finestra: normale, «comunque» (rose non in regola) o in corso. */
export function calendarProceedLabel(
  action: CalendarAction,
  hasIssues: boolean,
  working: boolean,
): string {
  const copy = CALENDAR_ACTION_COPY[action];
  if (working) {
    return copy.working;
  }
  return hasIssues ? copy.forceButton : copy.button;
}

/** Cosa succede se si procede comunque: le rose vanno sistemate, gli esuberi non si schierano. */
export function calendarForceNote(action: CalendarAction): string {
  const verb = CALENDAR_ACTION_COPY[action].verb;
  return `Puoi ${verb} comunque il calendario: le rose andranno sistemate, meglio prima del primo turno. Finché una rosa non torna in regola, i calciatori in esubero restano in rosa ma non potranno essere schierati, né titolari né tra i primi 10 della panchina; il resto della squadra può schierare la formazione senza di loro.`;
}

/** Squadre che non potranno schierare proprio la formazione; `null` se non ce ne sono. */
export function calendarBlockedNote(teams: CalendarRosterTeamIssues[]): string | null {
  const blocked = teams.filter((team) => team.lineupBlocked).map((team) => team.teamName);
  if (blocked.length === 0) {
    return null;
  }
  return `${joinTeamNames(blocked)} invece non ${
    blocked.length === 1 ? "potrà" : "potranno"
  } schierare la formazione finché la rosa non sarà completa e con almeno 3 campionati.`;
}

/** «Squadra X: Difensori 10 su 11, Attaccanti 11 su 10». */
export function calendarIssueText(team: CalendarRosterTeamIssues): string {
  return `${team.teamName}: ${team.issues.join(", ")}`;
}

/**
 * Le squadre con la rosa non in regola dal corpo di un errore `league_rosters_invalid`
 * (`CALENDAR_ROSTERS_INVALID_CODE`) di «Genera/Conferma calendario». Il controllo del codice
 * lo fa chi chiama l'API; qui si legge solo il corpo.
 */
export function calendarRosterIssuesFromPayload(
  payload: Record<string, unknown> | null | undefined,
): CalendarRosterTeamIssues[] {
  const raw = payload?.teams;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item): CalendarRosterTeamIssues[] => {
    if (!item || typeof item !== "object") {
      return [];
    }
    const team = item as Record<string, unknown>;
    if (typeof team.teamName !== "string") {
      return [];
    }
    return [
      {
        teamId: typeof team.teamId === "string" ? team.teamId : null,
        teamName: team.teamName,
        issues: Array.isArray(team.issues)
          ? team.issues.filter((issue): issue is string => typeof issue === "string")
          : [],
        lineupBlocked: team.lineupBlocked === true,
      },
    ];
  });
}

/** Esito mostrato nel pannello dopo «Genera calendario». */
export function calendarGeneratedMessage(
  calendar: Pick<LeagueCalendar, "matchupCount" | "roundCount">,
): string {
  return `Calendario generato: ${calendar.matchupCount} incontri su ${calendar.roundCount} giornate.`;
}

export const CALENDAR_CONFIRMED_MESSAGE = "Calendario confermato.";

/**
 * L'errore dice di sistemare le rose in «Partecipanti»: il pannello offre «Vai a Partecipanti».
 */
export function calendarErrorNeedsParticipants(message: string | null | undefined): boolean {
  return Boolean(message) && /Completa le rose|Partecipanti/i.test(message ?? "");
}

/** Spiegazione sotto «Stato» nel pannello del calendario. */
export const CALENDAR_PANEL_INTRO =
  "Genera e conferma il calendario quando tutte le rose in Partecipanti sono in regola: se qualcuna non lo è, prima di procedere ti diciamo quale e cosa manca.";
