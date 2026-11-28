/** Admin panel contracts — platform operator only (EP11-04a / EP11-04b). */

import type { AndroidAppVersion } from "./appVersion.js";
import type { SessionUser } from "./auth.js";
import type { FantasyRole } from "./leagues.js";

export type PlatformRole = "user" | "operator";

/** Short-lived, access-only session for support impersonation — no refresh token. */
export interface AdminImpersonateResult {
  accessToken: string;
  expiresIn: number;
  user: SessionUser;
}

export interface AdminOverview {
  operatorId: string;
  operatorDisplayName: string;
  environment: string;
  usersCount: number;
  operatorsCount: number;
  leaguesCount: number;
  /** Riepilogo 1.4: leghe per stato (`active`, `auction`, …). Assente dai server più vecchi. */
  leaguesByState?: Record<string, number>;
  /** Riepilogo 1.4: «Da guardare». Assente dai server più vecchi o se il calcolo non riesce. */
  watch?: AdminWatch | null;
}

/** Un job periodico spento dal pannello. */
export interface AdminWatchJob {
  key: string;
  title: string;
}

/** Un job con giri finiti con errore nel periodo guardato (l'errore più recente). */
export interface AdminWatchJobFailure {
  jobKey: string;
  title: string;
  failedAt: string;
  /** Motivo in breve (messaggio e tipo tecnico tra parentesi). */
  reason: string | null;
  /** Quanti giri finiti con errore nel periodo. */
  failures: number;
  /** Esito dell'ultimo giro, anche dopo l'errore: `ok` = il job è già ripreso. */
  lastOutcome: "ok" | "failed";
  lastFinishedAt: string;
}

export type AdminListoneUpdateKind = "refresh" | "roles_from_provider" | "roles_restored";

/** Ultimo aggiornamento del listone, salvato per sempre (release 1.4). */
export interface AdminListoneUpdate {
  updatedAt: string;
  seasonYear: number;
  kind: AdminListoneUpdateKind;
  /** `operator` dal pannello operatore, `league` dalla pagina di una lega. */
  source: "operator" | "league";
  authorDisplayName: string | null;
  leagueName: string | null;
  added: number;
  removed: number;
  changed: number;
}

/** Giornate in corso (turno aperto, o bloccato con la finestra aperta) nelle leghe attive. */
export interface AdminCurrentRounds {
  activeLeagues: number;
  leaguesInProgress: number;
  roundNumbers: number[];
}

/** Il prossimo blocco delle formazioni fra tutte le leghe attive. */
export interface AdminNextLineupLock {
  lockAt: string;
  leagueId: string;
  leagueName: string;
  roundNumber: number;
}

/** «Da guardare» del Riepilogo operatore (decisioni di Rosario del 22/11). */
export interface AdminWatch {
  generatedAt: string;
  testerRequestsPending: number;
  oldestTesterRequestAt: string | null;
  feedbackNew: number;
  latestFeedbackAt: string | null;
  jobsDisabled: AdminWatchJob[];
  /** Da quando si guardano gli errori dei job (oggi: le ultime 24 ore). */
  jobFailuresSince: string;
  jobFailures: AdminWatchJobFailure[];
  listoneLastUpdate: AdminListoneUpdate | null;
  currentRounds: AdminCurrentRounds;
  nextLineupLock: AdminNextLineupLock | null;
  androidAppVersion: AndroidAppVersion | null;
  /** Release 1.4: aggiornati su chi usa l'app. Assente dai server più vecchi o senza annuncio. */
  androidAppUsage?: AdminAppUsageSummary | null;
}

/** Riga «App Android annunciata» del Riepilogo: quanti hanno la versione annunciata. */
export interface AdminAppUsageSummary {
  /** Utenti con la versione annunciata o una più nuova (versione esatta, app 1.4+). */
  upToDateUsers: number;
  /** Utenti visti almeno una volta nell'app, qualsiasi versione (il sito da Android non conta). */
  appUsers: number;
}

