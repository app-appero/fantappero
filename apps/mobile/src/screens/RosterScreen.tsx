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
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, Text, View } from "react-native";
import {
  assignRandomAiRoster,
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
import { ScreenTabs } from "../components/ScreenTabs";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { MARKET_HUB_TABS } from "../navigation/marketHubTabs";
import type { AppTabParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { RosterAdminManualCard } from "./roster/RosterAdminManualCard";
import { RosterAdminToolsPanel } from "./roster/RosterAdminToolsPanel";
import { RosterCreditsPanel } from "./roster/RosterCreditsPanel";
import { RosterCsvImportCard } from "./roster/RosterCsvImportCard";
import { RosterEmptyState } from "./roster/RosterEmptyState";
import { RosterFilledSummary } from "./roster/RosterFilledSummary";
import {
  buildOwnership,
  LEDGER_PAGE_SIZE,
  sortLedgerNewestFirst,
  toSummary,
  type AthleteOwnership,
} from "./roster/rosterHelpers";
import { RosterHistorySection } from "./roster/RosterHistorySection";
import { RosterSectionTabs } from "./roster/RosterSectionTabs";
import { rosterStyles as styles } from "./roster/rosterStyles";

/** Rosa fantasy, ledger crediti e inserimento manuale admin (EP05-01/02/03).
 * EP05-04 CSV import UI is implemented but temporarily hidden (`SHOW_ROSTER_CSV_IMPORT`).
 */
const SHOW_ROSTER_CSV_IMPORT = false;

export function RosterScreen() {
  const navigation = useNavigation<NavigationProp<AppTabParamList>>();
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
  const [randomAiBusy, setRandomAiBusy] = useState(false);
  const [randomAiMessage, setRandomAiMessage] = useState<string | null>(null);
  const [randomAiError, setRandomAiError] = useState<string | null>(null);
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

  const onAssignRandomAiRoster = async () => {
    setRandomAiMessage(null);
    setRandomAiError(null);
    const targetId = adminTeamId || viewedTeam?.id;
    const resolvedTarget =
      (targetId ? teamDetails.find((row) => row.id === targetId) : null) ??
      adminTeam ??
      viewedTeam;
    if (!resolvedTarget || resolvedTarget.userType !== "ai") {
      setRandomAiError("Seleziona una squadra di un fantallenatore IA.");
      return;
    }
    if (resolvedTarget.filledSlots >= resolvedTarget.rosterSize) {
      setRandomAiMessage("La rosa del fantallenatore IA è già completa.");
      return;
    }
    if (!activeLeagueId || !accessToken) {
      setRandomAiError("Sessione o lega non disponibile.");
      return;
    }
    setRandomAiBusy(true);
    try {
      const updated = await assignRandomAiRoster(accessToken, activeLeagueId, resolvedTarget.id);
      setAdminTeam(updated);
      setTeamDetails((current) => current.map((row) => (row.id === updated.id ? updated : row)));
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
      setRandomAiMessage(`Rosa random assegnata: ${updated.filledSlots}/${updated.rosterSize} giocatori.`);
      await loadEditContext(updated.id);
    } catch (error) {
      setRandomAiError(getApiErrorMessage(error, "Impossibile assegnare la rosa random."));
    } finally {
      setRandomAiBusy(false);
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
      <ScreenTabs
        items={MARKET_HUB_TABS}
        activeId="Roster"
        onSelect={(id) => navigation.navigate(id as keyof AppTabParamList)}
        testID="market-hub-tabs"
      />
      <Text style={styles.meta}>
        {activeLeague ? `Lega: ${activeLeague.name}` : "Seleziona una lega dal selettore in alto."}
      </Text>

      {!loading && canView && !loadError ? (
        <RosterSectionTabs pageSection={pageSection} onSelect={setPageSection} />
      ) : null}

      {!loading && canView && !loadError && pageSection === "storico" ? (
        <RosterHistorySection
          historyLoading={historyLoading}
          historyError={historyError}
          history={history}
          snapshots={snapshots}
          snapshotDetail={snapshotDetail}
          snapshotRound={snapshotRound}
          onSnapshotRoundChange={setSnapshotRound}
          snapshotBusy={snapshotBusy}
          isAdmin={isAdmin}
          onCreateSnapshot={onCreateSnapshot}
          snapshotMessage={snapshotMessage}
          snapshotError={snapshotError}
        />
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

      {isAdmin && canView && !loading ? (
        <>
          {SHOW_ROSTER_CSV_IMPORT ? (
            <RosterCsvImportCard
              csvText={csvText}
              onCsvTextChange={setCsvText}
              csvBusy={csvBusy}
              onPreviewCsvText={onPreviewCsvText}
              csvPreview={csvPreview}
              onConfirmCsvImport={onConfirmCsvImport}
              csvMessage={csvMessage}
              csvError={csvError}
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

      {pageSection === "rosa" && !loading && canView && !loadError && viewedTeam && isEmpty ? (
        <RosterEmptyState viewedTeam={viewedTeam} />
      ) : null}

      {pageSection === "rosa" && !loading && canView && !loadError && viewedTeam && !isEmpty ? (
        <RosterFilledSummary
          viewedTeam={viewedTeam}
          filledByRole={filledByRole}
          canEdit={canEdit}
          adminBusy={adminBusy}
          onReleaseAthlete={onReleaseAthlete}
        />
      ) : null}

      {pageSection === "rosa" && canEdit && canView ? (
        <RosterAdminManualCard
          isAdmin={isAdmin}
          leagueTeams={leagueTeams}
          targetTeam={targetTeam}
          emptySlotsCount={emptySlots.length}
          purchaseCredits={purchaseCredits}
          onPurchaseCreditsChange={setPurchaseCredits}
          listone={listone}
          listoneQuery={listoneQuery}
          onListoneQueryChange={setListoneQuery}
          filteredListone={filteredListone}
          ownership={ownership}
          canReleaseAthlete={canReleaseAthlete}
          adminBusy={adminBusy}
          onReleaseAthlete={onReleaseAthlete}
          onAssignAthlete={onAssignAthlete}
          adminMessage={adminMessage}
          adminError={adminError}
        />
      ) : null}
    </PageContainer>
  );
}
