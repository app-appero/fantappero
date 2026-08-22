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
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import {
  assignRosterSlot,
  confirmRosterCsvImport,
  createRosterTurnSnapshot,
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
  previewRosterCsvImportText,
  releaseRosterSlot,
} from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

type AthleteOwnership = {
  teamId: string;
  teamName: string;
  slotIndex: number;
};

const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

const ROLE_SECTION_ORDER: FantasyRole[] = ["P", "D", "C", "A"];

const ROLE_SECTION_TITLE: Record<FantasyRole, string> = {
  P: "Portieri",
  D: "Difensori",
  C: "Centrocampisti",
  A: "Attaccanti",
};

function reasonLabel(reason: string): string {
  if (reason === "initial_allocation") {
    return "Allocazione iniziale";
  }
  if (reason === "admin_adjustment") {
    return "Aggiustamento admin";
  }
  if (reason === "roster_purchase") {
    return "Acquisto rosa";
  }
  if (reason === "roster_release_refund") {
    return "Rimborso rosa";
  }
  return reason;
}

const LEDGER_PAGE_SIZE = 10;

function formatLedgerDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sortLedgerNewestFirst(entries: CreditLedgerList["entries"]) {
  return [...entries].sort((left, right) => {
    const leftTime = Date.parse(left.createdAt);
    const rightTime = Date.parse(right.createdAt);
    if (leftTime !== rightTime) {
      return rightTime - leftTime;
    }
    return right.id.localeCompare(left.id);
  });
}

function buildOwnership(entries: RosterOccupancyEntry[]): Map<string, AthleteOwnership> {
  const map = new Map<string, AthleteOwnership>();
  for (const entry of entries) {
    map.set(entry.athleteId, {
      teamId: entry.fantasyTeamId,
      teamName: entry.teamName,
      slotIndex: entry.slotIndex,
    });
  }
  return map;
}

function roleLabel(role: string | null): string {
  if (!role) {
    return "—";
  }
  if (role in ROLE_LABEL) {
    return ROLE_LABEL[role as FantasyRole];
  }
  return role;
}

function roleBadgeColors(role: string | null | undefined): { backgroundColor: string; color: string } {
  if (role === "P") {
    return { backgroundColor: colors.success, color: colors.accentContrast };
  }
  if (role === "D") {
    return { backgroundColor: colors.warning, color: colors.background };
  }
  if (role === "C") {
    return { backgroundColor: colors.accent, color: colors.accentContrast };
  }
  if (role === "A") {
    return { backgroundColor: colors.danger, color: colors.accentContrast };
  }
  return { backgroundColor: colors.border, color: colors.foreground };
}

function toSummary(team: FantasyTeam): FantasyTeamSummary {
  return {
    id: team.id,
    leagueId: team.leagueId,
    membershipId: team.membershipId,
    userId: team.userId,
    userType: team.userType,
    name: team.name,
    rosterSize: team.rosterSize,
    filledSlots: team.filledSlots,
    compositionStatus: team.compositionStatus,
  };
}

function compositionStatusLabel(status: string | undefined): string {
  if (status === "validated") {
    return "Convalidata";
  }
  if (status === "invalid") {
    return "Non valida";
  }
  return "Incompleta";
}

/** Rosa fantasy, ledger crediti e inserimento manuale admin (EP05-01/02/03).
 * EP05-04 CSV import UI is implemented but temporarily hidden (`SHOW_ROSTER_CSV_IMPORT`).
 */
const SHOW_ROSTER_CSV_IMPORT = false;