/**
 * Gruppo dell'elenco «chi ha quale versione» (release 1.4, Rosario 23/11):
 * - `version`: versione esatta, mandata dall'app 1.4 o successive;
 * - `unknown_recent`: app 1.2 o 1.3 (controllano gli aggiornamenti ma non dicono la versione);
 * - `unknown`: app che non dice nulla (1.1 o precedente);
 * - `web_android`: mai visto nell'app ma visto sul sito da un telefono Android (riceve anche lui
 *   la notifica della nuova versione); assente dai server più vecchi;
 * - `never`: mai visto nell'app né sul sito da Android (sito da computer o iPhone, o mai entrato).
 */
export type AdminAppUsageGroupKind = "version" | "unknown_recent" | "unknown" | "web_android" | "never";

export interface AdminAppUsageUser {
  userId: string;
  /** Soprannome se scelto, altrimenti nome. */
  displayName: string;
  /** Nome del profilo, solo se diverso da `displayName`. */
  name: string | null;
  email: string;
  firstSeenAt: string | null;
  /** Ultima volta visto nell'app (nel gruppo `web_android`: sul sito da Android); `null` nel gruppo `never`. */
  lastSeenAt: string | null;
}

export interface AdminAppUsageGroup {
  kind: AdminAppUsageGroupKind;
  /** `android` (o `ios`); `web-android` nel gruppo `web_android`; `null` nel gruppo `never`. */
  platform: string | null;
  versionName: string | null;
  versionCode: number | null;
  /** Ha la versione annunciata o una più nuova. */
  upToDate: boolean;
  /** Il più recente prima (gruppo `never`: in ordine di nome). */
  users: AdminAppUsageUser[];
}

/** `GET /admin/app-version/users`: chi ha quale versione dell'app, versione per versione. */
export interface AdminAppUsage {
  generatedAt: string;
  announced: AndroidAppVersion | null;
  /** Utenti attivi (account non eliminati). */
  totalUsers: number;
  appUsers: number;
  upToDateUsers: number;
  /** Versioni esatte (la più nuova prima), poi versioni non note, sito da Android, «app mai usata». */
  groups: AdminAppUsageGroup[];
}

export interface AdminUser {
  id: string;
  email: string;
  displayName: string;
  platformRole: PlatformRole;
  createdAt: string;
  /** Autorizzato in modalità test (in lista oppure operatore). */
  isTester?: boolean;
  /** Operatore protetto: non declassabile, eliminabile né bloccabile. */
  isProtected?: boolean;
  /** Numero di leghe a cui partecipa. */
  leagueCount?: number;
}

export interface AdminBlockedAccount {
  id: string;
  email: string;
  reason: string | null;
  createdAt: string;
}

export interface AdminBlocklist {
  items: AdminBlockedAccount[];
}

export interface AdminDeleteUserResult {
  deletedUserId: string;
  /** Email messa in lista nera; null se eliminato senza bloccarlo. */
  blockedEmail: string | null;
}

export interface AdminTester {
  id: string;
  email: string;
  /** Nome dell'account, se la persona ha già acceduto. */
  displayName: string | null;
  createdAt: string;
}

export interface AdminTestMode {
  enabled: boolean;
  testers: AdminTester[];
}

