/**
 * Quota per ruolo della rosa nel listone «Inserimento manuale» (segnalazione di un tester,
 * Rosario 21/11 per pilota-1.2): raggiunti i 10 attaccanti l'app lasciava scorrere per
 * assegnarne un altro senza dire perché non entrava.
 *
 * Stessa regola del server (`_role_quota_check` in `backend/src/fantasy_teams/
 * composition_service.py`), così client e server non si contraddicono:
 * - contano tutti i calciatori in rosa, anche quelli segnati in esubero (`exceedsRoleQuota`);
 * - chi non ha un ruolo listone risolto (`role` nullo) conta in ogni ruolo, come se avesse il
 *   ruolo di chi entra;
 * - un ruolo è pieno quando i suoi calciatori sono già quanti il limite (o di più).
 *
 * Limiti dalle regole della lega (`composition.limits` della squadra), ruoli dagli slot.
 * Solo logica pura e import di tipo: i test `node:test` (anche quelli dell'app) caricano il
 * file dal sorgente.
 */
import type { FantasyRole, FantasyTeam, RosterCompositionLimits } from "./leagues.js";

/** Codice d'errore del server quando un'assegnazione supera la quota del ruolo. */
export const ROLE_QUOTA_EXCEEDED_CODE = "role_quota_exceeded";

export const ROSTER_QUOTA_ROLES: readonly FantasyRole[] = ["P", "D", "C", "A"];

const LIMIT_KEY: Record<FantasyRole, keyof Omit<RosterCompositionLimits, "rosterSize">> = {
  P: "goalkeepers",
  D: "defenders",
  C: "midfielders",
  A: "forwards",
};

export const ROLE_QUOTA_PLURAL: Record<FantasyRole, string> = {
  P: "Portieri",
  D: "Difensori",
  C: "Centrocampisti",
  A: "Attaccanti",
};

export interface RoleQuotaStat {
  role: FantasyRole;
  /** Calciatori che il server conta nel ruolo, senza ruolo compresi. */
  filled: number;
  max: number;
  full: boolean;
}

export interface RosterRoleQuota {
  roles: Record<FantasyRole, RoleQuotaStat>;
  /** Calciatori in rosa senza ruolo listone: contano in ogni ruolo. */
  unresolved: number;
}

export type RoleQuotaTeam = Pick<FantasyTeam, "slots" | "composition">;

function isRole(value: string | null | undefined): value is FantasyRole {
  return value === "P" || value === "D" || value === "C" || value === "A";
}

/** Pieni e massimi per ruolo; `null` se la squadra non porta i limiti della lega. */
export function rosterRoleQuota(team: RoleQuotaTeam | null | undefined): RosterRoleQuota | null {
  const limits = team?.composition?.limits;
  if (!team || !limits) {
    return null;
  }
  const counts: Record<FantasyRole, number> = { P: 0, D: 0, C: 0, A: 0 };
  let unresolved = 0;
  for (const slot of team.slots) {
    if (!slot.athleteId) {
      continue;
    }
    if (isRole(slot.role)) {
      counts[slot.role] += 1;
    } else {
      unresolved += 1;
    }
  }
  const roles = {} as Record<FantasyRole, RoleQuotaStat>;
  for (const role of ROSTER_QUOTA_ROLES) {
    const max = Math.max(0, Number(limits[LIMIT_KEY[role]]) || 0);
    const filled = counts[role] + unresolved;
    roles[role] = { role, filled, max, full: filled >= max };
  }
  return { roles, unresolved };
}

/** Ruoli pieni, nell'ordine P–D–C–A. */
export function fullRoleQuotas(quota: RosterRoleQuota | null | undefined): RoleQuotaStat[] {
  if (!quota) {
    return [];
  }
  return ROSTER_QUOTA_ROLES.map((role) => quota.roles[role]).filter((stat) => stat.full);
}

/** `true` se il ruolo è pieno: niente assegnazione per i suoi calciatori. */
export function isRoleQuotaFull(
  quota: RosterRoleQuota | null | undefined,
  role: FantasyRole | null | undefined,
): boolean {
  return Boolean(quota && role && isRole(role) && quota.roles[role].full);
}

function unresolvedNote(unresolved: number): string {
  if (unresolved <= 0) {
    return "";
  }
  return unresolved === 1
    ? " Nel conto c'è anche 1 calciatore senza ruolo nel listone."
    : ` Nel conto ci sono anche ${unresolved} calciatori senza ruolo nel listone.`;
}

export interface RoleQuotaMessageOptions {
  /** Squadra di un altro (l'admin assegna a lei): il messaggio la nomina. */
  teamName?: string | null;
  /** Calciatori senza ruolo inclusi nel conto (vedi `RosterRoleQuota.unresolved`). */
  unresolved?: number;
}

/**
 * «Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.»
 * oppure, per la squadra di un altro, «Real Tiki ha già 10 attaccanti su 10.»
 */
