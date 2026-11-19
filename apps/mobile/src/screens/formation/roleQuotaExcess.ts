/**
 * Chi è in esubero di ruolo nella schermata Formazione (QA 19/11, qa-02).
 *
 * Chi è in esubero (`exceedsRoleQuota`) resta in rosa ma non si schiera finché la rosa non torna
 * in regola: non va nella formazione mandata al server (titolari, panchina e tribuna) né nel
 * confronto con quella salvata. L'app lo metteva in coda alla panchina e ogni salvataggio era
 * rifiutato; si vede ancora in fondo alla tribuna, ma fuori dalla formazione.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Sul web lo stesso criterio è in `@fantappero/contracts`
 * (`withoutRoleQuotaExcess`).
 */
import type { LineupRosterPlayer } from "@fantappero/contracts";

/** Gli stessi id senza chi è in esubero di ruolo: gli id della rosa o una panchina già fatta. */
export function withoutRoleQuotaExcess(
  athleteIds: readonly string[],
  roster: readonly Pick<LineupRosterPlayer, "athleteId" | "exceedsRoleQuota">[],
): string[] {
  const excess = new Set(roster.filter((row) => row.exceedsRoleQuota === true).map((row) => row.athleteId));
  return athleteIds.filter((athleteId) => !excess.has(athleteId));
}
