/**
 * Finestre «Sei sicuro?» del pannello della lega e del pannello operatore (release 1.5,
 * allineamento app ↔ sito): stessi titoli, testi e pulsanti sul sito e nell'app.
 *
 * - «Rimuovi partecipante» (amministrazione lega): chiede conferma con il nome.
 * - Invio di notifiche (broadcast) dal pannello operatore: chiede conferma con il numero dei
 *   destinatari (o «tutti gli utenti»). «Invia a me come prova» non chiede conferma.
 * - Email dell'operatore: stessa conferma dell'invio di notifiche.
 *
 * Solo logica pura e nessun import a runtime: i test `node:test` dell'app caricano questo file
 * dal sorgente.
 */

export const CONFIRM_TITLE = "Sei sicuro?";
export const CONFIRM_CANCEL_LABEL = "Annulla";

export interface ConfirmCopy {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
}

/**
 * «12 utenti» / «1 utente» / «tutti gli utenti» (quando il numero non è noto): destinatari di
 * notifiche ed email dell'operatore. Mai «1 utenti» (QA 28/11).
 */
export function usersLabel(recipients: number | null): string {
  if (recipients === null) {
    return "tutti gli utenti";
  }
  return `${recipients} ${recipients === 1 ? "utente" : "utenti"}`;
}

/** Minimo di partecipanti ammesso dal server (`MIN_PARTICIPANTS`), se `participantMin` non è noto. */
export const DEFAULT_PARTICIPANT_MIN = 4;

/** Conteggi noti al client prima di «Rimuovi» (stessa regola del server). */
export interface RemovalCounts {
  /** Partecipanti previsti dal regolamento prima della rimozione; `null`/assente = non noti. */
  participantCount: number | null | undefined;
  /** Minimo ammesso per «Partecipanti» (`participantMin`); `null`/assente = quello predefinito. */
  participantMin?: number | null;
  /** Iscritti che restano dopo la rimozione. */
  remaining: number;
}

/**
 * Previsti dopo la rimozione di un partecipante: stessa regola di
 * `_sync_participant_count_after_removal` del server. I previsti scendono agli iscritti rimasti
 * solo se ne restano almeno `participantMin` (4 se non noto) e i previsti sono più degli iscritti;
 * altrimenti restano quelli di prima.
 */
export function participantCountAfterRemoval(input: {
  participantCount: number;
  participantMin?: number | null;
  remaining: number;
}): number {
  const min = input.participantMin ?? DEFAULT_PARTICIPANT_MIN;
  if (input.remaining < min || input.participantCount <= input.remaining) {
    return input.participantCount;
  }
  return input.remaining;
}

type RemovalOutcome =
  | { kind: "unknown" }
  | { kind: "aligned"; count: number }
  | { kind: "unchanged"; count: number };

function removalOutcome(counts: RemovalCounts | null | undefined): RemovalOutcome {
  if (!counts || counts.participantCount == null) {
    return { kind: "unknown" };
  }
  const after = participantCountAfterRemoval({
    participantCount: counts.participantCount,
    participantMin: counts.participantMin,
    remaining: counts.remaining,
  });
  return after === counts.participantCount
    ? { kind: "unchanged", count: after }
    : { kind: "aligned", count: after };
}

/**
 * «Rimuovi» accanto a un partecipante della lega: nome del partecipante nella domanda. Dice che
 * i previsti si allineano solo se cambiano davvero (altrimenti dice che restano); senza conteggi
 * noti non dice nulla sui previsti.
 */
export function removeMemberConfirmation(
  displayName: string,
  counts?: RemovalCounts | null,
): ConfirmCopy {
  const outcome = removalOutcome(counts);
  const tail =
    outcome.kind === "aligned"
      ? " Il numero dei partecipanti previsti si allinea agli iscritti rimasti."
      : outcome.kind === "unchanged"
        ? ` I partecipanti previsti restano ${outcome.count}.`
        : "";
  return {
    title: CONFIRM_TITLE,
    message: `Vuoi rimuovere ${displayName} dalla lega?${tail}`,
    confirmLabel: "Rimuovi",
    cancelLabel: CONFIRM_CANCEL_LABEL,
  };
}

/** Esito dopo «Rimuovi» e conferma: i previsti sono «allineati» solo se sono cambiati davvero. */
export function memberRemovedMessage(displayName: string, counts?: RemovalCounts | null): string {
  const outcome = removalOutcome(counts);
  const base = `${displayName} è stato rimosso dalla lega.`;
  if (outcome.kind === "aligned") {
    return `${base} Il numero partecipanti previsti è stato allineato agli iscritti (${outcome.count}).`;
  }
  if (outcome.kind === "unchanged") {
    return `${base} I partecipanti previsti restano ${outcome.count}.`;
  }
  return base;
}

export interface BroadcastConfirmInput {
  /** Titolo della notifica, come scritto dall'operatore. */
  title: string;
  /** Destinatari noti; `null` = tutti gli utenti (il numero non è stato letto). */
  recipients: number | null;
  /** Notifica programmata invece che subito. */
  scheduled: boolean;
  push: boolean;
  email: boolean;
}

/** «Invia a N utenti» / «Programma» dal pannello operatore → Notifiche. */
export function broadcastConfirmation(input: BroadcastConfirmInput): ConfirmCopy {
  const channels = ["App", input.push ? "push" : null, input.email ? "email" : null]
    .filter(Boolean)
    .join(" + ");
  const audience = usersLabel(input.recipients);
  const what = input.title.trim() ? `la notifica «${input.title.trim()}»` : "la notifica";
  const lead = input.scheduled
    ? `Stai per programmare ${what} per ${audience}.`
    : `Stai per inviare ${what} a ${audience}.`;
  return {
    title: CONFIRM_TITLE,
    message: `${lead} Canali: ${channels}.${input.scheduled ? "" : " Dopo l'invio non si può annullare."}`,
    confirmLabel: input.scheduled ? "Programma" : "Invia",
    cancelLabel: CONFIRM_CANCEL_LABEL,
  };
}

/** «Invia a N utenti» dal pannello operatore → Email. */
export function operatorEmailConfirmation(input: {
  /** Destinatari noti; `null` = tutti gli utenti. */
  recipients: number | null;
}): ConfirmCopy {
  return {
    title: CONFIRM_TITLE,
    message: `Inviare l'email a ${usersLabel(input.recipients)}? Dopo l'invio non si può annullare.`,
    confirmLabel: "Invia",
    cancelLabel: CONFIRM_CANCEL_LABEL,
  };
}
