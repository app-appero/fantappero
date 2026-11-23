/**
 * Riepilogo del pannello operatore (release 1.4, canvas «Proposte 1.3» scheda «Pannello
 * operatore», decisioni di Rosario del 22/11): le righe di «Da guardare» e la riga delle leghe
 * per stato, uguali sul sito e nell'app. Solo testo: ognuna delle due interfacce la disegna.
 *
 * Solo import di tipi: i test `node:test` dell'app caricano questo file dal sorgente.
 */

import type {
  AdminAppUsageGroup,
  AdminAppUsageGroupKind,
  AdminAppUsageSummary,
  AdminAppUsageUser,
  AdminListoneUpdate,
  AdminWatch,
  AdminWatchJobFailure,
} from "./admin.js";

/** Pallino della riga: verde (tutto a posto), ambra (da guardare), rosso (errore), grigio. */
export type OperatorWatchTone = "ok" | "warn" | "bad" | "idle";

/** Voce di menù del pannello a cui porta la riga (stessi id del menù di sito e app). */
export type OperatorWatchTarget =
  | "admin-users"
  | "admin-feedback"
  | "admin-jobs"
  | "admin-listone"
  | "admin-turni"
  | "admin-app-version";

export interface OperatorWatchItem {
  id: "testers" | "feedback" | "jobs" | "listone" | "rounds" | "app-version";
  tone: OperatorWatchTone;
  title: string;
  /** Righe sotto il titolo, già nell'ordine in cui si leggono. */
  details: string[];
  target: OperatorWatchTarget;
  /** Etichetta del link, come la voce di menù. */
  targetLabel: string;
}

const TARGET_LABELS: Record<OperatorWatchTarget, string> = {
  "admin-users": "Utenti",
  "admin-feedback": "Segnalazioni",
  "admin-jobs": "Job automatici",
  "admin-listone": "Listone",
  "admin-turni": "Turni",
  "admin-app-version": "Versione app",
};

/** Quanti job con errore si elencano uno per uno; gli altri si contano. */
const MAX_FAILURE_LINES = 3;
const ROME = "Europe/Rome";

type RomeParts = { year: number; month: number; day: number; hour: string; minute: string };