export function roleQuotaFullMessage(
  stat: Pick<RoleQuotaStat, "role" | "filled" | "max">,
  options: RoleQuotaMessageOptions = {},
): string {
  const plural = ROLE_QUOTA_PLURAL[stat.role];
  const teamName = options.teamName?.trim();
  const head = teamName
    ? `${teamName} ha già ${stat.filled} ${plural.toLowerCase()} su ${stat.max}.`
    : `${plural} al completo: ${stat.filled} su ${stat.max}. Per prenderne un altro prima svincolane uno.`;
  return head + unresolvedNote(options.unresolved ?? 0);
}

/** Riga per la scheda «Tutti»: «Al completo: Portieri (3/3), Attaccanti (10/10)». */
export function fullRolesSummary(quota: RosterRoleQuota | null | undefined): string | null {
  const full = fullRoleQuotas(quota);
  if (full.length === 0) {
    return null;
  }
  return `Al completo: ${full
    .map((stat) => `${ROLE_QUOTA_PLURAL[stat.role]} (${stat.filled}/${stat.max})`)
    .join(", ")}`;
}

/** Conto sulla scheda del ruolo: «10/10». */
export function roleQuotaCountLabel(stat: Pick<RoleQuotaStat, "filled" | "max">): string {
  return `${stat.filled}/${stat.max}`;
}

/**
 * Nome accessibile (e `title`) del pulsante «Assegna» spento per un calciatore di un ruolo pieno;
 * `reason` è il testo di `roleQuotaBlockReason`.
 */
export function roleQuotaBlockedLabel(athleteName: string, reason: string): string {
  return `Non puoi assegnare ${athleteName}. ${reason}`;
}

/**
 * Errore del server per quota superata (`role_quota_exceeded`) con lo stesso testo del client.
 * `null` per gli altri errori. Il server può spiegare che il limite lo superano contando chi è
 * senza ruolo («…: Rossi non ha un ruolo nel listone…»): quella parte resta in coda.
 */
export function roleQuotaErrorMessage(
  error: unknown,
  role: FantasyRole | null | undefined,
  quota: RosterRoleQuota | null | undefined,
  options: Pick<RoleQuotaMessageOptions, "teamName"> = {},
): string | null {
  if (!error || typeof error !== "object") {
    return null;
  }
  const { code, message } = error as { code?: unknown; message?: unknown };
  if (code !== ROLE_QUOTA_EXCEEDED_CODE || !role || !isRole(role)) {
    return null;
  }
  const text = typeof message === "string" ? message : "";
  const serverMax = Number(/raggiunto \((\d+)\)/.exec(text)?.[1]);
  const stat = quota?.roles[role];
  const max = Number.isFinite(serverMax) ? serverMax : stat?.max;
  if (max === undefined) {
    return null;
  }
  // Il server ha rifiutato: il ruolo è pieno anche se il conto del client era indietro.
  const filled = Math.max(stat?.filled ?? max, max);
  const detail = /raggiunto \(\d+\): (.+)$/.exec(text)?.[1]?.trim();
  const base = roleQuotaFullMessage(
    { role, filled, max },
    { teamName: options.teamName, unresolved: detail ? 0 : quota?.unresolved ?? 0 },
  );
  return detail ? `${base} ${detail.charAt(0).toUpperCase()}${detail.slice(1)}` : base;
}

export interface ListoneQuotaContext {
  /** Slot liberi della squadra: a rosa piena vale il comportamento di sempre, senza avvisi di ruolo. */
  emptySlotsCount: number;
  /** Squadra di un altro (l'admin assegna a lei); assente o `null` per la propria rosa. */
  teamName?: string | null;
}

/**
 * Perché un calciatore libero di quel ruolo non si può assegnare (testo da mostrare), o `null`
 * se il ruolo ha posto. A rosa piena (`emptySlotsCount` 0) resta `null`: lì l'assegnazione è
 * già spenta per tutti, come prima.
 */
export function roleQuotaBlockReason(
  quota: RosterRoleQuota | null | undefined,
  role: FantasyRole | null | undefined,
  context: ListoneQuotaContext,
): string | null {
  if (!quota || !role || !isRole(role) || context.emptySlotsCount <= 0) {
    return null;
  }
  const stat = quota.roles[role];
  if (!stat.full) {
    return null;
  }
  return roleQuotaFullMessage(stat, { teamName: context.teamName, unresolved: quota.unresolved });
}

/** Avviso in cima al listone per la scheda scelta: il ruolo pieno, o su «Tutti» i ruoli pieni. */
export function listoneQuotaNotice(
  quota: RosterRoleQuota | null | undefined,
  tab: "all" | FantasyRole,
  context: ListoneQuotaContext,
): string | null {
  if (context.emptySlotsCount <= 0) {
    return null;
  }
  return tab === "all" ? fullRolesSummary(quota) : roleQuotaBlockReason(quota, tab, context);
}