export interface PaginatedAdminUsers {
  items: AdminUser[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface AdminLeague {
  id: string;
  name: string;
  state: string;
  ownerDisplayName: string | null;
  createdAt: string;
}

export interface PaginatedAdminLeagues {
  items: AdminLeague[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface AdminListoneEntry {
  athleteId: string;
  canonicalName: string;
  seasonYear: number;
  officialRole: FantasyRole;
  providerPositionRaw: string | null;
  mappingVersion: string;
  clubId: string | null;
  clubName: string | null;
}

export interface AdminListoneRefreshCounters {
  athletesCreated: number;
  athletesUpdated: number;
  membershipsCreated: number;
  membershipsUpdated: number;
  transfersCreated: number;
  listoneCreated: number;
  listoneUpdated: number;
  listoneUnchanged: number;
  listoneSkippedUnmapped: number;
  /** Ruoli che il fornitore cambierebbe ma che restano quelli del listone (congelati). */
  roleChangesSkipped: number;
  /** Calciatori tolti dal listone (release 1.4; assente dai server più vecchi). */
  listoneRemoved?: number;
  catalogSynced: boolean;
}

/** «Aggiorna anche i ruoli dal fornitore» (POST /admin/listone/ruoli-dal-fornitore). */
export interface AdminListoneProviderRolesRequest {
  seasonYear: number;
  dryRun: boolean;
  /** Solo questi calciatori (quelli dell'anteprima confermata). */
  athleteIds?: string[];
}

export interface AdminListoneProviderRoleEntry {
  athleteId: string;
  name: string;
  club: string | null;
  currentRole: FantasyRole;
  newRole: FantasyRole;
  providerPositionRaw: string | null;
  /** Leghe (non concluse) in cui il calciatore è in rosa. */
  inRosters: string[];
}

export interface AdminListoneProviderRolesCounts {
  changes: number;
  applied: number;
  rostersOverQuotaNow: number;
  rostersOverQuotaAfter: number;
  rostersResynced: number;
}

export interface AdminListoneProviderRolesResult {
  seasonYear: number;
  dryRun: boolean;
  entries: AdminListoneProviderRoleEntry[];
  counts: AdminListoneProviderRolesCounts;
}

export interface AdminListoneRefreshResult {
  seasonYear: number;
  mappingVersion: string;
  refreshedAt: string;
  message: string;
  counters: AdminListoneRefreshCounters;
  /** Con `updateRoles`: anteprima dei ruoli che cambierebbero, da confermare. */
  roleChanges?: AdminListoneProviderRolesResult | null;
}

/** «Ripristina i ruoli cambiati da un aggiornamento» (POST /admin/listone/ripristina-ruoli). */
export interface AdminListoneRoleRestoreRequest {
  seasonYear: number;
  /** ISO 8601 con fuso orario: ruoli com'erano prima di questo momento. */
  before: string;
  dryRun: boolean;
  /** Solo questi calciatori (quelli dell'anteprima confermata). */
  athleteIds?: string[];
}

export interface AdminListoneRoleRestoreEntry {
  athleteId: string;
  name: string;
  club: string | null;
  currentRole: FantasyRole;
  /** `null` = non ricostruibile dalle risposte salvate del fornitore. */
  restoredRole: FantasyRole | null;
  reconstructible: boolean;
  restoredPosition: string | null;
  restoredClub: string | null;
  restoredSource: string | null;
  /** Leghe (non concluse) in cui il calciatore è in rosa. */
  inRosters: string[];
}

export interface AdminListoneRoleRestoreCounts {
  toRestore: number;
  notReconstructible: number;
  restored: number;
  rostersOverQuotaNow: number;
  rostersOverQuotaAfter: number;
  rostersResynced: number;
}

export interface AdminListoneRoleRestoreResult {
  seasonYear: number;
  before: string;
  dryRun: boolean;
  entries: AdminListoneRoleRestoreEntry[];
  counts: AdminListoneRoleRestoreCounts;
}

export interface AdminListoneRefreshJob {
  jobId: string;
  status: string;
  message: string;
}

export interface AdminListoneRefreshProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminListoneRefreshResult | null;
}

/**
 * Pannello operatore — turni, calendario, formazioni IA (EP-turni-automazione).
 *
 * Riga di sintesi per una lega attiva: il "turno corrente" è quello aperto,
 * o il primo programmato, o l'ultimo esistente se la lega è a fine stagione.
 */
export interface AdminLeagueTurnStatus {
  leagueId: string;
  leagueName: string;
  currentRoundId: string | null;
  currentRoundNumber: number | null;
  currentRoundStatus: string | null;
  homologationStatus: string | null;
  calendarUpdatedAt: string | null;
}

/** Esito di "Sincronizza turni" massivo (tutte le leghe attive). */
export interface AdminTurniSyncResult {
  leagues: number;
  created: number;
  opened: number;
  upgraded: number;
  duplicates: number;
  waiting: number;
}

/** Esito di "Genera formazioni AI" massivo (tutte le leghe attive). */
export interface AdminAiLineupsSyncResult {
  rounds: number;
  teamsUpdated: number;
  teamsSkipped: number;
}

export interface AdminCalendarSyncJob {
  jobId: string;
  status: string;
  message: string;
}

/** Esito di "Genera calendario" massivo (tutte le leghe attive). */
export interface AdminCalendarSyncResult {
  leagues: number;
  refreshed: number;
  failed: number;
  fixturesCreated: number;
  fixturesUpdated: number;
  roundsRealigned: number;
  roundsRemoved: number;
}

export interface AdminCalendarSyncProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminCalendarSyncResult | null;
}

export interface AdminSeasonImportJob {
  jobId: string;
  status: string;
  message: string;
}

/** Esito di "Importa calendario stagione" (catalogo + fixture, tutte le MVP). */
export interface AdminSeasonImportResult {
  seasonsCreated: number;
  seasonsUpdated: number;
  competitionsUpdated: number;
  fixturesCreated: number;
  fixturesUpdated: number;
}

export interface AdminSeasonImportProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminSeasonImportResult | null;
}

export interface SystemJob {
  key: string;
  title: string;
  description: string;
  task: string;
  enabled: boolean;
  intervalSeconds: number;
  minIntervalSeconds: number;
  maxIntervalSeconds: number;
  lastStartedAt: string | null;
  nextRunAt: string | null;
  /** Il giro chiama il fornitore sportivo e ne consuma la quota (1.5). */
  usesProviderQuota: boolean;
  /** Il giro può mandare avvisi (app, push) ai fantallenatori (1.5). */
  sendsNotifications: boolean;
  /** Sta girando adesso, lanciato a mano o dal beat (1.5). */
  running: boolean;
  /** Esito dell'ultimo giro finito; `null` se non ce n'è ancora (1.5). */
  lastRun: SystemJobLastRun | null;
}

/** Ultimo giro finito di un job: `ok` oppure `failed` con il motivo. */
export interface SystemJobLastRun {
  outcome: "ok" | "failed" | string;
  finishedAt: string;
  reason: string | null;
}

/** Esito del lancio a mano di un job («Esegui»): il giro è in coda, non ancora finito. */
export interface SystemJobRunResult {
  key: string;
  title: string;
  status: "started" | "already_running" | "failed" | string;
  message: string;
  /** Per un job spento: «lanciato a mano una volta sola, non riparte da solo». */
  warning: string | null;
  code: string | null;
  taskId: string | null;
}

/** Esito di «Esegui tutti» nei Job: uno per ogni job acceso, più i conteggi. */
export interface SystemJobRunAllResult {
  results: SystemJobRunResult[];
  started: number;
  alreadyRunning: number;
  failed: number;
}

export type TurniBatchOperationStatus = "pending" | "running" | "ok" | "failed" | "skipped";

/** Una operazione di «Esegui tutti» nei Turni, con l'esito. */
export interface TurniBatchOperation {
  key: string;
  label: string;
  status: TurniBatchOperationStatus | string;
  message: string | null;
}

/** Avanzamento di «Esegui tutti» nei Turni: le operazioni girano una dopo l'altra sul server. */
export interface TurniBatch {
  batchId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  operations: TurniBatchOperation[];
  ok: number;
  failed: number;
  skipped: number;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface SystemJobUpdate {
  enabled?: boolean;
  intervalSeconds?: number;
}

export interface AdminResultRecoveryJob {
  jobId: string;
  status: string;
  message: string;
}

/** Esito di "Recupera risultati": stati, statistiche e omologazione dei turni arretrati. */
export interface AdminResultRecoveryResult {
  fixturesCreated: number;
  fixturesUpdated: number;
  detailsFetched: number;
  roundsConsidered: number;
  roundsProcessed: number;
  roundsFinalized: number;
  fixturesScored: number;
  errors: Array<Record<string, string>>;
}

export interface AdminResultRecoveryProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminResultRecoveryResult | null;
}

/** Esito di "Calcola giornata corrente" massivo (tutte le leghe attive). */
export interface AdminRoundCalculationResult {
  roundsConsidered: number;
  roundsProcessed: number;
  roundsFinalized: number;
  fixturesScored: number;
  errors: Array<Record<string, string>>;
}

export interface AdminHistoricalRepairJob {
  jobId: string;
  status: string;
  message: string;
}

/** Esito di "Ricalcola storico" (tutte le leghe attive). */
export interface AdminHistoricalRepairResult {
  leagues: number;
  roundsConsidered: number;
  roundsRepaired: number;
  roundsFailed: number;
  errors: Array<Record<string, string>>;
}

export interface AdminHistoricalRepairProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminHistoricalRepairResult | null;
}

