import type {
  CreditAccount,
  CreditLedgerList,
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  RosterImportPreview,
  RosterOccupancyEntry,
  RosterOwnershipHistory,
  RosterTurnSnapshotDetail,
  RosterTurnSnapshotSummary,
} from "@fantappero/contracts";
import { Breadcrumb, Button, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  assignRandomAiRoster,
  assignRosterSlot,
  confirmRosterCsvImport,
  createRosterTurnSnapshot,
  downloadRosterCsvTemplate,
  ensureFantasyTeams,
  fetchFantasyTeamCreditsForAdmin,
  fetchFantasyTeamForAdmin,
  fetchFantasyTeams,
  fetchLeagueListone,
  fetchMyCreditMovements,
  fetchMyCredits,
  fetchMyFantasyTeam,
  fetchMyRosterHistory,
  fetchRosterOccupancy,
  fetchRosterTurnSnapshot,
  fetchRosterTurnSnapshots,
  fetchTeamRosterHistoryForAdmin,
  postAdminCreditMovement,
  previewRosterCsvImport,
  releaseRosterSlot,
} from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";
import { RosterAdminManualCard } from "./roster/RosterAdminManualCard";
import { RosterAdminToolsPanel } from "./roster/RosterAdminToolsPanel";
import {
  DEMO_CREDITS,
  DEMO_CREDITS_B,
  DEMO_HISTORY,
  DEMO_LEDGER,
  DEMO_LEDGER_B,
  DEMO_LISTONE,
  DEMO_OCCUPANCY,
  DEMO_SNAPSHOT_DETAIL,
  DEMO_SNAPSHOTS,
  DEMO_TEAM,
  DEMO_TEAM_B,
  DEMO_TEAMS,
} from "./roster/rosterDemoData";
import { RosterCreditsPanel } from "./roster/RosterCreditsPanel";
import { RosterCsvImportCard } from "./roster/RosterCsvImportCard";
import { RosterEmptyState } from "./roster/RosterEmptyState";
import { RosterFilledSummary } from "./roster/RosterFilledSummary";
import {
  LEDGER_PAGE_SIZE,
  buildOwnership,
  initialDemoCredits,
  initialDemoLedger,
  initialDemoTeam,
  sortLedgerNewestFirst,
  toSummary,
  type RoleTab,
  type RosterPageSection,
} from "./roster/rosterHelpers";
import { RosterHistorySection } from "./roster/RosterHistorySection";
import { RosterSectionTabs } from "./roster/RosterSectionTabs";

/** Rosa fantasy, ledger crediti e inserimento manuale admin (EP05-01/02/03).
 * EP05-04 CSV import UI is implemented but temporarily hidden (`SHOW_ROSTER_CSV_IMPORT`).
 */
const SHOW_ROSTER_CSV_IMPORT = false;

