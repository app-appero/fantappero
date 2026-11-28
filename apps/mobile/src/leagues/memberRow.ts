/**
 * Riga di un partecipante in Amministrazione lega → Invitati (1.5, allineamento app ↔ sito):
 * etichetta del ruolo («· IA»), link al profilo (non per sé) e «Assegna rosa random» per i
 * fantallenatori IA. Stesse regole di `LeagueMembersPanel` del sito.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test`.
 */
import type { LeagueMember } from "@fantappero/contracts";

/** «Amministratore» / «Partecipante», con «· IA» per i fantallenatori IA. */
export function memberRoleLabel(member: Pick<LeagueMember, "role" | "userType">): string {
  const role = member.role === "league_admin" ? "Amministratore" : "Partecipante";
  return member.userType === "ai" ? `${role} · IA` : role;
}

/** Il nome apre il profilo del fantallenatore, tranne il proprio. */
export function canOpenMemberProfile(
  member: Pick<LeagueMember, "userId">,
  selfUserId: string | null | undefined,
): boolean {
  return !selfUserId || member.userId !== selfUserId;
}

/** «Rimuovi» e «Assegna rosa random» compaiono solo per i partecipanti, a lega modificabile. */
export function canManageMember(
  member: Pick<LeagueMember, "role">,
  canEditMembers: boolean,
): boolean {
  return member.role === "member" && canEditMembers;
}

/** «Assegna rosa random»: solo per i fantallenatori IA. */
export function canAssignRandomRoster(
  member: Pick<LeagueMember, "role" | "userType">,
  canEditMembers: boolean,
): boolean {
  return canManageMember(member, canEditMembers) && member.userType === "ai";
}

export const RANDOM_ROSTER_ONLY_AI_MESSAGE =
  "La rosa random è disponibile solo per i fantallenatori IA.";
export const RANDOM_ROSTER_TEAM_MISSING_MESSAGE =
  "Squadra del fantallenatore IA non trovata. Assicura prima le squadre.";
export const RANDOM_ROSTER_FALLBACK_ERROR = "Impossibile assegnare la rosa random.";

/** «Rosa random assegnata a Allenatore IA 01: 25/25 giocatori.» */
export function randomRosterAssignedMessage(
  displayName: string,
  roster: { filledSlots: number; rosterSize: number },
): string {
  return `Rosa random assegnata a ${displayName}: ${roster.filledSlots}/${roster.rosterSize} giocatori.`;
}

/** Dopo «Rimuovi» e conferma: il partecipante esce e i previsti si allineano agli iscritti. */
export function memberRemovedMessage(displayName: string): string {
  return `${displayName} è stato rimosso dalla lega. Il numero partecipanti previsti è stato allineato agli iscritti.`;
}