export type AdminTesterRequestStatus = "pending" | "approved" | "rejected";

export interface AdminTesterRequest {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  phone: string | null;
  motivation?: string | null;
  status: AdminTesterRequestStatus;
  createdAt: string;
  decidedAt?: string | null;
  decisionNote?: string | null;
}

export interface AdminTesterRequestList {
  requests: AdminTesterRequest[];
}


// --- Storico stagioni dal fornitore, media stagionale e Valore (1.3) --------------------------

/**
 * «Importa lo storico» (POST /admin/listone/storico, solo operatore). `seasonYear` è la stagione
 * in corso del listone (2026): si importano le due precedenti (2025/26 e 2024/25).
 */
export interface AdminSeasonHistoryImportRequest {
  seasonYear: number;
  /** Default `true`: solo il conto delle chiamate, nessuna chiamata al fornitore. */
  dryRun?: boolean;
  /** Tetto di chiamate di questa esecuzione (default 2000); si riprende rilanciando. */
  maxCalls?: number;
}

export interface AdminSeasonHistorySeasonEstimate {
  seasonYear: number;
  seasonLabel: string;
  leaguePagesDone: number;
  leaguePagesRemaining: number;
  /** `false` finché la prima pagina di qualche campionato non dice quante sono (stima). */
  leaguePagesExact: boolean;
  listoneAthletes: number;
  athletesWithRows: number;
  athletesChecked: number;
  athletesToFill: number;
  /** `false` finché mancano pagine di campionato (stima). */
  athletesToFillExact: boolean;
  rowsStored: number;
  estimatedCalls: number;
}

