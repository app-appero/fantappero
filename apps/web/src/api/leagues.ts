import type {
  AiLineupRun,
  AcceptedLeagueInvite,
  AcceptLeagueInviteRequest,
  CompetitionSummary,
  CreatedLeagueInvite,
  CreateLeagueInviteRequest,
  CreateLeagueRequest,
  AdminCreditMovementRequest,
  AssignRosterSlotRequest,
  CreditAccount,
  CreditLedgerList,
  EnsureFantasyTeamsResult,
  FantasyTeam,
  FantasyTeamSummary,
  RosterImportConfirmRequest,
  RosterImportConfirmResult,
  RosterImportPreview,
  RosterOccupancyEntry,
  TeamRosterPlayer,
  RosterOwnershipHistory,
  RosterAsOf,
  CreateRosterTurnSnapshotRequest,
  RosterTurnSnapshotSummary,
  RosterTurnSnapshotDetail,
  EnsureFantasyTurnsResponse,
  ExcludeFantasyTurnFixtureRequest,
  FantasyCalendarRefreshJob,
  FantasyCalendarRefreshProgress,
  FantasyCalendarRefreshResult,
  FantasyTurnDetail,
  FantasyTurnPreview,
  FantasyTurnSummary,
  FixtureLiveDetail,
  GenerateFantasyTurnRequest,
  PendingFixtureSummary,
  RoundCalculationResult,
  LineupContext,
  LineupLockCountdown,
  SaveLineupDraftRequest,
  SaveLineupRequest,
  LeagueAdminPanel,
  LeagueCalendar,
  LeagueCalendarPlan,
  H2HCalendar,
  H2HMatchupDetail,
  LeagueDetail,
  LeagueInvite,
  LeagueLifecycle,
  LeagueListoneEntry,
  LeagueListoneRefreshJob,
  LeagueListoneRefreshProgress,
  LeagueListoneRefreshResult,
  LeagueMember,
  LeagueRules,
  LeagueStanding,
  LeagueSummary,
  TransitionLeagueStateRequest,
  UpdateLeagueRulesRequest,
} from "@fantappero/contracts";
import { apiRequest, apiUpload, ApiError } from "./client";
import { getWebEnv } from "../config/env";

export function fetchCompetitions(accessToken: string): Promise<CompetitionSummary[]> {
  return apiRequest<CompetitionSummary[]>("/leagues/competitions", { accessToken });
}

export function fetchMyLeagues(accessToken: string): Promise<LeagueSummary[]> {
  return apiRequest<LeagueSummary[]>("/leagues/mine", { accessToken });
}

export function fetchLeague(accessToken: string, leagueId: string): Promise<LeagueDetail> {
  return apiRequest<LeagueDetail>(`/leagues/${leagueId}`, { accessToken });
}

export function fetchLeagueMembersPublic(
  accessToken: string,
  leagueId: string,
): Promise<LeagueMember[]> {
  return apiRequest<LeagueMember[]>(`/leagues/${leagueId}/partecipanti`, { accessToken });
}