function romeParts(date: Date): RomeParts {
  const formatter = new Intl.DateTimeFormat("it-IT", {
    timeZone: ROME,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  let year = 0;
  let month = 0;
  let day = 0;
  let hour = "0";
  let minute = "00";
  if (typeof formatter.formatToParts === "function") {
    const parts = formatter.formatToParts(date);
    const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
    year = Number(pick("year"));
    month = Number(pick("month"));
    day = Number(pick("day"));
    hour = pick("hour");
    minute = pick("minute");
  } else {
    // Motori senza formatToParts: «22/11/2026, 15:00».
    const match = /(\d{1,2})\/(\d{1,2})\/(\d{4})\D+(\d{1,2}):(\d{2})/.exec(formatter.format(date));
    if (match) {
      day = Number(match[1]);
      month = Number(match[2]);
      year = Number(match[3]);
      hour = match[4] ?? "0";
      minute = match[5] ?? "00";
    }
  }
  // Alcuni motori scrivono la mezzanotte come «24».
  return { year, month, day, hour: hour === "24" ? "00" : hour, minute };
}

function parse(value: string | Date | null | undefined): Date | null {
  if (!value) {
    return null;
  }
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Giorni di calendario (ora italiana) da `now` a `value`: 0 oggi, -1 ieri, 1 domani. */
function romeDayOffset(value: Date, now: Date): number {
  const a = romeParts(value);
  const b = romeParts(now);
  const dayA = Date.UTC(a.year, a.month - 1, a.day);
  const dayB = Date.UTC(b.year, b.month - 1, b.day);
  return Math.round((dayA - dayB) / 86_400_000);
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** «19/11», nell'ora italiana. */
export function formatRomeDayMonth(value: string | Date | null | undefined): string {
  const date = parse(value);
  if (!date) {
    return "—";
  }
  const parts = romeParts(date);
  return `${pad(parts.day)}/${pad(parts.month)}`;
}

/** «oggi alle 15:00», «ieri alle 21:40», «domani alle 9:05» o «19/11 alle 15:00». */
export function formatRomeWhen(value: string | Date | null | undefined, now: Date = new Date()): string {
  const date = parse(value);
  if (!date) {
    return "—";
  }
  const parts = romeParts(date);
  const time = `${Number(parts.hour)}:${parts.minute}`;
  const offset = romeDayOffset(date, now);
  if (offset === 0) {
    return `oggi alle ${time}`;
  }
  if (offset === -1) {
    return `ieri alle ${time}`;
  }
  if (offset === 1) {
    return `domani alle ${time}`;
  }
  return `${pad(parts.day)}/${pad(parts.month)} alle ${time}`;
}

/** «oggi», «ieri», «3 giorni fa» (giorni di calendario, ora italiana). */
export function formatRomeDaysAgo(value: string | Date | null | undefined, now: Date = new Date()): string {
  const date = parse(value);
  if (!date) {
    return "—";
  }
  const days = -romeDayOffset(date, now);
  if (days <= 0) {
    return "oggi";
  }
  if (days === 1) {
    return "ieri";
  }
  return `${days} giorni fa`;
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

const STATE_ORDER: { states: string[]; one: string; many: string }[] = [
  { states: ["active"], one: "in corso", many: "in corso" },
  { states: ["auction"], one: "all'asta", many: "all'asta" },
  { states: ["draft", "configuring"], one: "in preparazione", many: "in preparazione" },
  { states: ["concluded"], one: "conclusa", many: "concluse" },
  { states: ["archived"], one: "archiviata", many: "archiviate" },
];

/** «2 in corso · 1 all'asta · 1 in preparazione». Vuoto se non ci sono leghe. */
export function formatLeaguesByState(counts: Record<string, number> | null | undefined): string {
  if (!counts) {
    return "";
  }
  const known = new Set(STATE_ORDER.flatMap((group) => group.states));
  const pieces: string[] = [];
  for (const group of STATE_ORDER) {
    const total = group.states.reduce((sum, state) => sum + (counts[state] ?? 0), 0);
    if (total > 0) {
      pieces.push(`${total} ${plural(total, group.one, group.many)}`);
    }
  }
  for (const [state, total] of Object.entries(counts)) {
    if (!known.has(state) && total > 0) {
      pieces.push(`${total} ${state}`);
    }
  }
  return pieces.join(" · ");
}

function item(
  id: OperatorWatchItem["id"],
  tone: OperatorWatchTone,
  title: string,
  details: string[],
  target: OperatorWatchTarget,
): OperatorWatchItem {
  return { id, tone, title, details, target, targetLabel: TARGET_LABELS[target] };
}

function testersItem(watch: AdminWatch, now: Date): OperatorWatchItem {
  const count = watch.testerRequestsPending;
  if (count <= 0) {
    return item("testers", "ok", "Nessuna richiesta tester in attesa", [], "admin-users");
  }
  const oldest = watch.oldestTesterRequestAt;
  const details: string[] = [];
  if (oldest) {
    details.push(
      count === 1
        ? `Arrivata ${formatRomeWhen(oldest, now)}`
        : `La più vecchia è di ${formatRomeDaysAgo(oldest, now)}`,
    );
  }
  return item(
    "testers",
    "warn",
    `${count} ${plural(count, "richiesta tester in attesa", "richieste tester in attesa")}`,
    details,
    "admin-users",
  );
}

function feedbackItem(watch: AdminWatch, now: Date): OperatorWatchItem {
  const count = watch.feedbackNew;
  if (count <= 0) {
    return item("feedback", "ok", "Nessuna segnalazione nuova", [], "admin-feedback");
  }
  const details = watch.latestFeedbackAt
    ? [
        count === 1
          ? `Arrivata ${formatRomeWhen(watch.latestFeedbackAt, now)}`
          : `L'ultima ${formatRomeWhen(watch.latestFeedbackAt, now)}`,
      ]
    : [];
  return item(
    "feedback",
    "warn",
    `${count} ${plural(count, "segnalazione nuova", "segnalazioni nuove")}`,
    details,
    "admin-feedback",
  );
}

function failureLine(failure: AdminWatchJobFailure, now: Date): string {
  const times = failure.failures > 1 ? ` (${failure.failures} volte)` : "";
  const raw = failure.reason?.trim() || "motivo non registrato";
  const reason = /[.!?…]$/.test(raw) ? raw : `${raw}.`;
  const recovered = failure.lastOutcome === "ok" ? " Poi è ripartito bene." : "";
  return `Errore in «${failure.title}» ${formatRomeWhen(failure.failedAt, now)}${times}: ${reason}${recovered}`;
}

function jobsItem(watch: AdminWatch, now: Date): OperatorWatchItem {
  const disabled = watch.jobsDisabled;
  const failures = watch.jobFailures;
  let title: string;
  if (disabled.length > 0) {
    const names = disabled.map((job) => job.title).join(", ");
    title = `${disabled.length} ${plural(disabled.length, "job spento", "job spenti")}: ${names}`;
  } else if (failures.length > 0) {
    title = `${failures.length} job con errori nelle ultime 24 ore`;
  } else {
    title = "Tutti i job sono accesi";
  }
  const details = failures.slice(0, MAX_FAILURE_LINES).map((failure) => failureLine(failure, now));
  if (failures.length > MAX_FAILURE_LINES) {
    const others = failures.length - MAX_FAILURE_LINES;
    details.push(`E altri ${others} job con errori.`);
  }
  if (failures.length === 0) {
    details.push("Nessun errore nelle ultime 24 ore");
  }
  const stillFailing = failures.some((failure) => failure.lastOutcome === "failed");
  const tone: OperatorWatchTone = stillFailing
    ? "bad"
    : failures.length > 0 || disabled.length > 0
      ? "warn"
      : "ok";
  return item("jobs", tone, title, details, "admin-jobs");
}

function countLabel(count: number, one: string, many: string): string {
  return `${count} ${plural(count, one, many)}`;
}

/** «3 nuovi, 1 tolto, 12 cambiati» (o il riassunto dei ruoli). */
export function listoneUpdateSummary(update: AdminListoneUpdate): string {
  if (update.kind === "roles_from_provider") {
    return `Ruoli presi dal fornitore: ${countLabel(update.changed, "calciatore", "calciatori")}`;
  }
  if (update.kind === "roles_restored") {
    return `Ruoli ripristinati: ${countLabel(update.changed, "calciatore", "calciatori")}`;
  }
  return [
    countLabel(update.added, "nuovo", "nuovi"),
    countLabel(update.removed, "tolto", "tolti"),
    countLabel(update.changed, "cambiato", "cambiati"),
  ].join(", ");
}

function listoneItem(watch: AdminWatch, now: Date): OperatorWatchItem {
  const update = watch.listoneLastUpdate;
  if (!update) {
    return item(
      "listone",
      "idle",
      "Nessun aggiornamento del listone registrato",
      ["Da qui in poi ogni aggiornamento resta salvato con data, autore e riassunto."],
      "admin-listone",
    );
  }
  const who = update.authorDisplayName ? `da ${update.authorDisplayName}` : "autore non registrato";
  const where = update.source === "league" && update.leagueName ? ` (lega ${update.leagueName})` : "";
  return item(
    "listone",
    "ok",
    `Listone aggiornato il ${formatRomeDayMonth(update.updatedAt)}`,
    [`${formatRomeDaysAgo(update.updatedAt, now)} · ${who}${where}`, listoneUpdateSummary(update)],
    "admin-listone",
  );
}

function roundsItem(watch: AdminWatch, now: Date): OperatorWatchItem {
  const rounds = watch.currentRounds;
  const lock = watch.nextLineupLock;
  const lockLine = lock
    ? `Prossimo blocco formazioni: ${formatRomeWhen(lock.lockAt, now)} (${lock.leagueName}, giornata ${lock.roundNumber})`
    : "Nessun blocco formazioni in arrivo";
  if (rounds.activeLeagues <= 0) {
    return item("rounds", "idle", "Nessuna lega in corso", [lockLine], "admin-turni");
  }
  if (rounds.leaguesInProgress <= 0) {
    return item("rounds", "ok", "Nessuna giornata in corso", [lockLine], "admin-turni");
  }
  const numbers = [...rounds.roundNumbers].sort((a, b) => a - b);
  const label =
    numbers.length <= 1
      ? `Giornata ${numbers[0] ?? ""}`.trim()
      : `Giornate ${numbers[0]}–${numbers[numbers.length - 1]}`;
  const where = `${rounds.leaguesInProgress} ${plural(rounds.leaguesInProgress, "lega", "leghe")} su ${rounds.activeLeagues}`;
  return item("rounds", "ok", `${label} in corso in ${where}`, [lockLine], "admin-turni");
}

function appVersionItem(watch: AdminWatch): OperatorWatchItem {
  const android = watch.androidAppVersion;
  if (!android) {
    return item(
      "app-version",
      "idle",
      "Nessuna versione dell'app annunciata",
      ["Nell'app non compare nessun avviso"],
      "admin-app-version",
    );
  }
  const usage = watch.androidAppUsage;
  return item(
    "app-version",
    "ok",
    `App Android annunciata: ${android.latestVersionName}`,
    [usage ? appUsageSummaryLine(usage) : "Chi ha una versione più vecchia vede l'avviso"],
    "admin-app-version",
  );
}

// --- «Chi ha quale versione» della pagina «Versione app» (release 1.4, Rosario 23/11) --------

/** «4 utenti aggiornati su 12 che usano l'app». */
export function appUsageSummaryLine(usage: AdminAppUsageSummary): string {
  const up = usage.upToDateUsers;
  const all = usage.appUsers;
  return `${up} ${plural(up, "utente aggiornato", "utenti aggiornati")} su ${all} che ${plural(all, "usa", "usano")} l'app`;
}

/**
 * Nome del gruppo: «1.4.0 (5)», «Versione non nota (app 1.2 o 1.3)», «Sito da Android (app non
 * installata o non ancora vista)», «App mai usata / solo sito».
 */
export function appUsageGroupLabel(group: AdminAppUsageGroup): string {
  switch (group.kind) {
    case "version": {
      const name = group.versionName?.trim();
      const base = name ? `${name} (${group.versionCode ?? "?"})` : `versionCode ${group.versionCode ?? "?"}`;
      return group.platform && group.platform !== "android" ? `${base} · ${group.platform === "ios" ? "iOS" : group.platform}` : base;
    }
    case "unknown_recent":
      return "Versione non nota (app 1.2 o 1.3)";
    case "unknown":
      return "Versione non nota (app 1.1 o precedente)";
    case "web_android":
      return "Sito da Android (app non installata o non ancora vista)";
    default:
      return "App mai usata / solo sito";
  }
}

/** Titolo del gruppo con il conteggio: «1.4.0 (5): 7 utenti». */
export function appUsageGroupTitle(group: AdminAppUsageGroup): string {
  const count = group.users.length;
  return `${appUsageGroupLabel(group)}: ${count} ${plural(count, "utente", "utenti")}`;
}

/** Riga di spiegazione sotto i gruppi che non hanno una versione esatta; vuota per le altre. */
export function appUsageGroupHint(group: AdminAppUsageGroup): string {
  switch (group.kind) {
    case "unknown_recent":
      return "Controllano gli aggiornamenti ma non dicono la versione: si vedrà dalla 1.4 in poi.";
    case "unknown":
      return "Usano l'app ma non controllano gli aggiornamenti.";
    case "web_android":
      return "Usano il sito da un telefono Android: ricevono anche loro la notifica della nuova versione.";
    case "never":
      return "Nessun accesso dall'app né dal sito da Android da quando il server registra le versioni: non ricevono la notifica della nuova versione.";
    default:
      return "";
  }
}

/** «Bomber (Mario Rossi)»: il soprannome e, se diverso, il nome. */
export function appUsageUserName(user: AdminAppUsageUser): string {
  return user.name ? `${user.displayName} (${user.name})` : user.displayName;
}

/**
 * «visto nell'app oggi alle 15:00» («visto sul sito da Android …» nel gruppo `web_android`);
 * vuoto per chi non è mai stato visto.
 */
export function appUsageUserSeen(
  user: AdminAppUsageUser,
  now: Date = new Date(),
  kind: AdminAppUsageGroupKind = "version",
): string {
  if (!user.lastSeenAt) {
    return "";
  }
  const where = kind === "web_android" ? "sul sito da Android" : "nell'app";
  return `visto ${where} ${formatRomeWhen(user.lastSeenAt, now)}`;
}

/** Le sei righe di «Da guardare», nell'ordine del canvas approvato. */
export function buildOperatorWatchItems(watch: AdminWatch, now: Date = new Date()): OperatorWatchItem[] {
  return [
    testersItem(watch, now),
    feedbackItem(watch, now),
    jobsItem(watch, now),
    listoneItem(watch, now),
    roundsItem(watch, now),
    appVersionItem(watch),
  ];
}