export interface AdminSeasonHistoryEstimate {
  seasonYear: number;
  seasons: AdminSeasonHistorySeasonEstimate[];
  estimatedCalls: number;
  estimatedMinutes: number;
  requestsPerMinute: number;
}

export interface AdminSeasonHistoryJob {
  jobId: string;
  status: string;
  message: string;
}

export interface AdminSeasonHistoryImportResponse {
  dryRun: boolean;
  estimate: AdminSeasonHistoryEstimate;
  /** Il job avviato (o quello già in corso); `null` in modalità conta. */
  job: AdminSeasonHistoryJob | null;
}

/** POST /admin/listone/valori/ricalcola (solo operatore). */
export interface AdminMarketValuesRefreshRequest {
  seasonYear: number;
  /** Default `true`: ricalcola anche se voti e storico non sono cambiati. */
  force?: boolean;
}

export interface AdminMarketValuesRefreshResult {
  seasonYear: number;
  skipped: boolean;
  currentSeasonRows: number;
  athletesValued: number;
  athletesWithHistory: number;
  athletesWithCurrentAverage: number;
  athletesWithPreviousAverage: number;
  computedAt: string | null;
}

export type AdminSeasonHistoryStopReason = "max_calls" | "quota_reserve" | "too_many_errors";

export interface AdminSeasonHistoryResult {
  seasonYear: number;
  seasons: number[];
  calls: number;
  leaguePages: number;
  athletesChecked: number;
  athletesFound: number;
  rowsCreated: number;
  rowsUpdated: number;
  snapshotsCreated: number;
  errors: number;
  /** `null` se finito; altrimenti fermato prima: rilanciare l'import per continuare. */
  stoppedReason: AdminSeasonHistoryStopReason | null;
  message: string;
  marketValues: AdminMarketValuesRefreshResult | null;
  /** Quello che resta da scaricare dopo questa esecuzione. */
  remaining: AdminSeasonHistoryEstimate | null;
}

/** GET /admin/listone/storico (job attivo o `null`) e GET /admin/listone/storico/{jobId}. */
export interface AdminSeasonHistoryProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed";
  percent: number;
  stage: string;
  message: string;
  errorCode: string | null;
  result: AdminSeasonHistoryResult | null;
}
