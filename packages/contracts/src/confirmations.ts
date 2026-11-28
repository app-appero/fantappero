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

function usersLabel(recipients: number | null): string {
  if (recipients === null) {
    return "tutti gli utenti";
  }
  return `${recipients} ${recipients === 1 ? "utente" : "utenti"}`;
}

/** «Rimuovi» accanto a un partecipante della lega: nome del partecipante nella domanda. */
export function removeMemberConfirmation(displayName: string): ConfirmCopy {
  return {
    title: CONFIRM_TITLE,
    message: `Vuoi rimuovere ${displayName} dalla lega? Il numero dei partecipanti previsti si allinea agli iscritti rimasti.`,
    confirmLabel: "Rimuovi",
    cancelLabel: CONFIRM_CANCEL_LABEL,
  };
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
