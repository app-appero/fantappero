import type {
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
  RosterOwnershipHistory,
  RosterAsOf,
  CreateRosterTurnSnapshotRequest,
  RosterTurnSnapshotSummary,
  RosterTurnSnapshotDetail,
  ExcludeFantasyTurnFixtureRequest,
  FantasyTurnDetail,
  FantasyTurnPreview,
  FantasyTurnSummary,
  GenerateFantasyTurnRequest,
  LineupContext,
  SaveLineupDraftRequest,
  SaveLineupRequest,
  LeagueAdminPanel,
  LeagueCalendar,
  LeagueDetail,
  LeagueInvite,
  LeagueLifecycle,
  LeagueListoneEntry,
  LeagueListoneRefreshJob,
  LeagueListoneRefreshProgress,
  LeagueListoneRefreshResult,
  LeagueMember,
  LeagueRules,
  LeagueSummary,
  TransitionLeagueStateRequest,
  UpdateLeagueRulesRequest,
} from "@fantappero/contracts";
import { apiRequest, apiUpload } from "./client";

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
      setTimeout(resolve, pollIntervalMs);
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

export function previewRosterCsvImport(
  accessToken: string,
  leagueId: string,
  file: { uri: string; name: string; type?: string },
): Promise<RosterImportPreview> {
  return apiUpload<RosterImportPreview>(
    `/leagues/${leagueId}/amministrazione/import-csv/anteprima`,
    { accessToken, file },
  );
}

export function previewRosterCsvImportText(
  accessToken: string,
  leagueId: string,
  csvText: string,
): Promise<RosterImportPreview> {
  return apiRequest<RosterImportPreview>(
    `/leagues/${leagueId}/amministrazione/import-csv/anteprima-testo`,
    {
      method: "POST",
      accessToken,
      body: { csvText },
    },
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
): Promise<{
  leagueId: string;
  created: number;
  opened: number;
  upgraded: number;
  duplicates: number;
  waiting: number;
  horizonDays: number;
}> {
  return apiRequest(`/leagues/${leagueId}/turni/sincronizza`, {
    method: "POST",
    accessToken,
  });
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
