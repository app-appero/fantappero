/**
 * Pannello operatore → Listone → «Aggiorna listone dal provider» (sito dal 22/11, app dalla
 * 1.5): la finestra con la scelta (tenere i ruoli o aggiornarli), l'anteprima dei ruoli che
 * cambierebbero e «Ripristina i ruoli cambiati da un aggiornamento». Testi e funzioni uguali
 * sul sito e nell'app.
 *
 * Solo logica pura e import di tipo: i test `node:test` dell'app caricano questo file dal
 * sorgente.
 */
import type {
  AdminListoneProviderRolesCounts,
  AdminListoneRoleRestoreCounts,
} from "./admin.js";

/** «Aggiorna listone»: solo nuovi calciatori e squadre (default) o anche i ruoli. */
export type ListoneRefreshMode = "keep_roles" | "update_roles";

export const LISTONE_REFRESH_BUTTON_LABEL = "Aggiorna listone dal provider";
export const LISTONE_REFRESH_TITLE = "Aggiorna listone dal provider";
export const LISTONE_REFRESH_QUESTION = "Cosa vuoi aggiornare?";
export const LISTONE_REFRESH_CANCEL_LABEL = "Annulla";

export const LISTONE_REFRESH_OPTIONS: ReadonlyArray<{
  mode: ListoneRefreshMode;
  title: string;
  hint: string;
}> = [
  {
    mode: "keep_roles",
    title: "Aggiungi i nuovi calciatori e aggiorna le squadre",
    hint: "I ruoli dei calciatori già nel listone restano come sono.",
  },
  {
    mode: "update_roles",
    title: "Aggiorna anche i ruoli dal fornitore",
    hint: "Prima vedi chi cambierebbe ruolo e in quali rose, poi confermi o annulli.",
  },
];

export const LISTONE_REFRESH_ROLES_WARNING =
  "Alcuni calciatori possono cambiare ruolo e le rose che li hanno possono andare fuori quota.";

/** Pulsante che avvia l'aggiornamento nella finestra di scelta. */
export function listoneRefreshStartLabel(mode: ListoneRefreshMode): string {
  return mode === "update_roles" ? "Aggiorna e mostra i ruoli" : "Aggiorna listone";
}

/** Esito dell'aggiornamento, con i ruoli lasciati com'erano se il fornitore ne indica un altro. */
export function listoneRefreshSummary(
  message: string,
  created: number,
  updated: number,
  skipped: number,
): string {
  const base = `${message} Creati: ${created}, aggiornati: ${updated}.`;
  if (skipped === 0) {
    return base;
  }
  return `${base} Ruoli lasciati com'erano (il fornitore ne indica un altro): ${skipped}.`;
}

// --- Anteprima dei ruoli che cambierebbero ----------------------------------------------

export const LISTONE_ROLE_PREVIEW_TITLE = "Ruoli che cambierebbero dal fornitore";
export const LISTONE_ROLE_PREVIEW_INTRO =
  "Il listone è già aggiornato (nuovi calciatori e squadre); i ruoli non sono ancora cambiati. Con la conferma cambiano e le rose che li hanno vengono ricalcolate.";
export const LISTONE_ROLE_PREVIEW_CONFIRM_LABEL = "Conferma i nuovi ruoli";
export const LISTONE_ROLE_PREVIEW_CANCEL_LABEL = "Annulla: i ruoli restano come sono";
export const LISTONE_ROLE_PREVIEW_ERROR_TITLE = "Ruoli non aggiornati";
export const LISTONE_ROLE_PREVIEW_ERROR_FALLBACK = "Aggiornamento dei ruoli non riuscito.";
export const LISTONE_ROLES_KEPT_MESSAGE = "Ruoli lasciati come sono: nessun ruolo è cambiato.";

/** «3 calciatori cambierebbero ruolo» / «1 calciatore cambierebbe ruolo». */
export function listoneRoleChangesLabel(changes: number): string {
  return changes === 1
    ? "1 calciatore cambierebbe ruolo"
    : `${changes} calciatori cambierebbero ruolo`;
}

/** Riga di sintesi dell'anteprima: chi cambia e le rose fuori quota prima e dopo. */
export function listoneRoleChangesParts(counts: Pick<
  AdminListoneProviderRolesCounts,
  "changes" | "rostersOverQuotaNow" | "rostersOverQuotaAfter"
>): { changes: string; overQuotaNow: number; overQuotaAfter: number } {
  return {
    changes: listoneRoleChangesLabel(counts.changes),
    overQuotaNow: counts.rostersOverQuotaNow,
    overQuotaAfter: counts.rostersOverQuotaAfter,
  };
}

/** Testo intero della riga di sintesi dell'anteprima (senza grassetti). */
export function listoneRoleChangesSummary(
  counts: Pick<
    AdminListoneProviderRolesCounts,
    "changes" | "rostersOverQuotaNow" | "rostersOverQuotaAfter"
  >,
): string {
  const parts = listoneRoleChangesParts(counts);
  return `${parts.changes} · Rose fuori quota con questi calciatori: ora ${parts.overQuotaNow}, con i nuovi ruoli ${parts.overQuotaAfter}`;
}