export function fetchLeagueCalendar(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar | null> {
  return apiRequest<LeagueCalendar | null>(`/leagues/${leagueId}/calendario`, { accessToken });
}

export function fetchH2HCalendar(
  accessToken: string,
  leagueId: string,
): Promise<H2HCalendar | null> {
  return apiRequest<H2HCalendar | null>(`/leagues/${leagueId}/calendario/h2h`, { accessToken });
}

export function fetchH2HMatchup(
  accessToken: string,
  leagueId: string,
  slotId: string,
): Promise<H2HMatchupDetail> {
  return apiRequest<H2HMatchupDetail>(`/leagues/${leagueId}/calendario/scontri/${slotId}`, {
    accessToken,
  });
}

export function fetchLeagueStandings(
  accessToken: string,
  leagueId: string,
): Promise<LeagueStanding[]> {
  return apiRequest<LeagueStanding[]>(`/leagues/${leagueId}/classifica`, { accessToken });
}

export function createLeague(
  accessToken: string,
  payload: CreateLeagueRequest,
): Promise<LeagueDetail> {
  return apiRequest<LeagueDetail>("/leagues", {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function deleteLeague(accessToken: string, leagueId: string): Promise<void> {
  return apiRequest<void>(`/leagues/${leagueId}`, {
    method: "DELETE",
    accessToken,
  });
}

export function fetchLeagueAdminPanel(
  accessToken: string,
  leagueId: string,
): Promise<LeagueAdminPanel> {
  return apiRequest<LeagueAdminPanel>(`/leagues/${leagueId}/amministrazione`, { accessToken });
}

export function updateLeagueRules(
  accessToken: string,
  leagueId: string,
  payload: UpdateLeagueRulesRequest,
): Promise<LeagueRules> {
  return apiRequest<LeagueRules>(`/leagues/${leagueId}/amministrazione/regolamento`, {
    method: "PUT",
    accessToken,
    body: payload,
  });
}

export function transitionLeagueState(
  accessToken: string,
  leagueId: string,
  payload: TransitionLeagueStateRequest,
): Promise<LeagueLifecycle> {
  return apiRequest<LeagueLifecycle>(`/leagues/${leagueId}/amministrazione/stato`, {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function fetchLeagueMembers(
  accessToken: string,
  leagueId: string,
): Promise<LeagueMember[]> {
  return apiRequest<LeagueMember[]>(`/leagues/${leagueId}/amministrazione/partecipanti`, {
    accessToken,
  });
}

export function transferLeagueAdmin(
  accessToken: string,
  leagueId: string,
  userId: string,
): Promise<LeagueMember> {
  return apiRequest<LeagueMember>(
    `/leagues/${leagueId}/amministrazione/partecipanti/${userId}/trasferimento-admin`,
    { method: "POST", accessToken },
  );
}

export function removeLeagueMember(
  accessToken: string,
  leagueId: string,
  userId: string,
): Promise<LeagueMember> {
  return apiRequest<LeagueMember>(
    `/leagues/${leagueId}/amministrazione/partecipanti/${userId}`,
    { method: "DELETE", accessToken },
  );
}

export function fetchLeagueInvites(
  accessToken: string,
  leagueId: string,
): Promise<LeagueInvite[]> {
  return apiRequest<LeagueInvite[]>(`/leagues/${leagueId}/amministrazione/inviti`, {
    accessToken,
  });
}

export function createLeagueInvite(
  accessToken: string,
  leagueId: string,
  payload: CreateLeagueInviteRequest,
): Promise<CreatedLeagueInvite> {
  return apiRequest<CreatedLeagueInvite>(`/leagues/${leagueId}/amministrazione/inviti`, {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function revokeLeagueInvite(
  accessToken: string,
  leagueId: string,
  inviteId: string,
): Promise<LeagueInvite> {
  return apiRequest<LeagueInvite>(
    `/leagues/${leagueId}/amministrazione/inviti/${inviteId}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

export function acceptLeagueInvite(
  accessToken: string,
  payload: AcceptLeagueInviteRequest,
): Promise<AcceptedLeagueInvite> {
  return apiRequest<AcceptedLeagueInvite>("/leagues/inviti/accetta", {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function fetchLeagueCalendarAdmin(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar | null> {
  return apiRequest<LeagueCalendar | null>(`/leagues/${leagueId}/amministrazione/calendario`, {
    accessToken,
  });
}

/** Anteprima finestre europee: usate, scartate e motivo (EP13-P03). */
export function fetchLeagueCalendarPlan(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendarPlan> {
  return apiRequest<LeagueCalendarPlan>(
    `/leagues/${leagueId}/amministrazione/calendario/finestre`,
    { accessToken },
  );
}

export function generateLeagueCalendar(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar> {
  return apiRequest<LeagueCalendar>(`/leagues/${leagueId}/amministrazione/calendario/genera`, {
    method: "POST",
    accessToken,
  });
}

export function confirmLeagueCalendar(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar> {
  return apiRequest<LeagueCalendar>(`/leagues/${leagueId}/amministrazione/calendario/conferma`, {
    method: "POST",
    accessToken,
  });
}

export function fetchLeagueListone(
  accessToken: string,
  leagueId: string,
  currentRound = 0,
): Promise<LeagueListoneEntry[]> {
  const params = new URLSearchParams({ currentRound: String(currentRound) });
  return apiRequest<LeagueListoneEntry[]>(`/leagues/${leagueId}/listone?${params}`, {
    accessToken,
  });
}

export function startLeagueListoneRefresh(
  accessToken: string,
  leagueId: string,
): Promise<LeagueListoneRefreshJob> {
  return apiRequest<LeagueListoneRefreshJob>(
    `/leagues/${leagueId}/amministrazione/listone/aggiorna`,
    {
      method: "POST",
      accessToken,
    },
  );
}

export function fetchLeagueListoneRefreshProgress(
  accessToken: string,
  leagueId: string,
  jobId: string,
): Promise<LeagueListoneRefreshProgress> {
  return apiRequest<LeagueListoneRefreshProgress>(
    `/leagues/${leagueId}/amministrazione/listone/aggiorna/${jobId}`,
    { accessToken },
  );
}

export async function refreshLeagueListone(
  accessToken: string,
  leagueId: string,
  options?: {
    onProgress?: (progress: LeagueListoneRefreshProgress) => void;
    pollIntervalMs?: number;
  },
): Promise<LeagueListoneRefreshResult> {
  const started = await startLeagueListoneRefresh(accessToken, leagueId);
  const jobId =
    started.jobId ||
    (started as unknown as { job_id?: string }).job_id ||
    "";
  if (!jobId) {
    throw new Error(
      "Aggiornamento avviato ma senza jobId. Ricarica la pagina e riprova.",
    );
  }
  const pollIntervalMs = options?.pollIntervalMs ?? 800;
  for (;;) {
    const progress = await fetchLeagueListoneRefreshProgress(
      accessToken,
      leagueId,
      jobId,
    );
    options?.onProgress?.(progress);
    if (progress.status === "completed") {
      if (!progress.result) {
        throw new Error("Aggiornamento completato senza risultato.");
      }
      return progress.result;
    }
    if (progress.status === "failed") {
      throw new Error(
        progress.message ||
          "Aggiornamento listone non riuscito (controlla quota API-Football / worker).",
      );
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, pollIntervalMs);
    });
  }
}

export function fetchMyFantasyTeam(accessToken: string, leagueId: string): Promise<FantasyTeam> {
  return apiRequest<FantasyTeam>(`/leagues/${leagueId}/rosa`, { accessToken });
}

export function fetchFantasyTeams(
  accessToken: string,
  leagueId: string,
): Promise<FantasyTeamSummary[]> {
  return apiRequest<FantasyTeamSummary[]>(`/leagues/${leagueId}/squadre`, { accessToken });
}

export function fetchRosterOccupancy(
  accessToken: string,
  leagueId: string,
): Promise<RosterOccupancyEntry[]> {
  return apiRequest<RosterOccupancyEntry[]>(`/leagues/${leagueId}/occupazione-rosa`, {
    accessToken,
  });
}

export function fetchTeamPlayersForTrade(
  accessToken: string,
  leagueId: string,
  teamId: string,
): Promise<TeamRosterPlayer[]> {
  return apiRequest<TeamRosterPlayer[]>(`/leagues/${leagueId}/squadre/${teamId}/giocatori`, {
    accessToken,
  });
}

export function ensureFantasyTeams(
  accessToken: string,
  leagueId: string,
): Promise<EnsureFantasyTeamsResult> {
  return apiRequest<EnsureFantasyTeamsResult>(`/leagues/${leagueId}/amministrazione/squadre`, {
    method: "POST",
    accessToken,
  });
}

export function fetchFantasyTeamForAdmin(
  accessToken: string,
  leagueId: string,
  teamId: string,
): Promise<FantasyTeam> {
  return apiRequest<FantasyTeam>(`/leagues/${leagueId}/amministrazione/squadre/${teamId}`, {
    accessToken,
  });
}

export function assignRandomAiRoster(
  accessToken: string,
  leagueId: string,
  teamId: string,
): Promise<FantasyTeam> {
  return apiRequest<FantasyTeam>(
    `/leagues/${leagueId}/amministrazione/squadre/${teamId}/rosa/random`,
    {
      method: "POST",
      accessToken,
    },
  );
}

export function assignRosterSlot(
  accessToken: string,
  leagueId: string,
  teamId: string,
  slotIndex: number,
  body: AssignRosterSlotRequest,
): Promise<FantasyTeam> {
  return apiRequest<FantasyTeam>(
    `/leagues/${leagueId}/amministrazione/squadre/${teamId}/slot/${slotIndex}`,
    {
      method: "PUT",
      accessToken,
      body,
    },
  );
}

export function releaseRosterSlot(
  accessToken: string,
  leagueId: string,
  teamId: string,
  slotIndex: number,
): Promise<FantasyTeam> {
  return apiRequest<FantasyTeam>(
    `/leagues/${leagueId}/amministrazione/squadre/${teamId}/slot/${slotIndex}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

export function fetchMyCredits(accessToken: string, leagueId: string): Promise<CreditAccount> {
  return apiRequest<CreditAccount>(`/leagues/${leagueId}/crediti`, { accessToken });
}

export function fetchMyCreditMovements(
  accessToken: string,
  leagueId: string,
): Promise<CreditLedgerList> {
  return apiRequest<CreditLedgerList>(`/leagues/${leagueId}/crediti/movimenti`, { accessToken });
}

export function fetchFantasyTeamCreditsForAdmin(
  accessToken: string,
  leagueId: string,
  teamId: string,
): Promise<CreditLedgerList> {
  return apiRequest<CreditLedgerList>(
    `/leagues/${leagueId}/amministrazione/squadre/${teamId}/crediti`,
    { accessToken },
  );
}

export function postAdminCreditMovement(
  accessToken: string,
  leagueId: string,
  body: AdminCreditMovementRequest,
): Promise<CreditLedgerList> {
  return apiRequest<CreditLedgerList>(`/leagues/${leagueId}/amministrazione/crediti/movimenti`, {
    method: "POST",
    accessToken,
    body,
  });
}

export function downloadRosterCsvTemplate(accessToken: string, leagueId: string): Promise<Blob> {
  return apiRequestBlob(`/leagues/${leagueId}/amministrazione/import-csv/modello`, {
    accessToken,
  });
}

export function previewRosterCsvImport(
  accessToken: string,
  leagueId: string,
  file: File,
): Promise<RosterImportPreview> {
  return apiUpload<RosterImportPreview>(
    `/leagues/${leagueId}/amministrazione/import-csv/anteprima`,
    { accessToken, file },
  );
}

export function confirmRosterCsvImport(
  accessToken: string,
  leagueId: string,
  importId: string,
  body: RosterImportConfirmRequest = {},
): Promise<RosterImportConfirmResult> {
  return apiRequest<RosterImportConfirmResult>(
    `/leagues/${leagueId}/amministrazione/import-csv/${importId}/conferma`,
    {
      method: "POST",
      accessToken,
      body,
    },
  );
}

export function fetchMyRosterHistory(
  accessToken: string,
  leagueId: string,
  options: { activeOnly?: boolean } = {},
): Promise<RosterOwnershipHistory> {
  const params = new URLSearchParams();
  if (options.activeOnly) {
    params.set("activeOnly", "true");
  }
  const query = params.toString();
  return apiRequest<RosterOwnershipHistory>(
    `/leagues/${leagueId}/rosa/storico${query ? `?${query}` : ""}`,
    { accessToken },
  );
}

export function fetchTeamRosterHistoryForAdmin(
  accessToken: string,
  leagueId: string,
  teamId: string,
  options: { activeOnly?: boolean } = {},
): Promise<RosterOwnershipHistory> {
  const params = new URLSearchParams();
  if (options.activeOnly) {
    params.set("activeOnly", "true");
  }
  const query = params.toString();
  return apiRequest<RosterOwnershipHistory>(
    `/leagues/${leagueId}/amministrazione/squadre/${teamId}/rosa/storico${query ? `?${query}` : ""}`,
    { accessToken },
  );
}

export function fetchMyRosterAsOf(
  accessToken: string,
  leagueId: string,
  at?: string,
): Promise<RosterAsOf> {
  const params = new URLSearchParams();
  if (at) {
    params.set("at", at);
  }
  const query = params.toString();
  return apiRequest<RosterAsOf>(`/leagues/${leagueId}/rosa/as-of${query ? `?${query}` : ""}`, {
    accessToken,
  });
}

export function fetchRosterTurnSnapshots(
  accessToken: string,
  leagueId: string,
): Promise<RosterTurnSnapshotSummary[]> {
  return apiRequest<RosterTurnSnapshotSummary[]>(`/leagues/${leagueId}/rosa/snapshot-turni`, {
    accessToken,
  });
}

export function fetchRosterTurnSnapshot(
  accessToken: string,
  leagueId: string,
  roundNumber: number,
  options: { teamId?: string } = {},
): Promise<RosterTurnSnapshotDetail> {
  const params = new URLSearchParams();
  if (options.teamId) {
    params.set("teamId", options.teamId);
  }
  const query = params.toString();
  return apiRequest<RosterTurnSnapshotDetail>(
    `/leagues/${leagueId}/rosa/snapshot-turni/${roundNumber}${query ? `?${query}` : ""}`,
    { accessToken },
  );
}

export function createRosterTurnSnapshot(
  accessToken: string,
  leagueId: string,
  body: CreateRosterTurnSnapshotRequest,
): Promise<RosterTurnSnapshotDetail> {
  return apiRequest<RosterTurnSnapshotDetail>(
    `/leagues/${leagueId}/amministrazione/rosa/snapshot-turni`,
    {
      method: "POST",
      accessToken,
      body,
    },
  );
}

export function fetchFantasyTurns(
  accessToken: string,
  leagueId: string,
): Promise<FantasyTurnSummary[]> {
  return apiRequest<FantasyTurnSummary[]>(`/leagues/${leagueId}/turni`, { accessToken });
}

export function fetchFantasyTurn(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<FantasyTurnDetail> {
  return apiRequest<FantasyTurnDetail>(`/leagues/${leagueId}/turni/${roundId}`, { accessToken });
}

/** Dettaglio partita live: formazioni ufficiali e cronologia (EP13-P04). */
export function fetchFixtureLiveDetail(
  accessToken: string,
  leagueId: string,
  roundId: string,
  fixtureId: string,
): Promise<FixtureLiveDetail> {
  return apiRequest<FixtureLiveDetail>(
    `/leagues/${leagueId}/turni/${roundId}/partite/${fixtureId}`,
    { accessToken },
  );
}

/** Preview o ricalcolo delle formazioni automatiche IA (EP13-P05). */
export function runAiLineups(
  accessToken: string,
  leagueId: string,
  roundId: string,
  dryRun: boolean,
): Promise<AiLineupRun> {
  return apiRequest<AiLineupRun>(
    `/leagues/${leagueId}/turni/${roundId}/formazioni-ia?dry_run=${dryRun}`,
    { method: "POST", accessToken },
  );
}

export function previewFantasyTurn(
  accessToken: string,
  leagueId: string,
  body: GenerateFantasyTurnRequest,
): Promise<FantasyTurnPreview> {
  return apiRequest<FantasyTurnPreview>(`/leagues/${leagueId}/turni/anteprima`, {
    method: "POST",
    accessToken,
    body,
  });
}

export function generateFantasyTurn(
  accessToken: string,
  leagueId: string,
  body: GenerateFantasyTurnRequest,
): Promise<FantasyTurnDetail> {
  return apiRequest<FantasyTurnDetail>(`/leagues/${leagueId}/turni`, {
    method: "POST",
    accessToken,
    body,
  });
}

export function ensureFantasyTurns(
  accessToken: string,
  leagueId: string,
): Promise<EnsureFantasyTurnsResponse> {
  return apiRequest(`/leagues/${leagueId}/turni/sincronizza`, {
    method: "POST",
    accessToken,
  });
}

export function fetchPendingFixtures(
  accessToken: string,
  leagueId: string,
): Promise<PendingFixtureSummary[]> {
  return apiRequest<PendingFixtureSummary[]>(`/leagues/${leagueId}/turni/da-aggiornare`, {
    accessToken,
  });
}

export function startCalendarRefresh(
  accessToken: string,
  leagueId: string,
): Promise<FantasyCalendarRefreshJob> {
  return apiRequest<FantasyCalendarRefreshJob>(
    `/leagues/${leagueId}/turni/aggiorna-calendario`,
    { method: "POST", accessToken },
  );
}

export function fetchCalendarRefreshProgress(
  accessToken: string,
  leagueId: string,
  jobId: string,
): Promise<FantasyCalendarRefreshProgress> {
  return apiRequest<FantasyCalendarRefreshProgress>(
    `/leagues/${leagueId}/turni/aggiorna-calendario/${jobId}`,
    { accessToken },
  );
}

/** Comando unico "Aggiorna calendario": sync provider + backfill stagionale + riallineo turni. */
export async function refreshFullCalendar(
  accessToken: string,
  leagueId: string,
  options?: {
    onProgress?: (progress: FantasyCalendarRefreshProgress) => void;
    pollIntervalMs?: number;
  },
): Promise<FantasyCalendarRefreshResult> {
  const started = await startCalendarRefresh(accessToken, leagueId);
  if (!started.jobId) {
    throw new Error("Aggiornamento avviato ma senza jobId. Ricarica la pagina e riprova.");
  }
  const pollIntervalMs = options?.pollIntervalMs ?? 800;
  for (;;) {
    const progress = await fetchCalendarRefreshProgress(accessToken, leagueId, started.jobId);
    options?.onProgress?.(progress);
    if (progress.status === "completed") {
      if (!progress.result) {
        throw new Error("Aggiornamento completato senza risultato.");
      }
      return progress.result;
    }
    if (progress.status === "failed") {
      throw new Error(
        progress.message ||
          "Aggiornamento calendario non riuscito (controlla quota API-Football / worker).",
      );
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, pollIntervalMs);
    });
  }
}

export function openFantasyTurn(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<FantasyTurnDetail> {
  return apiRequest<FantasyTurnDetail>(`/leagues/${leagueId}/turni/${roundId}/apri`, {
    method: "POST",
    accessToken,
  });
}

export function calculateCurrentRound(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<RoundCalculationResult> {
  return apiRequest<RoundCalculationResult>(
    `/leagues/${leagueId}/turni/${roundId}/calcola-giornata`,
    { method: "POST", accessToken },
  );
}

export function excludeFantasyTurnFixture(
  accessToken: string,
  leagueId: string,
  roundId: string,
  body: ExcludeFantasyTurnFixtureRequest,
): Promise<FantasyTurnDetail> {
  return apiRequest<FantasyTurnDetail>(`/leagues/${leagueId}/turni/${roundId}/escludi-fixture`, {
    method: "POST",
    accessToken,
    body,
  });
}

export function recalculateFantasyTurnCutoff(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<FantasyTurnDetail> {
  return apiRequest<FantasyTurnDetail>(
    `/leagues/${leagueId}/turni/${roundId}/ricalcola-cutoff`,
    {
      method: "POST",
      accessToken,
    },
  );
}

export function fetchMyLineup(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<LineupContext> {
  return apiRequest<LineupContext>(`/leagues/${leagueId}/turni/${roundId}/formazione`, {
    accessToken,
  });
}

export function fetchLineupLockCountdown(
  accessToken: string,
  leagueId: string,
): Promise<LineupLockCountdown> {
  return apiRequest<LineupLockCountdown>(`/leagues/${leagueId}/formazione/prossimo-blocco`, {
    accessToken,
  });
}

export function saveMyLineup(
  accessToken: string,
  leagueId: string,
  roundId: string,
  body: SaveLineupRequest,
): Promise<LineupContext> {
  return apiRequest<LineupContext>(`/leagues/${leagueId}/turni/${roundId}/formazione`, {
    method: "PUT",
    accessToken,
    body,
  });
}

export function copyPreviousLineupToDraft(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<LineupContext> {
  return apiRequest<LineupContext>(`/leagues/${leagueId}/turni/${roundId}/formazione/copia`, {
    method: "POST",
    accessToken,
  });
}

export function saveLineupDraft(
  accessToken: string,
  leagueId: string,
  roundId: string,
  body: SaveLineupDraftRequest,
): Promise<LineupContext> {
  return apiRequest<LineupContext>(`/leagues/${leagueId}/turni/${roundId}/formazione/bozza`, {
    method: "PUT",
    accessToken,
    body,
  });
}

async function apiRequestBlob(
  path: string,
  options: { accessToken: string },
): Promise<Blob> {
  const { viteApiBaseUrl } = getWebEnv();
  const response = await fetch(`${viteApiBaseUrl}${path}`, {
    headers: {
      Accept: "text/csv,application/octet-stream,*/*",
      Authorization: `Bearer ${options.accessToken}`,
    },
  });
  if (!response.ok) {
    throw new ApiError("Download modello CSV non riuscito.", response.status, "download_failed");
  }
  return response.blob();
}