export function RosterPage() {
  const { isDemoMode, activeLeagueId, activeLeague, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const isAdmin = can(["league:admin"]);
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);

  const [team, setTeam] = useState<FantasyTeam | null>(() =>
    initialDemoTeam(isDemoMode, demoState),
  );
  const [credits, setCredits] = useState<CreditAccount | null>(() =>
    initialDemoCredits(isDemoMode, demoState),
  );
  const [ledger, setLedger] = useState<CreditLedgerList | null>(() =>
    initialDemoLedger(isDemoMode, demoState),
  );
  const [loading, setLoading] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error"
      ? "Impossibile caricare i giocatori della rosa."
      : null,
  );
  const [ensureMessage, setEnsureMessage] = useState<string | null>(null);
  const [ensureError, setEnsureError] = useState<string | null>(null);
  const [ensuring, setEnsuring] = useState(false);
  const [randomAiMessage, setRandomAiMessage] = useState<string | null>(null);
  const [randomAiError, setRandomAiError] = useState<string | null>(null);
  const [randomAiBusy, setRandomAiBusy] = useState(false);
  const [adjustAmount, setAdjustAmount] = useState("-10");
  const [adjustNote, setAdjustNote] = useState("");
  const [adjustMessage, setAdjustMessage] = useState<string | null>(null);
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [adjusting, setAdjusting] = useState(false);

  const [leagueTeams, setLeagueTeams] = useState<FantasyTeamSummary[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_TEAMS
      : [],
  );
  const [adminTeamId, setAdminTeamId] = useState(() =>
    isDemoMode ? DEMO_TEAM.id : "",
  );
  const [adminTeam, setAdminTeam] = useState<FantasyTeam | null>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_TEAM
      : null,
  );
  const [teamDetails, setTeamDetails] = useState<FantasyTeam[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? [DEMO_TEAM, DEMO_TEAM_B]
      : [],
  );
  const [listone, setListone] = useState<LeagueListoneEntry[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_LISTONE
      : [],
  );
  const [roleTab, setRoleTab] = useState<RoleTab>("all");
  const [listoneQuery, setListoneQuery] = useState("");
  const [purchaseCredits, setPurchaseCredits] = useState("1");
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_OCCUPANCY
      : [],
  );
  const [adminBusy, setAdminBusy] = useState(false);
  const [adminMessage, setAdminMessage] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminLoadError, setAdminLoadError] = useState<string | null>(null);
  const [ledgerPage, setLedgerPage] = useState(0);
  const [csvPreview, setCsvPreview] = useState<RosterImportPreview | null>(null);
  const [csvResolutions, setCsvResolutions] = useState<Record<number, string>>({});
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvMessage, setCsvMessage] = useState<string | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [pageSection, setPageSection] = useState<RosterPageSection>(() => {
    const params = new URLSearchParams(search);
    return params.get("sezione") === "storico" ? "storico" : "rosa";
  });
  const [history, setHistory] = useState<RosterOwnershipHistory | null>(() => {
    if (!isDemoMode || demoState === "forbidden" || demoState === "error" || demoState === "loading") {
      return null;
    }
    if (demoState === "empty") {
      return { fantasyTeamId: "demo-team", intervals: [] };
    }
    return DEMO_HISTORY;
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<RosterTurnSnapshotSummary[]>(() => {
    if (!isDemoMode || demoState === "forbidden" || demoState === "error" || demoState === "loading" || demoState === "empty") {
      return [];
    }
    return DEMO_SNAPSHOTS;
  });
  const [snapshotDetail, setSnapshotDetail] = useState<RosterTurnSnapshotDetail | null>(() => {
    if (!isDemoMode || demoState === "forbidden" || demoState === "error" || demoState === "loading" || demoState === "empty") {
      return null;
    }
    return DEMO_SNAPSHOT_DETAIL;
  });
  const [snapshotRound, setSnapshotRound] = useState("1");
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [snapshotMessage, setSnapshotMessage] = useState<string | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const csvFileInputRef = useRef<HTMLInputElement | null>(null);
  const adminTeamIdRef = useRef(adminTeamId);
  adminTeamIdRef.current = adminTeamId;

  const ownership = useMemo(() => buildOwnership(occupancy), [occupancy]);

  const viewedTeam = isAdmin ? (adminTeam ?? team) : team;
  const targetTeam = viewedTeam;
  const targetTeamId = isAdmin ? adminTeamId : team?.id ?? "";

  const emptySlots = useMemo(
    () => targetTeam?.slots.filter((slot) => !slot.athleteId) ?? [],
    [targetTeam],
  );

  const canReleaseAthlete = useCallback(
    (ownerTeamId: string) => isAdmin || ownerTeamId === team?.id,
    [isAdmin, team?.id],
  );

  const applyTeamUpdate = useCallback((updated: FantasyTeam) => {
    setTeamDetails((current) => {
      const next = current.some((row) => row.id === updated.id)
        ? current.map((row) => (row.id === updated.id ? updated : row))
        : [...current, updated];
      return next;
    });
    setLeagueTeams((current) =>
      current.map((row) => (row.id === updated.id ? toSummary(updated) : row)),
    );
    setAdminTeam((current) => (current?.id === updated.id ? updated : current));
    setTeam((current) => (current?.id === updated.id ? updated : current));
    setOccupancy((current) => {
      const withoutTeam = current.filter((entry) => entry.fantasyTeamId !== updated.id);
      const fromTeam = updated.slots
        .filter((slot) => slot.athleteId)
        .map((slot) => ({
          athleteId: slot.athleteId!,
          fantasyTeamId: updated.id,
          teamName: updated.name,
          slotIndex: slot.slotIndex,
          purchaseCredits: slot.purchaseCredits,
        }));
      return [...withoutTeam, ...fromTeam];
    });
  }, []);

  const refreshMyCredits = useCallback(async (accessToken: string, leagueId: string) => {
    const [nextCredits, nextLedger] = await Promise.all([
      fetchMyCredits(accessToken, leagueId),
      fetchMyCreditMovements(accessToken, leagueId),
    ]);
    setCredits(nextCredits);
    setLedger(nextLedger);
    setLedgerPage(0);
  }, []);

  const applyLedgerResult = useCallback((result: CreditLedgerList) => {
    setCredits({
      fantasyTeamId: result.fantasyTeamId,
      balance: result.balance,
      version: result.version,
      reconstructedBalance: result.entries.reduce((sum, entry) => sum + entry.amount, 0),
    });
    setLedger(result);
    setLedgerPage(0);
  }, []);

  const refreshViewedCredits = useCallback(
    async (accessToken: string, leagueId: string) => {
      const viewedId = adminTeamIdRef.current;
      if (isAdmin && viewedId) {
        const result = await fetchFantasyTeamCreditsForAdmin(accessToken, leagueId, viewedId);
        applyLedgerResult(result);
        return;
      }
      await refreshMyCredits(accessToken, leagueId);
    },
    [applyLedgerResult, isAdmin, refreshMyCredits],
  );

  const applyDemoCreditDelta = useCallback((fantasyTeamId: string, delta: number) => {
    setCredits((current) => {
      if (!current || current.fantasyTeamId !== fantasyTeamId) {
        return current;
      }
      return { ...current, balance: current.balance + delta };
    });
  }, []);

  const loadEditContext = useCallback(
    async (preferredTeamId?: string) => {
      setAdminLoadError(null);
      if (!canEdit) {
        setLeagueTeams([]);
        setAdminTeam(null);
        setTeamDetails([]);
        setListone([]);
        setOccupancy([]);
        return;
      }

      if (isDemoMode) {
        if (demoState === "forbidden" || demoState === "error" || demoState === "loading") {
          setLeagueTeams([]);
          setAdminTeam(null);
          setTeamDetails([]);
          setListone([]);
          setOccupancy([]);
          return;
        }
        setListone(DEMO_LISTONE);
        setOccupancy(DEMO_OCCUPANCY);
        if (isAdmin) {
          setLeagueTeams(DEMO_TEAMS);
          setTeamDetails([DEMO_TEAM, DEMO_TEAM_B]);
          const nextId = preferredTeamId || adminTeamIdRef.current || DEMO_TEAM.id;
          setAdminTeamId(nextId);
          setAdminTeam(nextId === DEMO_TEAM.id ? DEMO_TEAM : DEMO_TEAM_B);
        }
        return;
      }

      if (!activeLeagueId) {
        setLeagueTeams([]);
        setAdminTeam(null);
        setTeamDetails([]);
        setListone([]);
        setOccupancy([]);
        return;
      }
      const stored = loadStoredSession();
      if (!stored?.accessToken) {
        setAdminLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      try {
        const [entries, occupancyData] = await Promise.all([
          fetchLeagueListone(stored.accessToken, activeLeagueId),
          fetchRosterOccupancy(stored.accessToken, activeLeagueId),
        ]);
        setListone(entries);
        setOccupancy(occupancyData);

        if (isAdmin) {
          const teams = await fetchFantasyTeams(stored.accessToken, activeLeagueId);
          setLeagueTeams(teams);
          const details = await Promise.all(
            teams.map((row) =>
              fetchFantasyTeamForAdmin(stored.accessToken, activeLeagueId, row.id),
            ),
          );
          setTeamDetails(details);
          const nextId = preferredTeamId || adminTeamIdRef.current || teams[0]?.id || "";
          setAdminTeamId(nextId);
          setAdminTeam(details.find((row) => row.id === nextId) ?? null);
        }
      } catch (error) {
        setAdminLoadError(
          getApiErrorMessage(error, "Impossibile caricare il listone e l'occupazione rosa."),
        );
        setAdminTeam(null);
        setTeamDetails([]);
      }
    },
    [activeLeagueId, canEdit, demoState, isAdmin, isDemoMode],
  );

  const loadRoster = useCallback(async () => {
    setEnsureMessage(null);
    setEnsureError(null);
    setAdjustMessage(null);
    setAdjustError(null);
    setAdminMessage(null);
    setAdminError(null);

    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError("Impossibile caricare i giocatori della rosa.");
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setTeam({
          ...DEMO_TEAM,
          filledSlots: 0,
          slots: DEMO_TEAM.slots.map((slot) => ({
            ...slot,
            athleteId: null,
            athleteName: null,
          })),
        });
        setCredits(DEMO_CREDITS);
        setLedger(DEMO_LEDGER);
        setLoadError(null);
        return;
      }
      if (demoState === "forbidden") {
        setLoading(false);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError(null);
        return;
      }
      setTeam(DEMO_TEAM);
      setCredits(DEMO_CREDITS);
      setLedger(DEMO_LEDGER);
      setLoading(false);
      setLoadError(null);
      return;
    }

    if (!canView) {
      setLoading(false);
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError(null);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const [nextTeam, nextCredits, nextLedger] = await Promise.all([
        fetchMyFantasyTeam(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId),
        fetchMyCreditMovements(stored.accessToken, activeLeagueId),
      ]);
      setTeam(nextTeam);
      setCredits(nextCredits);
      setLedger(nextLedger);
    } catch (error) {
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i giocatori della rosa."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, canView, demoState, isDemoMode]);

  useEffect(() => {
    void loadRoster();
  }, [loadRoster]);

  useEffect(() => {
    void loadEditContext();
  }, [loadEditContext]);

  useEffect(() => {
    if (!canEdit || isAdmin || !team) {
      return;
    }
    setAdminTeamId(team.id);
    setAdminTeam(team);
  }, [canEdit, isAdmin, team]);

  const loadHistory = useCallback(async () => {
    setHistoryError(null);
    setSnapshotError(null);
    if (isDemoMode) {
      if (demoState === "forbidden" || demoState === "error" || demoState === "loading") {
        setHistory(null);
        setSnapshots([]);
        setSnapshotDetail(null);
        return;
      }
      if (demoState === "empty") {
        setHistory({ fantasyTeamId: "demo-team", intervals: [] });
        setSnapshots([]);
        setSnapshotDetail(null);
        return;
      }
      setHistory(DEMO_HISTORY);
      setSnapshots(DEMO_SNAPSHOTS);
      setSnapshotDetail(DEMO_SNAPSHOT_DETAIL);
      return;
    }
    if (!canView || !activeLeagueId) {
      setHistory(null);
      setSnapshots([]);
      setSnapshotDetail(null);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setHistoryError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setHistoryLoading(true);
    try {
      const historyPromise =
        isAdmin && adminTeamId
          ? fetchTeamRosterHistoryForAdmin(stored.accessToken, activeLeagueId, adminTeamId)
          : fetchMyRosterHistory(stored.accessToken, activeLeagueId);
      const [nextHistory, nextSnapshots] = await Promise.all([
        historyPromise,
        fetchRosterTurnSnapshots(stored.accessToken, activeLeagueId),
      ]);
      setHistory(nextHistory);
      setSnapshots(nextSnapshots);
      const preferred = nextSnapshots.at(-1);
      if (preferred) {
        setSnapshotRound(String(preferred.roundNumber));
        const detail = await fetchRosterTurnSnapshot(
          stored.accessToken,
          activeLeagueId,
          preferred.roundNumber,
          isAdmin && adminTeamId ? { teamId: adminTeamId } : undefined,
        );
        setSnapshotDetail(detail);
      } else {
        setSnapshotDetail(null);
      }
    } catch (error) {
      setHistory(null);
      setSnapshots([]);
      setSnapshotDetail(null);
      setHistoryError(getApiErrorMessage(error, "Impossibile caricare lo storico rosa."));
    } finally {
      setHistoryLoading(false);
    }
  }, [activeLeagueId, adminTeamId, canView, demoState, isAdmin, isDemoMode]);

  useEffect(() => {
    if (pageSection !== "storico") {
      return;
    }
    void loadHistory();
  }, [loadHistory, pageSection]);

  const onSelectSnapshotRound = async (roundValue: string) => {
    setSnapshotRound(roundValue);
    setSnapshotError(null);
    setSnapshotMessage(null);
    if (isDemoMode) {
      setSnapshotDetail(
        Number(roundValue) === DEMO_SNAPSHOT_DETAIL.roundNumber ? DEMO_SNAPSHOT_DETAIL : null,
      );
      return;
    }
    if (!activeLeagueId || !roundValue) {
      setSnapshotDetail(null);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setSnapshotError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSnapshotBusy(true);
    try {
      const detail = await fetchRosterTurnSnapshot(
        stored.accessToken,
        activeLeagueId,
        Number(roundValue),
        isAdmin && adminTeamId ? { teamId: adminTeamId } : undefined,
      );
      setSnapshotDetail(detail);
    } catch (error) {
      setSnapshotDetail(null);
      setSnapshotError(getApiErrorMessage(error, "Snapshot turno non disponibile."));
    } finally {
      setSnapshotBusy(false);
    }
  };

  const onCreateSnapshot = async () => {
    setSnapshotError(null);
    setSnapshotMessage(null);
    const roundNumber = Number(snapshotRound);
    if (!Number.isInteger(roundNumber) || roundNumber < 1) {
      setSnapshotError("Indica un numero di turno valido (≥ 1).");
      return;
    }
    if (isDemoMode) {
      setSnapshotBusy(true);
      window.setTimeout(() => {
        setSnapshotMessage(`Snapshot turno ${roundNumber} creato (demo).`);
        setSnapshotDetail({
          ...DEMO_SNAPSHOT_DETAIL,
          roundNumber,
          created: true,
        });
        setSnapshots([
          {
            id: `snap-${roundNumber}`,
            leagueId: "demo-league",
            roundNumber,
            capturedAt: new Date().toISOString(),
            entryCount: DEMO_SNAPSHOT_DETAIL.entryCount,
            actorId: "demo-admin",
          },
        ]);
        setSnapshotBusy(false);
      }, 200);
      return;
    }
    if (!activeLeagueId) {
      setSnapshotError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setSnapshotError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSnapshotBusy(true);
    try {
      const detail = await createRosterTurnSnapshot(stored.accessToken, activeLeagueId, {
        roundNumber,
      });
      setSnapshotDetail(detail);
      setSnapshotMessage(
        detail.created
          ? `Snapshot turno ${roundNumber} creato.`
          : `Snapshot turno ${roundNumber} già presente (idempotente).`,
      );
      const nextSnapshots = await fetchRosterTurnSnapshots(stored.accessToken, activeLeagueId);
      setSnapshots(nextSnapshots);
    } catch (error) {
      setSnapshotError(getApiErrorMessage(error, "Impossibile creare lo snapshot."));
    } finally {
      setSnapshotBusy(false);
    }
  };

  const onEnsureTeams = async () => {
    setEnsureMessage(null);
    setEnsureError(null);
    if (isDemoMode) {
      setEnsuring(true);
      window.setTimeout(() => {
        setEnsureMessage("Squadre verificate (demo).");
        setEnsuring(false);
      }, 300);
      return;
    }
    if (!activeLeagueId) {
      setEnsureError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setEnsureError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setEnsuring(true);
    try {
      const result = await ensureFantasyTeams(stored.accessToken, activeLeagueId);
      setEnsureMessage(
        `Squadre aggiornate: ${result.created} create, ${result.existing} già presenti.`,
      );
      setLeagueTeams(result.teams);
      await loadRoster();
      await loadEditContext(result.teams[0]?.id);
    } catch (error) {
      setEnsureError(getApiErrorMessage(error, "Impossibile creare le squadre."));
    } finally {
      setEnsuring(false);
    }
  };

  const onAssignRandomAiRoster = async () => {
    setRandomAiMessage(null);
    setRandomAiError(null);
    const targetId = adminTeamId || viewedTeam?.id;
    const targetTeam =
      (targetId ? teamDetails.find((row) => row.id === targetId) : null) ??
      adminTeam ??
      viewedTeam;
    if (!targetTeam || targetTeam.userType !== "ai") {
      setRandomAiError("Seleziona una squadra di un fantallenatore IA.");
      return;
    }
    if (targetTeam.filledSlots >= targetTeam.rosterSize) {
      setRandomAiMessage("La rosa del fantallenatore IA è già completa.");
      return;
    }
    if (isDemoMode) {
      setRandomAiBusy(true);
      window.setTimeout(() => {
        const filled = {
          ...DEMO_TEAM_B,
          filledSlots: DEMO_TEAM_B.rosterSize,
          compositionStatus: "incomplete" as const,
          composition: {
            ...DEMO_TEAM_B.composition!,
            status: "incomplete" as const,
            filledSlots: DEMO_TEAM_B.rosterSize,
            counts: { P: 3, D: 11, C: 11, A: 10 },
          },
          slots: DEMO_TEAM_B.slots.map((slot, index) => ({
            ...slot,
            athleteId: `ai-demo-${index}`,
            athleteName: `Calciatore IA ${index + 1}`,
            role: (["P", "P", "P", "D", "D", "D", "D", "D", "D", "D", "D", "D", "D", "D", "C", "C", "C", "C", "C", "C", "C", "C", "C", "C", "C", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A"] as const)[index] ?? "A",
            purchaseCredits: 0,
          })),
        };
        setAdminTeam(filled);
        setTeamDetails((current) =>
          current.map((row) => (row.id === filled.id ? filled : row)),
        );
        setLeagueTeams((current) =>
          current.map((row) =>
            row.id === filled.id
              ? { ...row, filledSlots: filled.filledSlots, compositionStatus: filled.compositionStatus }
              : row,
          ),
        );
        setRandomAiMessage("Rosa random assegnata al fantallenatore IA (demo).");
        setRandomAiBusy(false);
      }, 300);
      return;
    }
    if (!activeLeagueId) {
      setRandomAiError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setRandomAiError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setRandomAiBusy(true);
    try {
      const updated = await assignRandomAiRoster(
        stored.accessToken,
        activeLeagueId,
        targetTeam.id,
      );
      setAdminTeam(updated);
      setTeamDetails((current) =>
        current.map((row) => (row.id === updated.id ? updated : row)),
      );
      setLeagueTeams((current) =>
        current.map((row) =>
          row.id === updated.id
            ? {
                ...row,
                filledSlots: updated.filledSlots,
                compositionStatus: updated.compositionStatus,
                userType: updated.userType,
              }
            : row,
        ),
      );
      setRandomAiMessage(
        `Rosa random assegnata: ${updated.filledSlots}/${updated.rosterSize} giocatori.`,
      );
      await loadEditContext(updated.id);
    } catch (error) {
      setRandomAiError(
        getApiErrorMessage(error, "Impossibile assegnare la rosa random."),
      );
    } finally {
      setRandomAiBusy(false);
    }
  };

  const onDownloadCsvTemplate = async () => {
    setCsvError(null);
    setCsvMessage(null);
    if (isDemoMode) {
      const blob = new Blob(
        ["squadra,provider_id,nome,crediti\nSquadra Esempio,12345,Nome Calciatore,10\n"],
        { type: "text/csv;charset=utf-8" },
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "fantappero-import-rosa.csv";
      anchor.click();
      URL.revokeObjectURL(url);
      setCsvMessage("Modello CSV scaricato (demo).");
      return;
    }
    if (!activeLeagueId) {
      setCsvError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCsvError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    try {
      const blob = await downloadRosterCsvTemplate(stored.accessToken, activeLeagueId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "fantappero-import-rosa.csv";
      anchor.click();
      URL.revokeObjectURL(url);
      setCsvMessage("Modello CSV scaricato.");
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile scaricare il modello CSV."));
    }
  };

  const onCsvFileSelected = async (file: File | null) => {
    setCsvError(null);
    setCsvMessage(null);
    setCsvPreview(null);
    setCsvResolutions({});
    if (!file) {
      return;
    }
    if (isDemoMode) {
      setCsvBusy(true);
      window.setTimeout(() => {
        setCsvPreview({
          importId: "demo-import",
          status: "draft",
          fileSha256: "demo",
          originalFilename: file.name,
          canConfirm: true,
          rowCount: 1,
          errorCount: 0,
          warningCount: 0,
          confirmedAt: null,
          rows: [
            {
              rowNumber: 2,
              squadra: DEMO_TEAM.name,
              providerId: 1,
              nome: "L. Martinez",
              crediti: 10,
              status: "ok",
              fantasyTeamId: DEMO_TEAM.id,
              fantasyTeamName: DEMO_TEAM.name,
              athleteId: "a1",
              athleteName: "L. Martinez",
              slotIndex: 2,
              issues: [],
              candidates: [],
            },
          ],
        });
        setCsvBusy(false);
      }, 200);
      return;
    }
    if (!activeLeagueId) {
      setCsvError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCsvError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setCsvBusy(true);
    try {
      const preview = await previewRosterCsvImport(
        stored.accessToken,
        activeLeagueId,
        file,
      );
      setCsvPreview(preview);
      if (preview.errorCount > 0) {
        setCsvError("Anteprima con errori: correggi il file o risolvi le ambiguità.");
      }
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile elaborare il CSV."));
    } finally {
      setCsvBusy(false);
    }
  };

  const onConfirmCsvImport = async () => {
    setCsvError(null);
    setCsvMessage(null);
    if (!csvPreview) {
      setCsvError("Carica prima un file CSV.");
      return;
    }
    if (isDemoMode) {
      setCsvBusy(true);
      window.setTimeout(() => {
        setCsvMessage("Import CSV confermato (demo).");
        setCsvPreview(null);
        setCsvBusy(false);
      }, 200);
      return;
    }
    if (!activeLeagueId) {
      setCsvError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCsvError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const resolutions = Object.entries(csvResolutions).map(([rowNumber, athleteId]) => ({
      rowNumber: Number(rowNumber),
      athleteId,
    }));
    setCsvBusy(true);
    try {
      const result = await confirmRosterCsvImport(
        stored.accessToken,
        activeLeagueId,
        csvPreview.importId,
        { resolutions },
      );
      setCsvMessage(
        `Import completato: ${result.assignedCount} assegnazioni su ${result.teamsTouched} squadre.`,
      );
      setCsvPreview(null);
      setCsvResolutions({});
      await loadRoster();
      await loadEditContext(adminTeamId || undefined);
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile confermare l'import CSV."));
    } finally {
      setCsvBusy(false);
    }
  };

  const csvCanConfirm =
    !!csvPreview &&
    (csvPreview.canConfirm ||
      csvPreview.rows.every(
        (row) =>
          row.status === "ok" ||
          (row.status === "ambiguous" && Boolean(csvResolutions[row.rowNumber])),
      ));

  const onSelectAdminTeam = (teamId: string) => {
    setAdminTeamId(teamId);
    setAdminMessage(null);
    setAdminError(null);
    setAdjustMessage(null);
    setAdjustError(null);
    const detail = teamDetails.find((row) => row.id === teamId) ?? null;
    setAdminTeam(detail);

    if (isDemoMode) {
      if (teamId === DEMO_TEAM_B.id) {
        setCredits(DEMO_CREDITS_B);
        setLedger(DEMO_LEDGER_B);
      } else {
        setCredits(DEMO_CREDITS);
        setLedger(DEMO_LEDGER);
      }
      return;
    }

    if (!activeLeagueId) {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    void (async () => {
      try {
        const result = await fetchFantasyTeamCreditsForAdmin(
          stored.accessToken,
          activeLeagueId,
          teamId,
        );
        applyLedgerResult(result);
        if (!detail) {
          const fetched = await fetchFantasyTeamForAdmin(
            stored.accessToken,
            activeLeagueId,
            teamId,
          );
          setAdminTeam(fetched);
          setTeamDetails((current) =>
            current.some((row) => row.id === fetched.id)
              ? current.map((row) => (row.id === fetched.id ? fetched : row))
              : [...current, fetched],
          );
        }
      } catch {
        // Keep previous credits if the switch fails; assign/release will surface errors.
      }
    })();
  };

  const onAssignAthlete = async (athleteId: string) => {
    setAdminMessage(null);
    setAdminError(null);
    if (!targetTeamId || !targetTeam) {
      setAdminError("Seleziona una squadra.");
      return;
    }
    const emptySlot = emptySlots[0];
    if (!emptySlot) {
      setAdminError("Nessuno slot libero sulla squadra selezionata.");
      return;
    }
    if (ownership.has(athleteId)) {
      setAdminError("Il calciatore appartiene già a una squadra di questa lega.");
      return;
    }
    const credits = Number.parseInt(purchaseCredits, 10);
    if (!Number.isFinite(credits) || credits < 1) {
      setAdminError("Inserisci crediti acquisto validi (minimo 1).");
      return;
    }

    if (isDemoMode) {
      setAdminBusy(true);
      window.setTimeout(() => {
        const athlete = listone.find((entry) => entry.athleteId === athleteId);
        const updated: FantasyTeam = {
          ...targetTeam,
          slots: targetTeam.slots.map((slot) =>
            slot.slotIndex === emptySlot.slotIndex
              ? {
                  ...slot,
                  athleteId,
                  athleteName: athlete?.canonicalName ?? "Calciatore",
                  clubName: athlete?.clubName ?? null,
                  role: athlete?.effectiveRole ?? null,
                  purchaseCredits: credits,
                }
              : slot,
          ),
        };
        updated.filledSlots = updated.slots.filter((slot) => slot.athleteId).length;
        applyTeamUpdate(updated);
        applyDemoCreditDelta(updated.id, -credits);
        setAdminMessage(`${athlete?.canonicalName ?? "Calciatore"} assegnato (demo).`);
        setAdminBusy(false);
      }, 200);
      return;
    }

    if (!activeLeagueId) {
      setAdminError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setAdminError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setAdminBusy(true);
    try {
      const updated = await assignRosterSlot(
        stored.accessToken,
        activeLeagueId,
        targetTeamId,
        emptySlot.slotIndex,
        { athleteId, purchaseCredits: credits },
      );
      applyTeamUpdate(updated);
      await refreshViewedCredits(stored.accessToken, activeLeagueId);
      setAdminMessage(
        `Assegnato a slot ${emptySlot.slotIndex + 1}: ${
          updated.slots.find((slot) => slot.slotIndex === emptySlot.slotIndex)?.athleteName ??
          "calciatore"
        }.`,
      );
    } catch (error) {
      setAdminError(getApiErrorMessage(error, "Impossibile assegnare il calciatore."));
    } finally {
      setAdminBusy(false);
    }
  };

  const onReleaseAthlete = async (athleteId: string) => {
    setAdminMessage(null);
    setAdminError(null);
    const owner = ownership.get(athleteId);
    if (!owner) {
      setAdminError("Il calciatore non risulta in rosa.");
      return;
    }
    if (!canReleaseAthlete(owner.teamId)) {
      setAdminError("Non puoi rimuovere calciatori di altre squadre.");
      return;
    }

    if (isDemoMode) {
      setAdminBusy(true);
      window.setTimeout(() => {
        const current = isAdmin
          ? teamDetails.find((row) => row.id === owner.teamId)
          : team?.id === owner.teamId
            ? team
            : null;
        if (!current) {
          setAdminBusy(false);
          return;
        }
        const releasedSlot = current.slots.find((slot) => slot.slotIndex === owner.slotIndex);
        const refund = releasedSlot?.purchaseCredits ?? 0;
        const updated: FantasyTeam = {
          ...current,
          slots: current.slots.map((slot) =>
            slot.slotIndex === owner.slotIndex
              ? {
                  ...slot,
                  athleteId: null,
                  athleteName: null,
                  clubName: null,
                  role: null,
                  purchaseCredits: null,
                }
              : slot,
          ),
        };
        updated.filledSlots = updated.slots.filter((slot) => slot.athleteId).length;
        applyTeamUpdate(updated);
        applyDemoCreditDelta(owner.teamId, refund);
        setAdminMessage(`Rimosso da ${owner.teamName} (demo).`);
        setAdminBusy(false);
      }, 200);
      return;
    }

    if (!activeLeagueId) {
      setAdminError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setAdminError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setAdminBusy(true);
    try {
      const updated = await releaseRosterSlot(
        stored.accessToken,
        activeLeagueId,
        owner.teamId,
        owner.slotIndex,
      );
      applyTeamUpdate(updated);
      await refreshViewedCredits(stored.accessToken, activeLeagueId);
      setAdminMessage(`Rimosso da ${owner.teamName}.`);
    } catch (error) {
      setAdminError(getApiErrorMessage(error, "Impossibile liberare lo slot."));
    } finally {
      setAdminBusy(false);
    }
  };

  const onAdminAdjust = async () => {
    setAdjustMessage(null);
    setAdjustError(null);
    const targetTeamId = adminTeamId || team?.id;
    if (isDemoMode) {
      setAdjusting(true);
      window.setTimeout(() => {
        setAdjustMessage("Movimento registrato (demo).");
        setAdjusting(false);
      }, 300);
      return;
    }
    if (!activeLeagueId || !targetTeamId) {
      setAdjustError("Seleziona una lega e una squadra.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setAdjustError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const amount = Number.parseInt(adjustAmount, 10);
    if (!Number.isFinite(amount) || amount === 0) {
      setAdjustError("Inserisci un importo diverso da zero.");
      return;
    }
    setAdjusting(true);
    try {
      const result = await postAdminCreditMovement(stored.accessToken, activeLeagueId, {
        fantasyTeamId: targetTeamId,
        amount,
        transactionId: `admin:${targetTeamId}:${Date.now()}`,
        note: adjustNote.trim() || null,
      });
      applyLedgerResult(result);
      setAdjustMessage(`Movimento registrato. Nuovo saldo: ${result.balance} crediti.`);
    } catch (error) {
      setAdjustError(getApiErrorMessage(error, "Impossibile registrare il movimento."));
    } finally {
      setAdjusting(false);
    }
  };

  const filledSlots = useMemo(
    () => viewedTeam?.slots.filter((slot) => slot.athleteId) ?? [],
    [viewedTeam?.slots],
  );
  const filledByRole = useMemo(() => {
    const groups: Record<FantasyRole | "unknown", typeof filledSlots> = {
      P: [],
      D: [],
      C: [],
      A: [],
      unknown: [],
    };
    for (const slot of filledSlots) {
      if (slot.role === "P" || slot.role === "D" || slot.role === "C" || slot.role === "A") {
        groups[slot.role].push(slot);
      } else {
        groups.unknown.push(slot);
      }
    }
    return groups;
  }, [filledSlots]);
  const isEmpty = Boolean(viewedTeam && viewedTeam.filledSlots === 0);
  const showForbidden = (isDemoMode && demoState === "forbidden") || (!isDemoMode && !canView);
  const hasLedger = Boolean(ledger && ledger.entries.length > 0);
  const ledgerEntriesNewestFirst = useMemo(
    () => (ledger ? sortLedgerNewestFirst(ledger.entries) : []),
    [ledger],
  );
  const ledgerPageCount = Math.max(1, Math.ceil(ledgerEntriesNewestFirst.length / LEDGER_PAGE_SIZE));
  const safeLedgerPage = Math.min(ledgerPage, ledgerPageCount - 1);
  const pagedLedgerEntries = ledgerEntriesNewestFirst.slice(
    safeLedgerPage * LEDGER_PAGE_SIZE,
    safeLedgerPage * LEDGER_PAGE_SIZE + LEDGER_PAGE_SIZE,
  );

  return (
    <PageContainer
      title="Rosa"
      density="compact"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: activeLeague?.name ?? "Rosa" },
          ]}
        />
      }
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento rosa"
          message="Recupero giocatori e crediti…"
          testId="roster-loading"
        />
      ) : null}

      {!loading && showForbidden ? (
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai i permessi per visualizzare la rosa."
          testId="roster-forbidden"
        />
      ) : null}

      {!loading && !showForbidden && !loadError ? (
        <RosterSectionTabs pageSection={pageSection} onSelect={setPageSection} />
      ) : null}

      {!loading && !showForbidden && !loadError && pageSection === "storico" ? (
        <RosterHistorySection
          historyLoading={historyLoading}
          historyError={historyError}
          history={history}
          snapshots={snapshots}
          snapshotDetail={snapshotDetail}
          snapshotRound={snapshotRound}
          snapshotBusy={snapshotBusy}
          snapshotMessage={snapshotMessage}
          snapshotError={snapshotError}
          isAdmin={isAdmin}
          onSnapshotRoundChange={setSnapshotRound}
          onSelectSnapshotRound={onSelectSnapshotRound}
          onCreateSnapshot={onCreateSnapshot}
        />
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && loadError ? (
        <div data-testid="roster-error-wrap">
          <UiStatePanel
            state="error"
            title="Rosa non disponibile"
            message={loadError}
            testId="roster-error"
          />
          <Button type="button" variant="secondary" onClick={() => void loadRoster()}>
            Ricarica
          </Button>
        </div>
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && !activeLeagueId && !isDemoMode ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare la rosa."
          testId="roster-no-league"
        />
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && (viewedTeam || team) ? (
        <RosterCreditsPanel
          isAdmin={isAdmin}
          leagueTeams={leagueTeams}
          adminTeamId={adminTeamId}
          onSelectAdminTeam={onSelectAdminTeam}
          adminBusy={adminBusy}
          adjusting={adjusting}
          hasAdjustTarget={Boolean(adminTeamId || team)}
          credits={credits}
          adjustAmount={adjustAmount}
          onAdjustAmountChange={setAdjustAmount}
          adjustNote={adjustNote}
          onAdjustNoteChange={setAdjustNote}
          onAdminAdjust={onAdminAdjust}
          adjustMessage={adjustMessage}
          adjustError={adjustError}
          hasLedger={hasLedger}
          pagedLedgerEntries={pagedLedgerEntries}
          ledgerEntriesCount={ledgerEntriesNewestFirst.length}
          safeLedgerPage={safeLedgerPage}
          ledgerPageCount={ledgerPageCount}
          onLedgerPagePrev={() => setLedgerPage((page) => Math.max(0, page - 1))}
          onLedgerPageNext={() =>
            setLedgerPage((page) => Math.min(ledgerPageCount - 1, page + 1))
          }
        />
      ) : null}

      {isAdmin && !showForbidden && !loading ? (
        <>
          {SHOW_ROSTER_CSV_IMPORT ? (
            <RosterCsvImportCard
              csvBusy={csvBusy}
              onDownloadCsvTemplate={onDownloadCsvTemplate}
              csvFileInputRef={csvFileInputRef}
              onCsvFileSelected={onCsvFileSelected}
              csvCanConfirm={csvCanConfirm}
              onConfirmCsvImport={onConfirmCsvImport}
              csvMessage={csvMessage}
              csvError={csvError}
              csvPreview={csvPreview}
              csvResolutions={csvResolutions}
              onCsvResolutionChange={(rowNumber, athleteId) =>
                setCsvResolutions((current) => ({
                  ...current,
                  [rowNumber]: athleteId,
                }))
              }
            />
          ) : null}

          <RosterAdminToolsPanel
            ensuring={ensuring}
            randomAiBusy={randomAiBusy}
            onEnsureTeams={onEnsureTeams}
            leagueTeams={leagueTeams}
            adminOrViewedTeam={adminTeam ?? viewedTeam}
            onAssignRandomAiRoster={onAssignRandomAiRoster}
            ensureMessage={ensureMessage}
            ensureError={ensureError}
            randomAiMessage={randomAiMessage}
            randomAiError={randomAiError}
          />
        </>
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && viewedTeam && isEmpty ? (
        <RosterEmptyState viewedTeam={viewedTeam} onReload={loadRoster} />
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && viewedTeam && !isEmpty ? (
        <RosterFilledSummary
          viewedTeam={viewedTeam}
          filledByRole={filledByRole}
          canEdit={canEdit}
          adminBusy={adminBusy}
          onReleaseAthlete={onReleaseAthlete}
        />
      ) : null}

      {pageSection === "rosa" && canEdit && !showForbidden ? (
        <RosterAdminManualCard
          isAdmin={isAdmin}
          adminLoadError={adminLoadError}
          leagueTeams={leagueTeams}
          targetTeam={targetTeam}
          emptySlotsCount={emptySlots.length}
          purchaseCredits={purchaseCredits}
          onPurchaseCreditsChange={setPurchaseCredits}
          adminMessage={adminMessage}
          adminError={adminError}
          listone={listone}
          listoneQuery={listoneQuery}
          onListoneQueryChange={setListoneQuery}
          roleTab={roleTab}
          onRoleTabChange={setRoleTab}
          ownership={ownership}
          canReleaseAthlete={canReleaseAthlete}
          adminBusy={adminBusy}
          onReleaseAthlete={onReleaseAthlete}
          onAssignAthlete={onAssignAthlete}
        />
      ) : null}
    </PageContainer>
  );
}