export function RosterScreen() {
  const { can, accessToken, activeLeagueId, activeLeague } = useAuthSession();
  const isAdmin = can(["league:admin"]);
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);

  const [team, setTeam] = useState<FantasyTeam | null>(null);
  const [credits, setCredits] = useState<CreditAccount | null>(null);
  const [ledger, setLedger] = useState<CreditLedgerList | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [ensuring, setEnsuring] = useState(false);
  const [ensureMessage, setEnsureMessage] = useState<string | null>(null);
  const [ensureError, setEnsureError] = useState<string | null>(null);
  const [adjustAmount, setAdjustAmount] = useState("-10");
  const [adjustNote, setAdjustNote] = useState("");
  const [adjusting, setAdjusting] = useState(false);
  const [adjustMessage, setAdjustMessage] = useState<string | null>(null);
  const [adjustError, setAdjustError] = useState<string | null>(null);

  const [leagueTeams, setLeagueTeams] = useState<FantasyTeamSummary[]>([]);
  const [adminTeamId, setAdminTeamId] = useState("");
  const [adminTeam, setAdminTeam] = useState<FantasyTeam | null>(null);
  const [teamDetails, setTeamDetails] = useState<FantasyTeam[]>([]);
  const [listone, setListone] = useState<LeagueListoneEntry[]>([]);
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>([]);
  const [listoneQuery, setListoneQuery] = useState("");
  const [purchaseCredits, setPurchaseCredits] = useState("1");
  const [adminBusy, setAdminBusy] = useState(false);
  const [adminMessage, setAdminMessage] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [ledgerPage, setLedgerPage] = useState(0);
  const [csvText, setCsvText] = useState(
    "squadra,provider_id,nome,crediti\n",
  );
  const [csvPreview, setCsvPreview] = useState<RosterImportPreview | null>(null);
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvMessage, setCsvMessage] = useState<string | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [pageSection, setPageSection] = useState<"rosa" | "storico">("rosa");
  const [history, setHistory] = useState<RosterOwnershipHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<RosterTurnSnapshotSummary[]>([]);
  const [snapshotDetail, setSnapshotDetail] = useState<RosterTurnSnapshotDetail | null>(null);
  const [snapshotRound, setSnapshotRound] = useState("1");
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [snapshotMessage, setSnapshotMessage] = useState<string | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
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
  const filteredListone = useMemo(() => {
    const normalized = listoneQuery.trim().toLocaleLowerCase("it-IT");
    if (!normalized) {
      return listone;
    }
    return listone.filter((entry) => {
      const haystack = `${entry.canonicalName} ${entry.clubName ?? ""}`.toLocaleLowerCase("it-IT");
      return haystack.includes(normalized);
    });
  }, [listone, listoneQuery]);

  const applyTeamUpdate = useCallback((updated: FantasyTeam) => {
    setTeamDetails((current) =>
      current.some((row) => row.id === updated.id)
        ? current.map((row) => (row.id === updated.id ? updated : row))
        : [...current, updated],
    );
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

  const refreshMyCredits = useCallback(async () => {
    if (!accessToken || !activeLeagueId) {
      return;
    }
    const [nextCredits, nextLedger] = await Promise.all([
      fetchMyCredits(accessToken, activeLeagueId),
      fetchMyCreditMovements(accessToken, activeLeagueId),
    ]);
    setCredits(nextCredits);
    setLedger(nextLedger);
    setLedgerPage(0);
  }, [accessToken, activeLeagueId]);

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

  const refreshViewedCredits = useCallback(async () => {
    if (!accessToken || !activeLeagueId) {
      return;
    }
    const viewedId = adminTeamIdRef.current;
    if (isAdmin && viewedId) {
      const result = await fetchFantasyTeamCreditsForAdmin(accessToken, activeLeagueId, viewedId);
      applyLedgerResult(result);
      return;
    }
    await refreshMyCredits();
  }, [accessToken, activeLeagueId, applyLedgerResult, isAdmin, refreshMyCredits]);

  const loadEditContext = useCallback(
    async (preferredTeamId?: string) => {
      if (!canEdit || !activeLeagueId || !accessToken) {
        setLeagueTeams([]);
        setAdminTeam(null);
        setTeamDetails([]);
        setListone([]);
        setOccupancy([]);
        return;
      }
      try {
        const [entries, occupancyData] = await Promise.all([
          fetchLeagueListone(accessToken, activeLeagueId),
          fetchRosterOccupancy(accessToken, activeLeagueId),
        ]);
        setListone(entries);
        setOccupancy(occupancyData);

        if (isAdmin) {
          const teams = await fetchFantasyTeams(accessToken, activeLeagueId);
          setLeagueTeams(teams);
          const details = await Promise.all(
            teams.map((row) => fetchFantasyTeamForAdmin(accessToken, activeLeagueId, row.id)),
          );
          setTeamDetails(details);
          const nextId = preferredTeamId || adminTeamIdRef.current || teams[0]?.id || "";
          setAdminTeamId(nextId);
          setAdminTeam(details.find((row) => row.id === nextId) ?? null);
        }
      } catch {
        setLeagueTeams([]);
        setAdminTeam(null);
        setTeamDetails([]);
        setListone([]);
        setOccupancy([]);
      }
    },
    [accessToken, activeLeagueId, canEdit, isAdmin],
  );

  const loadRoster = useCallback(
    async (options?: { silent?: boolean }) => {
      setEnsureMessage(null);
      setEnsureError(null);
      setAdjustMessage(null);
      setAdjustError(null);
      setAdminMessage(null);
      setAdminError(null);

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
      if (!accessToken) {
        setLoading(false);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const [nextTeam, nextCredits, nextLedger] = await Promise.all([
          fetchMyFantasyTeam(accessToken, activeLeagueId),
          fetchMyCredits(accessToken, activeLeagueId),
          fetchMyCreditMovements(accessToken, activeLeagueId),
        ]);
        setTeam(nextTeam);
        setCredits(nextCredits);
        setLedger(nextLedger);
        if (canEdit) {
          await loadEditContext();
        }
      } catch (error) {
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError(getApiErrorMessage(error, "Impossibile caricare i giocatori della rosa."));
      } finally {
        setLoading(false);
      }
    },
    [accessToken, activeLeagueId, canView, canEdit, loadEditContext],
  );

  const { refreshing, onRefresh } = useScreenData(loadRoster);

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
    if (!canView || !activeLeagueId || !accessToken) {
      setHistory(null);
      setSnapshots([]);
      setSnapshotDetail(null);
      return;
    }
    setHistoryLoading(true);
    try {
      const historyPromise =
        isAdmin && adminTeamId
          ? fetchTeamRosterHistoryForAdmin(accessToken, activeLeagueId, adminTeamId)
          : fetchMyRosterHistory(accessToken, activeLeagueId);
      const [nextHistory, nextSnapshots] = await Promise.all([
        historyPromise,
        fetchRosterTurnSnapshots(accessToken, activeLeagueId),
      ]);
      setHistory(nextHistory);
      setSnapshots(nextSnapshots);
      const preferred = nextSnapshots.at(-1);
      if (preferred) {
        setSnapshotRound(String(preferred.roundNumber));
        const detail = await fetchRosterTurnSnapshot(
          accessToken,
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
  }, [accessToken, activeLeagueId, adminTeamId, canView, isAdmin]);

  useEffect(() => {
    if (pageSection !== "storico") {
      return;
    }
    void loadHistory();
  }, [loadHistory, pageSection]);

  const onCreateSnapshot = async () => {
    setSnapshotError(null);
    setSnapshotMessage(null);
    const roundNumber = Number(snapshotRound);
    if (!Number.isInteger(roundNumber) || roundNumber < 1) {
      setSnapshotError("Indica un numero di turno valido (≥ 1).");
      return;
    }
    if (!activeLeagueId || !accessToken) {
      setSnapshotError("Sessione o lega non disponibile.");
      return;
    }
    setSnapshotBusy(true);
    try {
      const detail = await createRosterTurnSnapshot(accessToken, activeLeagueId, { roundNumber });
      setSnapshotDetail(detail);
      setSnapshotMessage(
        detail.created
          ? `Snapshot turno ${roundNumber} creato.`
          : `Snapshot turno ${roundNumber} già presente.`,
      );
      setSnapshots(await fetchRosterTurnSnapshots(accessToken, activeLeagueId));
    } catch (error) {
      setSnapshotError(getApiErrorMessage(error, "Impossibile creare lo snapshot."));
    } finally {
      setSnapshotBusy(false);
    }
  };

  const onEnsureTeams = async () => {
    setEnsureMessage(null);
    setEnsureError(null);
    if (!activeLeagueId || !accessToken) {
      setEnsureError("Sessione o lega non disponibile.");
      return;
    }
    setEnsuring(true);
    try {
      const result = await ensureFantasyTeams(accessToken, activeLeagueId);
      setEnsureMessage(
        `Squadre aggiornate: ${result.created} create, ${result.existing} già presenti.`,
      );
      setLeagueTeams(result.teams);
      await loadRoster({ silent: true });
      await loadEditContext(result.teams[0]?.id);
    } catch (error) {
      setEnsureError(getApiErrorMessage(error, "Impossibile creare le squadre."));
    } finally {
      setEnsuring(false);
    }
  };

  const onPreviewCsvText = async () => {
    setCsvError(null);
    setCsvMessage(null);
    setCsvPreview(null);
    if (!activeLeagueId || !accessToken) {
      setCsvError("Sessione o lega non disponibile.");
      return;
    }
    setCsvBusy(true);
    try {
      const preview = await previewRosterCsvImportText(
        accessToken,
        activeLeagueId,
        csvText,
      );
      setCsvPreview(preview);
      if (preview.errorCount > 0) {
        setCsvError("Anteprima con errori: correggi il testo CSV.");
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
    if (!csvPreview || !activeLeagueId || !accessToken) {
      setCsvError("Genera prima un'anteprima valida.");
      return;
    }
    setCsvBusy(true);
    try {
      const result = await confirmRosterCsvImport(
        accessToken,
        activeLeagueId,
        csvPreview.importId,
        { resolutions: [] },
      );
      setCsvMessage(
        `Import completato: ${result.assignedCount} assegnazioni su ${result.teamsTouched} squadre.`,
      );
      setCsvPreview(null);
      await loadRoster({ silent: true });
      await loadEditContext(adminTeamId || undefined);
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile confermare l'import CSV."));
    } finally {
      setCsvBusy(false);
    }
  };

  const onSelectAdminTeam = (teamId: string) => {
    setAdminTeamId(teamId);
    setAdminMessage(null);
    setAdminError(null);
    setAdjustMessage(null);
    setAdjustError(null);
    setAdminTeam(teamDetails.find((row) => row.id === teamId) ?? null);
    if (!accessToken || !activeLeagueId) {
      return;
    }
    void (async () => {
      try {
        const result = await fetchFantasyTeamCreditsForAdmin(accessToken, activeLeagueId, teamId);
        applyLedgerResult(result);
        if (!teamDetails.some((row) => row.id === teamId)) {
          const fetched = await fetchFantasyTeamForAdmin(accessToken, activeLeagueId, teamId);
          setAdminTeam(fetched);
          setTeamDetails((current) =>
            current.some((row) => row.id === fetched.id)
              ? current.map((row) => (row.id === fetched.id ? fetched : row))
              : [...current, fetched],
          );
        }
      } catch {
        // Keep previous credits if switch fails.
      }
    })();
  };

  const onAssignAthlete = async (athleteId: string) => {
    setAdminMessage(null);
    setAdminError(null);
    if (!activeLeagueId || !accessToken || !targetTeamId || !targetTeam) {
      setAdminError("Sessione o squadra non disponibile.");
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
    setAdminBusy(true);
    try {
      const updated = await assignRosterSlot(
        accessToken,
        activeLeagueId,
        targetTeamId,
        emptySlot.slotIndex,
        { athleteId, purchaseCredits: credits },
      );
      applyTeamUpdate(updated);
      await refreshViewedCredits();
      setAdminMessage(`Assegnato a slot ${emptySlot.slotIndex + 1}.`);
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
    if (!activeLeagueId || !accessToken) {
      setAdminError("Sessione o lega non disponibile.");
      return;
    }
    setAdminBusy(true);
    try {
      const updated = await releaseRosterSlot(
        accessToken,
        activeLeagueId,
        owner.teamId,
        owner.slotIndex,
      );
      applyTeamUpdate(updated);
      await refreshViewedCredits();
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
    const adjustTeamId = adminTeamId || team?.id;
    if (!activeLeagueId || !accessToken || !adjustTeamId) {
      setAdjustError("Sessione o squadra non disponibile.");
      return;
    }
    const amount = Number.parseInt(adjustAmount, 10);
    if (!Number.isFinite(amount) || amount === 0) {
      setAdjustError("Inserisci un importo diverso da zero.");
      return;
    }
    setAdjusting(true);
    try {
      const result = await postAdminCreditMovement(accessToken, activeLeagueId, {
        fantasyTeamId: adjustTeamId,
        amount,
        transactionId: `admin:${adjustTeamId}:${Date.now()}`,
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
      testID="screen-roster"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <Text style={styles.meta}>
        {activeLeague ? `Lega: ${activeLeague.name}` : "Seleziona una lega dal selettore in alto."}
      </Text>

      {!loading && canView && !loadError ? (
        <View style={styles.chipRow} testID="roster-section-tabs">
          <Pressable
            style={[styles.chip, pageSection === "rosa" && styles.chipSelected]}
            onPress={() => setPageSection("rosa")}
            testID="roster-section-rosa"
          >
            <Text style={[styles.chipLabel, pageSection === "rosa" && styles.chipLabelSelected]}>
              Rosa
            </Text>
          </Pressable>
          <Pressable
            style={[styles.chip, pageSection === "storico" && styles.chipSelected]}
            onPress={() => setPageSection("storico")}
            testID="roster-section-storico"
          >
            <Text
              style={[styles.chipLabel, pageSection === "storico" && styles.chipLabelSelected]}
            >
              Storico
            </Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && canView && !loadError && pageSection === "storico" ? (
        <View testID="roster-history">
          {historyLoading ? (
            <UiStatePanel
              state="loading"
              title="Caricamento storico"
              message="Recupero intervalli e snapshot…"
              testID="roster-history-loading"
            />
          ) : null}
          {!historyLoading && historyError ? (
            <UiStatePanel
              state="error"
              title="Storico non disponibile"
              message={historyError}
              testID="roster-history-error"
            />
          ) : null}
          {!historyLoading && !historyError && history && history.intervals.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessun possesso registrato"
              message="Gli intervalli compaiono dopo assegnazioni o rilasci."
              testID="roster-history-empty"
            />
          ) : null}
          {!historyLoading && !historyError && history && history.intervals.length > 0 ? (
            <View testID="roster-history-success">
              <Text style={styles.summary}>Intervalli di possesso</Text>
              {history.intervals.map((row) => (
                <Text key={row.id} style={styles.meta}>
                  {row.athleteName ?? row.athleteId} · slot {row.slotIndex + 1} ·{" "}
                  {row.purchaseCredits} cr ·{" "}
                  {row.releasedAt ? "chiuso" : "in rosa"} · {row.source}
                </Text>
              ))}
            </View>
          ) : null}
          <View style={{ marginTop: spacing.md }} testID="roster-snapshots">
            <Text style={styles.summary}>Snapshot per turno</Text>
            <TextInput
              style={styles.input}
              value={snapshotRound}
              onChangeText={setSnapshotRound}
              keyboardType="numeric"
              placeholder="Numero turno"
              testID="roster-snapshot-round"
            />
            {isAdmin ? (
              <Pressable
                style={[styles.button, snapshotBusy && styles.disabled]}
                disabled={snapshotBusy}
                onPress={() => void onCreateSnapshot()}
                testID="roster-snapshot-create"
              >
                <Text style={styles.buttonLabel}>
                  {snapshotBusy ? "Salvataggio…" : "Crea snapshot turno"}
                </Text>
              </Pressable>
            ) : null}
            {snapshotMessage ? (
              <Text style={styles.ok} testID="roster-snapshot-ok">
                {snapshotMessage}
              </Text>
            ) : null}
            {snapshotError ? (
              <Text style={styles.error} testID="roster-snapshot-error">
                {snapshotError}
              </Text>
            ) : null}
            {!snapshotDetail ? (
              <UiStatePanel
                state="empty"
                title="Nessuno snapshot"
                message="Crea uno snapshot per congelare la rosa di un turno."
                testID="roster-snapshot-empty"
              />
            ) : (
              <View testID="roster-snapshot-detail">
                <Text style={styles.meta}>
                  Turno {snapshotDetail.roundNumber} · {snapshotDetail.entryCount} assegnazioni
                </Text>
                {snapshotDetail.entries.map((entry) => (
                  <Text
                    key={`${entry.fantasyTeamId}-${entry.slotIndex}-${entry.athleteId}`}
                    style={styles.meta}
                  >
                    {entry.teamName}: {entry.athleteName ?? entry.athleteId} ({entry.role ?? "—"})
                  </Text>
                ))}
                {snapshots.length > 0 ? (
                  <Text style={styles.meta}>
                    Snapshot disponibili: {snapshots.map((row) => row.roundNumber).join(", ")}
                  </Text>
                ) : null}
              </View>
            )}
          </View>
        </View>
      ) : null}

      {pageSection === "rosa" && loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento rosa"
          message="Recupero giocatori e crediti…"
          testID="roster-loading"
        />
      ) : null}

      {pageSection === "rosa" && !loading && !canView ? (
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai i permessi per visualizzare la rosa."
          testID="roster-forbidden"
        />
      ) : null}

      {pageSection === "rosa" && !loading && canView && loadError ? (
        <View>
          <UiStatePanel
            state="error"
            title="Rosa non disponibile"
            message={loadError}
            testID="roster-error"
          />
          <Pressable style={styles.button} onPress={() => void loadRoster()}>
            <Text style={styles.buttonLabel}>Ricarica</Text>
          </Pressable>
        </View>
      ) : null}

      {pageSection === "rosa" && !loading && canView && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare la rosa."
          testID="roster-no-league"
        />
      ) : null}

      {pageSection === "rosa" && !loading && canView && !loadError && (viewedTeam || team) ? (
        <View style={styles.credits} testID="roster-credits">
          {isAdmin && leagueTeams.length > 0 ? (
            <>
              <Text style={styles.summary}>Squadra target</Text>
              <View style={styles.chipRow} testID="roster-admin-team">
                {leagueTeams.map((row) => {
                  const selected = row.id === adminTeamId;
                  return (
                    <Pressable
                      key={row.id}
                      style={[styles.chip, selected && styles.chipSelected]}
                      disabled={adminBusy || adjusting}
                      onPress={() => onSelectAdminTeam(row.id)}
                    >
                      <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>
                        {row.name} ({row.filledSlots}/{row.rosterSize})
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </>
          ) : null}
          <Text style={styles.summary} testID="roster-credits-balance">
            Crediti residui: {credits?.balance ?? "—"}
            {credits ? ` (v${credits.version})` : ""}
          </Text>
          {isAdmin ? (
            <View style={styles.inlineAdjust} testID="roster-admin-credits">
              <TextInput
                style={styles.input}
                value={adjustAmount}
                onChangeText={setAdjustAmount}
                keyboardType="numeric"
                placeholder="Importo"
                testID="roster-adjust-amount"
              />
              <TextInput
                style={styles.input}
                value={adjustNote}
                onChangeText={setAdjustNote}
                placeholder="Nota"
                testID="roster-adjust-note"
              />
              <Pressable
                style={[styles.button, (adjusting || !(adminTeamId || team)) && styles.disabled]}
                disabled={adjusting || !(adminTeamId || team)}
                onPress={() => void onAdminAdjust()}
              >
                <Text style={styles.buttonLabel}>
                  {adjusting ? "Registrazione…" : "Aggiusta crediti"}
                </Text>
              </Pressable>
              {adjustMessage ? (
                <Text style={styles.ok} testID="roster-adjust-ok">
                  {adjustMessage}
                </Text>
              ) : null}
              {adjustError ? (
                <Text style={styles.error} testID="roster-adjust-error">
                  {adjustError}
                </Text>
              ) : null}
            </View>
          ) : null}
          {hasLedger ? (
            <View testID="roster-credits-ledger">
              {pagedLedgerEntries.map((entry) => {
                const note = entry.note?.trim();
                return (
                  <Text key={entry.id} style={styles.meta}>
                    {formatLedgerDate(entry.createdAt)} · {reasonLabel(entry.reason)}
                    {note ? ` — ${note}` : ""}: {entry.amount > 0 ? "+" : ""}
                    {entry.amount} → {entry.balanceAfter}
                  </Text>
                );
              })}
              {ledgerEntriesNewestFirst.length > LEDGER_PAGE_SIZE ? (
                <View style={styles.chipRow}>
                  <Pressable
                    style={[styles.chip, safeLedgerPage <= 0 && styles.disabled]}
                    disabled={safeLedgerPage <= 0}
                    testID="roster-credits-ledger-prev"
                    onPress={() => setLedgerPage((page) => Math.max(0, page - 1))}
                  >
                    <Text style={styles.chipLabel}>Precedenti</Text>
                  </Pressable>
                  <Text style={styles.meta} testID="roster-credits-ledger-page">
                    {safeLedgerPage + 1}/{ledgerPageCount}
                  </Text>
                  <Pressable
                    style={[
                      styles.chip,
                      safeLedgerPage >= ledgerPageCount - 1 && styles.disabled,
                    ]}
                    disabled={safeLedgerPage >= ledgerPageCount - 1}
                    testID="roster-credits-ledger-next"
                    onPress={() =>
                      setLedgerPage((page) => Math.min(ledgerPageCount - 1, page + 1))
                    }
                  >
                    <Text style={styles.chipLabel}>Successivi</Text>
                  </Pressable>
                </View>
              ) : null}
            </View>
          ) : (
            <UiStatePanel
              state="empty"
              title="Nessun movimento"
              message="Il ledger crediti non contiene ancora movimenti."
              testID="roster-credits-empty"
            />
          )}
        </View>
      ) : null}

      {isAdmin && canView && !loading ? (
        <>
          {SHOW_ROSTER_CSV_IMPORT ? (
          <View style={styles.card} testID="roster-csv-import">
            <Text style={styles.cardTitle}>Import CSV rose</Text>
            <Text style={styles.meta}>
              Incolla il CSV (colonne squadra,provider_id,nome,crediti), genera anteprima e
              conferma solo senza errori.
            </Text>
            <TextInput
              style={[styles.input, styles.csvInput]}
              multiline
              value={csvText}
              onChangeText={setCsvText}
              editable={!csvBusy}
              testID="roster-csv-text"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <Pressable
              style={[styles.button, csvBusy && styles.disabled]}
              disabled={csvBusy}
              onPress={() => void onPreviewCsvText()}
              testID="roster-csv-preview-btn"
            >
              <Text style={styles.buttonLabel}>
                {csvBusy ? "Elaborazione…" : "Anteprima CSV"}
              </Text>
            </Pressable>
            <Pressable
              style={[
                styles.button,
                (csvBusy || !csvPreview?.canConfirm) && styles.disabled,
              ]}
              disabled={csvBusy || !csvPreview?.canConfirm}
              onPress={() => void onConfirmCsvImport()}
              testID="roster-csv-confirm"
            >
              <Text style={styles.buttonLabel}>Conferma import</Text>
            </Pressable>
            {csvPreview ? (
              <Text style={styles.meta} testID="roster-csv-preview">
                Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount} · avvisi{" "}
                {csvPreview.warningCount}
              </Text>
            ) : null}
            {csvMessage ? (
              <Text style={styles.ok} testID="roster-csv-ok">
                {csvMessage}
              </Text>
            ) : null}
            {csvError ? (
              <Text style={styles.error} testID="roster-csv-error">
                {csvError}
              </Text>
            ) : null}
          </View>
          ) : null}

          <View style={styles.admin} testID="roster-admin-tools">
            <Pressable
              style={[styles.button, ensuring && styles.disabled]}
              disabled={ensuring}
              onPress={() => void onEnsureTeams()}
            >
              <Text style={styles.buttonLabel}>
                {ensuring ? "Verifica in corso…" : "Assicura squadre partecipanti"}
              </Text>
            </Pressable>
            {ensureMessage ? (
              <Text style={styles.ok} testID="roster-ensure-ok">
                {ensureMessage}
              </Text>
            ) : null}
            {ensureError ? (
              <Text style={styles.error} testID="roster-ensure-error">
                {ensureError}
              </Text>
            ) : null}
          </View>
        </>
      ) : null}

      {pageSection === "rosa" && !loading && canView && !loadError && viewedTeam && isEmpty ? (
        <View testID="roster-empty">
          <UiStatePanel
            state="empty"
            title="Rosa vuota"
            message="Completa l'asta o importa i giocatori per popolare la rosa."
          />
          <Text style={styles.summary} testID="roster-empty-summary">
            {viewedTeam.name}: 0/{viewedTeam.rosterSize} slot occupati
          </Text>
        </View>
      ) : null}

      {pageSection === "rosa" && !loading && canView && !loadError && viewedTeam && !isEmpty ? (
        <View testID="roster-success">
          <Text style={styles.summary} testID="roster-summary">
            {viewedTeam.name}: {viewedTeam.filledSlots}/{viewedTeam.rosterSize} giocatori
          </Text>
          {viewedTeam.composition ? (
            <View testID="roster-composition" style={styles.compositionBox}>
              <Text style={styles.meta}>
                Composizione: {compositionStatusLabel(viewedTeam.composition.status)}
              </Text>
              <Text style={styles.meta} testID="roster-composition-counts">
                {viewedTeam.composition.counts.P}/{viewedTeam.composition.limits.goalkeepers}P ·{" "}
                {viewedTeam.composition.counts.D}/{viewedTeam.composition.limits.defenders}D ·{" "}
                {viewedTeam.composition.counts.C}/{viewedTeam.composition.limits.midfielders}C ·{" "}
                {viewedTeam.composition.counts.A}/{viewedTeam.composition.limits.forwards}A ·{" "}
                {viewedTeam.composition.competitionCount} campionati
              </Text>
              {viewedTeam.composition.issues.map((issue) => (
                <Text key={`${issue.code}-${issue.message}`} style={styles.errorText}>
                  {issue.message}
                </Text>
              ))}
            </View>
          ) : null}
          <View testID="roster-filled-table" style={styles.roleTables}>
            {ROLE_SECTION_ORDER.map((role) => {
              const slots = filledByRole[role];
              const limit =
                viewedTeam.composition?.limits == null
                  ? null
                  : role === "P"
                    ? viewedTeam.composition.limits.goalkeepers
                    : role === "D"
                      ? viewedTeam.composition.limits.defenders
                      : role === "C"
                        ? viewedTeam.composition.limits.midfielders
                        : viewedTeam.composition.limits.forwards;
              const roleColors = roleBadgeColors(role);
              return (
                <View key={role} style={styles.roleSection} testID={`roster-filled-table-${role}`}>
                  <View style={styles.roleSectionHeader}>
                    <View style={[styles.roleBadge, roleColors]}>
                      <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{role}</Text>
                    </View>
                    <Text style={styles.roleSectionTitle}>{ROLE_SECTION_TITLE[role]}</Text>
                    <Text style={styles.roleSectionCount}>
                      {slots.length}
                      {limit != null ? `/${limit}` : ""}
                    </Text>
                  </View>
                  {slots.length === 0 ? (
                    <Text style={styles.meta}>Nessun giocatore in questo ruolo.</Text>
                  ) : (
                    slots.map((slot) => (
                      <View key={slot.id} style={styles.card}>
                        <Text style={styles.cardTitle}>{slot.athleteName ?? "Calciatore"}</Text>
                        <Text style={styles.meta}>
                          Club: {slot.clubName ?? "—"} · Crediti: {slot.purchaseCredits ?? "—"} ·
                          Slot {slot.slotIndex + 1}
                        </Text>
                        {canEdit && slot.athleteId ? (
                          <Pressable
                            style={[styles.button, adminBusy && styles.disabled]}
                            disabled={adminBusy}
                            testID={`roster-admin-release-${slot.athleteId}`}
                            onPress={() => void onReleaseAthlete(slot.athleteId!)}
                          >
                            <Text style={styles.buttonLabel}>Rimuovi</Text>
                          </Pressable>
                        ) : null}
                      </View>
                    ))
                  )}
                </View>
              );
            })}
            {filledByRole.unknown.length > 0 ? (
              <View style={styles.roleSection} testID="roster-filled-table-unknown">
                <View style={styles.roleSectionHeader}>
                  <Text style={styles.roleSectionTitle}>Senza ruolo</Text>
                  <Text style={styles.roleSectionCount}>{filledByRole.unknown.length}</Text>
                </View>
                {filledByRole.unknown.map((slot) => (
                  <View key={slot.id} style={styles.card}>
                    <Text style={styles.cardTitle}>{slot.athleteName ?? "Calciatore"}</Text>
                    <Text style={styles.meta}>
                      Club: {slot.clubName ?? "—"} · Crediti: {slot.purchaseCredits ?? "—"} · Slot{" "}
                      {slot.slotIndex + 1}
                    </Text>
                    {canEdit && slot.athleteId ? (
                      <Pressable
                        style={[styles.button, adminBusy && styles.disabled]}
                        disabled={adminBusy}
                        testID={`roster-admin-release-${slot.athleteId}`}
                        onPress={() => void onReleaseAthlete(slot.athleteId!)}
                      >
                        <Text style={styles.buttonLabel}>Rimuovi</Text>
                      </Pressable>
                    ) : null}
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        </View>
      ) : null}

      {pageSection === "rosa" && canEdit && canView ? (
        <View style={styles.adjust} testID="roster-admin-manual">
          <View style={styles.headerRow}>
            <Text style={styles.summary}>Inserimento manuale rose</Text>
          </View>
          {isAdmin && leagueTeams.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessuna squadra"
              message="Assicura prima le squadre dei partecipanti."
              testID="roster-admin-manual-empty"
            />
          ) : !isAdmin && !targetTeam ? (
            <UiStatePanel
              state="empty"
              title="Nessuna squadra"
              message="La tua rosa non è ancora disponibile."
              testID="roster-admin-manual-empty"
            />
          ) : (
            <>
              {targetTeam ? (
                <Text style={styles.meta} testID="roster-admin-team-summary">
                  {targetTeam.name}: {targetTeam.filledSlots}/{targetTeam.rosterSize} ·{" "}
                  {emptySlots.length} liberi
                </Text>
              ) : null}

              <Text style={styles.meta}>Crediti acquisto</Text>
              <TextInput
                style={styles.input}
                value={purchaseCredits}
                onChangeText={setPurchaseCredits}
                keyboardType="numeric"
                testID="roster-purchase-credits"
              />

              {listone.length === 0 ? (
                <UiStatePanel
                  state="empty"
                  title="Listone vuoto"
                  message="Il listone ufficiale non è ancora disponibile. Verrà popolato dagli operatori della piattaforma."
                  testID="roster-admin-listone-empty"
                />
              ) : (
                <View testID="roster-admin-listone-table-all">
                  <TextInput
                    style={styles.input}
                    value={listoneQuery}
                    onChangeText={setListoneQuery}
                    placeholder="Cerca per nome o club…"
                    autoCapitalize="none"
                    autoCorrect={false}
                    testID="roster-admin-listone-search"
                  />
                  {filteredListone.length === 0 ? (
                    <UiStatePanel
                      state="empty"
                      title="Nessun calciatore"
                      message="Nessun risultato per la ricerca corrente."
                      testID="roster-admin-listone-search-empty"
                    />
                  ) : (
                    filteredListone.map((entry) => {
                      const owner = ownership.get(entry.athleteId);
                      const canAssign = !owner && emptySlots.length > 0;
                      const canRelease = owner ? canReleaseAthlete(owner.teamId) : false;
                      const roleColors = roleBadgeColors(entry.effectiveRole);
                      return (
                        <View key={entry.athleteId} style={styles.card}>
                          <View style={styles.row}>
                            <View style={[styles.roleBadge, roleColors]}>
                              <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>
                                {entry.effectiveRole}
                              </Text>
                            </View>
                            <Text style={styles.cardTitle}>{entry.canonicalName}</Text>
                          </View>
                          <Text style={styles.meta}>
                            {ROLE_LABEL[entry.effectiveRole]}
                            {entry.clubName ? ` · ${entry.clubName}` : ""}
                            {owner ? ` · In rosa: ${owner.teamName}` : " · Libero"}
                          </Text>
                          {owner && canRelease ? (
                            <Pressable
                              style={[styles.button, adminBusy && styles.disabled]}
                              disabled={adminBusy}
                              testID={`roster-admin-release-${entry.athleteId}`}
                              onPress={() => void onReleaseAthlete(entry.athleteId)}
                            >
                              <Text style={styles.buttonLabel}>Rimuovi</Text>
                            </Pressable>
                          ) : !owner ? (
                            <Pressable
                              style={[
                                styles.button,
                                (adminBusy || !canAssign) && styles.disabled,
                              ]}
                              disabled={adminBusy || !canAssign}
                              testID={`roster-admin-assign-${entry.athleteId}`}
                              onPress={() => void onAssignAthlete(entry.athleteId)}
                            >
                              <Text style={styles.buttonLabel}>Assegna</Text>
                            </Pressable>
                          ) : null}
                        </View>
                      );
                    })
                  )}
                </View>
              )}

              {adminMessage ? (
                <Text style={styles.ok} testID="roster-admin-ok">
                  {adminMessage}
                </Text>
              ) : null}
              {adminError ? (
                <Text style={styles.error} testID="roster-admin-assign-error">
                  {adminError}
                </Text>
              ) : null}
            </>
          )}
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  summary: {
    fontSize: typography.fontSize.md,
    color: colors.foreground,
    marginBottom: spacing.sm,
  },
  meta: {
    fontSize: typography.fontSize.sm,
    color: colors.muted,
    marginBottom: spacing.sm,
  },
  compositionBox: {
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  errorText: {
    fontSize: typography.fontSize.sm,
    color: colors.danger,
  },
  roleTables: {
    gap: spacing.md,
  },
  roleSection: {
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  roleSectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  roleSectionTitle: {
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
    flex: 1,
  },
  roleSectionCount: {
    fontSize: typography.fontSize.sm,
    color: colors.muted,
  },
  credits: {
    marginBottom: spacing.md,
  },
  inlineAdjust: {
    marginBottom: spacing.sm,
    gap: spacing.xs,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  card: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    backgroundColor: colors.background,
  },
  cardTitle: {
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
    flexShrink: 1,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  roleBadge: {
    minWidth: 28,
    height: 28,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  roleBadgeText: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  admin: {
    marginTop: spacing.lg,
  },
  adjust: {
    marginTop: spacing.md,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: colors.background,
  },
  chipSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.accent,
  },
  chipLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.foreground,
  },
  chipLabelSelected: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.background,
    minHeight: 44,
  },
  csvInput: {
    minHeight: 120,
    textAlignVertical: "top",
  },
  button: {
    marginTop: spacing.sm,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    minHeight: 44,
    justifyContent: "center",
  },
  disabled: {
    opacity: 0.6,
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  ok: {
    fontSize: typography.fontSize.sm,
    color: colors.foreground,
    marginTop: spacing.sm,
  },
  error: {
    fontSize: typography.fontSize.sm,
    color: colors.danger,
    marginTop: spacing.sm,
  },
});
