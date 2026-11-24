import type { FantasyCoachDirectoryItem } from "@fantappero/contracts";

/**
 * Id dell'invito nominativo che l'admin può annullare dalla directory, o
 * `null` se non c'è nulla da annullare: serve un invito ancora pendente e il
 * suo id (assente sui backend precedenti, che quindi mostrano solo «Già invitato»).
 */
export function revocableInviteId(
  coach: Pick<FantasyCoachDirectoryItem, "namedInviteStatus" | "namedInviteId" | "isSelf" | "inLeague">,
): string | null {
  if (coach.namedInviteStatus !== "pending" || coach.isSelf === true || coach.inLeague === true) {
    return null;
  }
  const inviteId = coach.namedInviteId?.trim();
  return inviteId ? inviteId : null;
}

/** Testo della conferma prima di annullare l'invito. */
export function revokeInviteConfirmMessage(displayName: string): string {
  return `${displayName} non vedrà più l'invito tra quelli ricevuti. Potrai invitarlo di nuovo quando vuoi.`;
}

/**
 * Errori dell'invito che dicono che la riga della directory non è aggiornata (es. «Invito già
 * inviato» da un altro admin o da un altro dispositivo): va ricaricata, così non offre più
 * «Invita». Come la directory del web.
 */
export function inviteErrorRefreshesRow(error: { code?: string } | null | undefined): boolean {
  return (
    error?.code === "named_invite_already_pending" ||
    error?.code === "already_member" ||
    error?.code === "recipient_unavailable"
  );
}

/**
 * Errori della revoca che dicono che la riga è vecchia (il fantallenatore ha già risposto,
 * l'invito è scaduto o non c'è più): si ricaricano la riga e gli inviti in attesa accanto al
 * conto. Come la directory del web.
 */
export function revokeErrorRefreshesRow(error: { code?: string } | null | undefined): boolean {
  return error?.code === "named_invite_not_pending" || error?.code === "named_invite_not_found";
}

/**
 * Messaggio per gli errori noti della revoca; `null` per gli altri, che il
 * chiamante rende con il messaggio generico dell'API.
 */
export function revokeInviteErrorMessage(
  error: { status?: number; code?: string } | null | undefined,
): string | null {
  if (!error) {
    return null;
  }
  if (error.status === 403) {
    return "Non hai i permessi per annullare gli inviti di questa lega.";
  }
  if (error.code === "named_invite_not_pending") {
    return "L'invito non è più annullabile: il fantallenatore ha già risposto o è scaduto.";
  }
  if (error.code === "named_invite_not_found") {
    return "Invito non trovato.";
  }
  return null;
}