/** Esito dopo «Conferma i nuovi ruoli». */
export function listoneRolesAppliedMessage(
  counts: Pick<AdminListoneProviderRolesCounts, "applied" | "rostersResynced">,
): string {
  return `Ruoli aggiornati dal fornitore: ${counts.applied}. Rose ricalcolate: ${counts.rostersResynced}.`;
}

// --- Ripristina i ruoli cambiati da un aggiornamento --------------------------------------

export const LISTONE_RESTORE_TITLE = "Ripristina i ruoli cambiati da un aggiornamento";
export const LISTONE_RESTORE_INTRO =
  "Se un aggiornamento del listone ha cambiato il ruolo di calciatori già nelle rose, qui li riporti al ruolo che avevano prima dell'ora scelta. Il ruolo si ricostruisce dalle rose del fornitore salvate prima di quell'ora. Prima guardi cosa cambia, poi confermi.";
export const LISTONE_RESTORE_BEFORE_LABEL = "Ruoli com'erano prima del (ora di Roma)";
export const LISTONE_RESTORE_PREVIEW_LABEL = "Mostra cosa cambia";
export const LISTONE_RESTORE_APPLY_LABEL = "Ripristina";
export const LISTONE_RESTORE_CONFIRM_YES_LABEL = "Sì, ripristina";
export const LISTONE_RESTORE_CONFIRM_NO_LABEL = "Annulla";
export const LISTONE_RESTORE_INVALID_INPUT = "Scegli una stagione e una data e ora valide.";

/** L'ora prima dell'aggiornamento del 21/11 su pilota (ora di Roma). */
export const DEFAULT_RESTORE_BEFORE = "2026-11-21T12:00";

const ROME = "Europe/Rome";
const LOCAL_DATE_TIME = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/;

function romeOffsetMs(utcMs: number): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: ROME,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((item) => item.type === type)?.value ?? "0");
  const wall = Date.UTC(
    part("year"),
    part("month") - 1,
    part("day"),
    part("hour"),
    part("minute"),
    part("second"),
  );
  return wall - utcMs;
}

/**
 * «2026-11-21T12:00» (o «2026-11-21 12:00»), ora di Roma qualunque sia il fuso del dispositivo →
 * ISO in UTC. `null` se il testo non è una data e ora.
 */
export function romeLocalToIso(value: string): string | null {
  const match = LOCAL_DATE_TIME.exec(value.trim());
  if (!match) {
    return null;
  }
  const [year, month, day, hour, minute] = match.slice(1, 6).map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ];
  const wall = Date.UTC(year, month - 1, day, hour, minute);
  let utc = wall - romeOffsetMs(wall);
  utc = wall - romeOffsetMs(utc);
  return new Date(utc).toISOString();
}

/** «21/11/2026 alle 12:00» da «2026-11-21T12:00» (o con lo spazio). */
export function formatRomeLocal(value: string): string {
  const match = LOCAL_DATE_TIME.exec(value.trim());
  if (!match) {
    return value;
  }
  const [, year, month, day, hour, minute] = match;
  return `${day}/${month}/${year} alle ${hour}:${minute}`;
}

/** Anteprima del ripristino: da ripristinare, non ricostruibili, rose fuori quota prima e dopo. */
export function listoneRestoreSummary(
  counts: Pick<
    AdminListoneRoleRestoreCounts,
    "toRestore" | "notReconstructible" | "rostersOverQuotaNow" | "rostersOverQuotaAfter"
  >,
): string {
  return `Da ripristinare: ${counts.toRestore} · Non ricostruibili: ${counts.notReconstructible} · Rose fuori quota con questi calciatori: ora ${counts.rostersOverQuotaNow}, dopo il ripristino ${counts.rostersOverQuotaAfter}`;
}

export function listoneRestoreEmptyMessage(before: string): string {
  return `Nessun ruolo cambiato dopo il ${formatRomeLocal(before)}.`;
}

/** Domanda di conferma del ripristino. */
export function listoneRestoreConfirmText(toRestore: number, before: string): string {
  return `Riporti ${toRestore === 1 ? "1 calciatore" : `${toRestore} calciatori`} al ruolo che avevano prima del ${formatRomeLocal(before)}. Le rose che li hanno vengono ricalcolate. I non ricostruibili restano come sono. Confermi?`;
}

/** Esito dopo «Sì, ripristina». */
export function listoneRestoreDoneMessage(
  counts: Pick<AdminListoneRoleRestoreCounts, "restored" | "rostersResynced">,
): string {
  return `Ruoli ripristinati: ${counts.restored}. Rose ricalcolate: ${counts.rostersResynced}. Controlla le rose e la generazione del calendario.`;
}
