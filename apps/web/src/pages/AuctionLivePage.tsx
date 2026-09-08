import type {
  FantasyTeamSummary,
  LeagueListoneEntry,
  LiveAuctionSession,
  LiveLot,
  LiveRaise,
  MarketLiveNominationMode,
  PendingSwapDecision,
  RosterOccupancyEntry,
} from "@fantappero/contracts";
import { computeMinimumNextBid } from "@fantappero/contracts";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Modal,
  Select,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchFantasyTeams,
  fetchLeagueListone,
  fetchLeagueMembersPublic,
  fetchMyCredits,
  fetchRosterOccupancy,
} from "../api/leagues";
import {
  cancelLiveAuctionLot,
  createLiveAuctionSession,
  declineLiveAuctionSwap,
  endLiveAuctionSession,
  fetchLiveAuctionLots,
  fetchLiveAuctionSessions,
  forceSellLiveAuctionLot,
  nominateLiveAuctionLot,
  passLiveAuctionLot,
  placeLiveAuctionRaise,
  resolveLiveAuctionSwap,
  startLiveAuctionSession,
} from "../api/marketLive";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLiveAuctionPolling } from "../market/useLiveAuctionPolling";
import { LiveAuctionTable } from "./auction-live/LiveAuctionTable";

const SESSION_STATUS_LABEL: Record<string, string> = {
  scheduled: "Programmata",
  open: "In corso",
  resolved: "Terminata",
};

const LOT_STATUS_LABEL: Record<string, string> = {
  open: "In corso",
  sold: "Aggiudicato",
  passed: "Non assegnato",
  cancelled: "Annullato",
  pending_swap: "In attesa di scambio",
};

// Le 5 modalità di chiamata: due storiche (manual, sequential) più tre nuove
// (turn_based, alphabetical_by_role, random). Etichetta breve per lo stato
// sessione + opzione/spiegazione estesa per il form di creazione, così
// l'admin sa cosa sta scegliendo *prima* di avviare l'asta live.
const NOMINATION_MODE_SHORT_LABEL: Record<MarketLiveNominationMode, string> = {
  manual: "scelta libera",
  turn_based: "a richiamo (a turno)",
  sequential: "lista prestabilita",
  alphabetical_by_role: "alfabetico per ruolo",
  random: "casuale",
};

const NOMINATION_MODE_OPTIONS: Array<{ value: MarketLiveNominationMode; label: string }> = [
  { value: "manual", label: "Libera — sceglie l'admin/delegato" },
  { value: "turn_based", label: "A richiamo (a turno)" },
  { value: "sequential", label: "Lista prestabilita" },
  { value: "alphabetical_by_role", label: "Alfabetico per ruolo" },
  { value: "random", label: "Casuale" },
];

const NOMINATION_MODE_HINT: Record<MarketLiveNominationMode, string> = {
  manual:
    "L'amministratore (o il delegato) sceglie liberamente, in qualsiasi momento della sessione, quale calciatore mettere all'asta.",
  turn_based:
    "A ogni chiamata tocca a un fantallenatore diverso: l'ordine di turno viene estratto a sorte all'avvio della sessione e si ripete ciclicamente finché la sessione è aperta. L'admin/delegato può comunque chiamare in ogni momento, ad esempio se un fantallenatore non è disponibile.",
  sequential:
    "Prepari tu l'elenco esatto e ordinato dei calciatori: verranno chiamati automaticamente uno dopo l'altro, nell'ordine scelto qui sotto.",
  alphabetical_by_role:
    "I calciatori liberi vengono chiamati automaticamente in ordine alfabetico, raggruppati per ruolo: prima i portieri, poi difensori, centrocampisti e attaccanti.",
  random:
    "I calciatori liberi vengono chiamati automaticamente in un ordine casuale, estratto una sola volta all'avvio della sessione.",
};

// Modalità che generano da sole la coda di chiamata (nessun elenco da compilare).
const AUTO_QUEUE_MODES: MarketLiveNominationMode[] = ["sequential", "alphabetical_by_role", "random"];

// Solo per l'anteprima visiva del tavolo in modalità demo: nessun dato reale.
const DEMO_TABLE_TEAMS: FantasyTeamSummary[] = [
  { id: "d1", leagueId: "demo", membershipId: "d1", userId: "d1", userType: "human", name: "Romy", rosterSize: 35, filledSlots: 4, compositionStatus: "incomplete" },
  { id: "d2", leagueId: "demo", membershipId: "d2", userId: "d2", userType: "human", name: "Bomber FC", rosterSize: 35, filledSlots: 3, compositionStatus: "incomplete" },
  { id: "d3", leagueId: "demo", membershipId: "d3", userId: "d3", userType: "human", name: "Gli Invincibili", rosterSize: 35, filledSlots: 5, compositionStatus: "incomplete" },
  { id: "d4", leagueId: "demo", membershipId: "d4", userId: "d4", userType: "ai", name: "Rete e Fuga", rosterSize: 35, filledSlots: 2, compositionStatus: "incomplete" },
  { id: "d5", leagueId: "demo", membershipId: "d5", userId: "d5", userType: "human", name: "Fantavolpe", rosterSize: 35, filledSlots: 4, compositionStatus: "incomplete" },
  { id: "d6", leagueId: "demo", membershipId: "d6", userId: "d6", userType: "human", name: "Aquile Nere", rosterSize: 35, filledSlots: 3, compositionStatus: "incomplete" },
];

const DEMO_TABLE_LOT: LiveLot = {
  id: "demo-lot",
  sessionId: "demo-session",
  athleteId: "demo-athlete",
  athleteName: "L. Martinez",
  sequenceNumber: 4,
  status: "open",
  openedAt: new Date().toISOString(),
  closesAt: new Date(Date.now() + 18_000).toISOString(),
  minIncrementCredits: 5,
  currentLeaderTeamId: "d3",
  currentLeaderTeamName: "Gli Invincibili",
  currentAmountCredits: 45,
  minimumNextAmountCredits: 50,
  closedAt: null,
};

/** Schermata Asta a rilanci: sessioni live collegate alle API reali (EP08-09). */
export function AuctionLivePage() {
  const { isDemoMode, activeLeagueId, can, user } = useAuth();
  const canManageSession = can(["market:manage"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>([]);
  const [members, setMembers] = useState<Array<{ userId: string; displayName: string }>>([]);
  const [teams, setTeams] = useState<FantasyTeamSummary[]>([]);
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>([]);
  const [balance, setBalance] = useState<number | null>(null);

  const [sessions, setSessions] = useState<LiveAuctionSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [currentLot, setCurrentLot] = useState<LiveLot | null>(null);
  const [recentRaises, setRecentRaises] = useState<LiveRaise[]>([]);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [lotHistory, setLotHistory] = useState<LiveLot[]>([]);
  const [pendingSwap, setPendingSwap] = useState<PendingSwapDecision | null>(null);
  const [currentTurnTeamId, setCurrentTurnTeamId] = useState<string | null>(null);
  const [currentTurnTeamName, setCurrentTurnTeamName] = useState<string | null>(null);

  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const currentSession = sessions.find((row) => row.status !== "resolved") ?? null;
  const isOperator =
    !!currentSession &&
    !!user &&
    (canManageSession || currentSession.operatorUserId === user.id);
  // Modalità "a richiamo": la squadra sul cui turno tocca chiamare può farlo
  // anche senza essere admin/delegato (autorizzazione fine lato server).
  const myTeam = useMemo(
    () => (user ? (teams.find((row) => row.userId === user.id) ?? null) : null),
    [teams, user],
  );
  const isMyTurnToNominate =
    !!currentSession &&
    currentSession.nominationMode === "turn_based" &&
    !!myTeam &&
    myTeam.id === currentTurnTeamId;
  const canNominate = isOperator || isMyTurnToNominate;
  const needsExplicitAthlete =
    currentSession?.nominationMode === "manual" || currentSession?.nominationMode === "turn_based";

  const load = useCallback(async () => {
    if (isDemoMode) {
      setLoading(false);
      setLoadError(null);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
      setSessions([]);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [rows, listone, memberRows, teamRows, occupancyRows, credits] = await Promise.all([
        fetchLiveAuctionSessions(stored.accessToken, activeLeagueId),
        fetchLeagueListone(stored.accessToken, activeLeagueId),
        fetchLeagueMembersPublic(stored.accessToken, activeLeagueId),
        fetchFantasyTeams(stored.accessToken, activeLeagueId),
        fetchRosterOccupancy(stored.accessToken, activeLeagueId).catch(() => []),
        fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null),
      ]);
      setSessions(rows);
      setEntries(listone);
      setMembers(memberRows);
      setTeams(teamRows);
      setOccupancy(occupancyRows);
      if (credits) setBalance(credits.balance);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare l'asta a rilanci."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, isDemoMode]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadLots = useCallback(async () => {
    if (isDemoMode || !activeLeagueId || !currentSession) {
      setLotHistory([]);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    try {
      const result = await fetchLiveAuctionLots(stored.accessToken, activeLeagueId, currentSession.id);
      setLotHistory(result.lots);
    } catch {
      // Storico non critico: la vista corrente resta comunque aggiornata dal polling.
    }
  }, [activeLeagueId, currentSession, isDemoMode]);

  useEffect(() => {
    void loadLots();
  }, [loadLots]);

  const { degraded } = useLiveAuctionPolling(
    activeLeagueId,
    currentSession?.status === "open" ? currentSession.id : null,
    (next) => {
      setSessions((prev) => prev.map((row) => (row.id === next.session.id ? next.session : row)));
      setCurrentLot(next.currentLot);
      setRecentRaises(next.recentRaises);
      setSecondsRemaining(next.secondsRemaining);
      setPendingSwap(next.pendingSwap);
      setCurrentTurnTeamId(next.currentTurnTeamId);
      setCurrentTurnTeamName(next.currentTurnTeamName);
      if (next.currentLot === null) {
        void loadLots();
      }
    },
    !isDemoMode && currentSession?.status === "open",
  );

  // -- creazione sessione (admin) --------------------------------------------

  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [nominationMode, setNominationMode] = useState<MarketLiveNominationMode>("manual");
  const [minIncrement, setMinIncrement] = useState("10");
  const [softClose, setSoftClose] = useState("15");
  const [lotDuration, setLotDuration] = useState("30");
  const [operatorUserId, setOperatorUserId] = useState("");
  const [queueAthleteIds, setQueueAthleteIds] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const freeAgents = useMemo(() => entries, [entries]);
  const ownedAthleteIds = useMemo(() => new Set(occupancy.map((row) => row.athleteId)), [occupancy]);

  function toggleQueueAthlete(athleteId: string) {
    setQueueAthleteIds((current) =>
      current.includes(athleteId)
        ? current.filter((id) => id !== athleteId)
        : [...current, athleteId],
    );
  }

  async function handleCreateSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeLeagueId || !opensAt || !closesAt) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createLiveAuctionSession(stored.accessToken, activeLeagueId, {
        opensAt: new Date(opensAt).toISOString(),
        closesAt: new Date(closesAt).toISOString(),
        nominationMode,
        minIncrementCredits: Number(minIncrement) || 1,
        softCloseSeconds: Number(softClose) || 5,
        lotDurationSeconds: Number(lotDuration) || 10,
        operatorUserId: operatorUserId || null,
        nominationQueueAthleteIds: nominationMode === "sequential" ? queueAthleteIds : null,
      });
      setSessions((prev) => [created, ...prev]);
    } catch (error) {
      setCreateError(getApiErrorMessage(error, "Impossibile creare la sessione."));
    } finally {
      setCreating(false);
    }
  }

  // -- azioni operatore (e, per la chiamata in modalità "a turno", anche il
  // fantallenatore di turno — vedi `canNominate`) -----------------------------

  async function runOperatorAction<T>(action: () => Promise<T>, successMessage: string) {
    setActionMessage(null);
    setActionError(null);
    setActionBusy(true);
    try {
      await action();
      setActionMessage(successMessage);
      await load();
      await loadLots();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Operazione non riuscita."));
    } finally {
      setActionBusy(false);
    }
  }

  const [manualAthleteId, setManualAthleteId] = useState("");

  function handleStart() {
    if (!activeLeagueId || !currentSession) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    void runOperatorAction(
      () => startLiveAuctionSession(stored.accessToken, activeLeagueId, currentSession.id),
      "Sessione avviata.",
    );
  }

  function handleEnd() {
    if (!activeLeagueId || !currentSession) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    void runOperatorAction(
      () => endLiveAuctionSession(stored.accessToken, activeLeagueId, currentSession.id),
      "Sessione terminata.",
    );
  }

  function handleNominate() {
    if (!activeLeagueId || !currentSession) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    void runOperatorAction(async () => {
      const lot = await nominateLiveAuctionLot(stored.accessToken, activeLeagueId, currentSession.id, {
        athleteId: needsExplicitAthlete ? manualAthleteId : null,
      });
      setCurrentLot(lot);
      setManualAthleteId("");
    }, "Calciatore chiamato.");
  }

  function handleForceSell() {
    if (!activeLeagueId || !currentSession || !currentLot) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    void runOperatorAction(
      () => forceSellLiveAuctionLot(stored.accessToken, activeLeagueId, currentSession.id, currentLot.id),
      "Lotto aggiudicato.",
    );
  }

  function handlePass() {
    if (!activeLeagueId || !currentSession || !currentLot) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    void runOperatorAction(
      () => passLiveAuctionLot(stored.accessToken, activeLeagueId, currentSession.id, currentLot.id),
      "Lotto saltato.",
    );
  }

  function handleCancel() {
    if (!activeLeagueId || !currentSession || !currentLot) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    void runOperatorAction(
      () => cancelLiveAuctionLot(stored.accessToken, activeLeagueId, currentSession.id, currentLot.id),
      "Nomina annullata.",
    );
  }

  // -- rilancio (qualunque partecipante) ---------------------------------------

  const [raiseBusy, setRaiseBusy] = useState(false);
  const [raiseError, setRaiseError] = useState<string | null>(null);

  const minimumNextBid = currentLot
    ? computeMinimumNextBid(
        currentLot.currentAmountCredits,
        currentLot.currentLeaderTeamId !== null,
        currentLot.minIncrementCredits,
      )
    : null;

  function handleRaise(amount: number) {
    if (!activeLeagueId || !currentSession || !currentLot) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    setRaiseBusy(true);
    setRaiseError(null);
    placeLiveAuctionRaise(stored.accessToken, activeLeagueId, currentSession.id, currentLot.id, {
      amountCredits: amount,
    })
      .then((lot) => {
        setCurrentLot(lot);
        return fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null);
      })
      .then((credits) => {
        if (credits) setBalance(credits.balance);
      })
      .catch((error) => setRaiseError(getApiErrorMessage(error, "Rilancio non riuscito.")))
      .finally(() => setRaiseBusy(false));
  }

  // -- scambio rosa piena (EP08-09) --------------------------------------------

  const [swapBusy, setSwapBusy] = useState(false);
  const [swapError, setSwapError] = useState<string | null>(null);

  function handleResolveSwap(releaseAthleteId: string) {
    if (!activeLeagueId || !currentSession || !pendingSwap) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    setSwapBusy(true);
    setSwapError(null);
    resolveLiveAuctionSwap(stored.accessToken, activeLeagueId, currentSession.id, pendingSwap.lotId, {
      releaseAthleteId,
    })
      .then(() => {
        setPendingSwap(null);
        return load();
      })
      .catch((error) => setSwapError(getApiErrorMessage(error, "Scambio non riuscito.")))
      .finally(() => setSwapBusy(false));
  }

  function handleDeclineSwap() {
    if (!activeLeagueId || !currentSession || !pendingSwap) return;
    const stored = loadStoredSession();
    if (!stored?.accessToken) return;
    setSwapBusy(true);
    setSwapError(null);
    declineLiveAuctionSwap(stored.accessToken, activeLeagueId, currentSession.id, pendingSwap.lotId)
      .then(() => {
        setPendingSwap(null);
        return load();
      })
      .catch((error) => setSwapError(getApiErrorMessage(error, "Operazione non riuscita.")))
      .finally(() => setSwapBusy(false));
  }

  if (isDemoMode) {
    return (
      <div data-testid="auction-live-demo-placeholder">
        <UiStatePanel
          state="empty"
          title="Non disponibile in demo"
          message="L'asta a rilanci richiede una sessione reale collegata alla lega. Sotto, un'anteprima solo visiva del tavolo (dati inventati)."
        />
        <LiveAuctionTable teams={DEMO_TABLE_TEAMS} currentLot={DEMO_TABLE_LOT} secondsRemaining={18} />
      </div>
    );
  }

  return (
    <>
      {loading ? (
        <UiStatePanel state="loading" title="Caricamento" message="Recupero l'asta a rilanci…" testId="auction-live-loading" />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel state="error" title="Errore" message={loadError} testId="auction-live-error" />
      ) : null}

      {!loading && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Scegli una lega dal selettore in alto."
          testId="auction-live-no-league"
        />
      ) : null}

      {!loading && !loadError && activeLeagueId ? (
        <div data-testid="wireframe-auction-live-success" className="fa-auction-live-page">
          {canManageSession && !currentSession ? (
            <WireframeSection label="Crea sessione asta a rilanci" testId="auction-live-create">
              <form data-testid="auction-live-create-form" onSubmit={handleCreateSession}>
                <Input label="Apertura" name="opens-at" type="datetime-local" value={opensAt} onChange={(e) => setOpensAt(e.target.value)} required />
                <Input label="Chiusura" name="closes-at" type="datetime-local" value={closesAt} onChange={(e) => setClosesAt(e.target.value)} required />
                <Select
                  label="Modalità di chiamata"
                  name="nomination-mode"
                  hint={NOMINATION_MODE_HINT[nominationMode]}
                  value={nominationMode}
                  onChange={(e) => setNominationMode(e.target.value as MarketLiveNominationMode)}
                  options={NOMINATION_MODE_OPTIONS}
                />
                <Input label="Incremento minimo (crediti)" name="min-increment" type="number" min={1} value={minIncrement} onChange={(e) => setMinIncrement(e.target.value)} />
                <Input label="Soft-close (secondi)" name="soft-close" type="number" min={5} max={120} value={softClose} onChange={(e) => setSoftClose(e.target.value)} />
                <Input label="Durata lotto (secondi)" name="lot-duration" type="number" min={10} max={300} value={lotDuration} onChange={(e) => setLotDuration(e.target.value)} />
                <Select
                  label="Delegato (opzionale)"
                  name="operator-user-id"
                  value={operatorUserId}
                  onChange={(e) => setOperatorUserId(e.target.value)}
                  placeholder="Nessun delegato — solo admin"
                  options={members.map((row) => ({ value: row.userId, label: row.displayName }))}
                />
                {nominationMode === "sequential" ? (
                  <fieldset data-testid="auction-live-queue-picker">
                    <legend>Lista di chiamata (in ordine di selezione)</legend>
                    {freeAgents.map((entry) => {
                      const owned = ownedAthleteIds.has(entry.athleteId);
                      return (
                        <label key={entry.athleteId} style={{ display: "block", opacity: owned ? 0.5 : 1 }}>
                          <input
                            type="checkbox"
                            disabled={owned}
                            checked={queueAthleteIds.includes(entry.athleteId)}
                            onChange={() => toggleQueueAthlete(entry.athleteId)}
                          />{" "}
                          {entry.canonicalName}
                          {owned ? " (assegnato)" : ""}
                        </label>
                      );
                    })}
                  </fieldset>
                ) : null}
                {AUTO_QUEUE_MODES.includes(nominationMode) && nominationMode !== "sequential" ? (
                  <UiStatePanel
                    state="empty"
                    title="Lista generata automaticamente"
                    message={NOMINATION_MODE_HINT[nominationMode]}
                    testId="auction-live-auto-queue-hint"
                  />
                ) : null}
                {createError ? (
                  <UiStatePanel state="error" title="Sessione non creata" message={createError} testId="auction-live-create-error" />
                ) : null}
                <Button type="submit" variant="primary" disabled={creating}>
                  {creating ? "Creazione…" : "Crea sessione"}
                </Button>
              </form>
            </WireframeSection>
          ) : null}

          {!canManageSession && !currentSession ? (
            <UiStatePanel
              state="empty"
              title="Nessuna asta a rilanci in corso"
              message="L'amministratore della lega non ha ancora aperto una sessione."
              testId="auction-live-empty"
            />
          ) : null}

          {currentSession ? (
            <WireframeSection label="Sessione asta a rilanci" testId="auction-live-session">
              <p data-testid="auction-live-session-status">
                Stato: <Badge variant={currentSession.status === "open" ? "success" : "neutral"}>{SESSION_STATUS_LABEL[currentSession.status]}</Badge>
                {" · "}Modalità: {NOMINATION_MODE_SHORT_LABEL[currentSession.nominationMode] ?? currentSession.nominationMode}
                {AUTO_QUEUE_MODES.includes(currentSession.nominationMode)
                  ? ` (${currentSession.queueRemaining} rimasti)`
                  : null}
                {currentSession.nominationMode === "turn_based" && currentLot === null
                  ? ` · turno di: ${currentTurnTeamName ?? "—"}`
                  : null}
                {currentSession.pendingSwapCount > 0
                  ? ` · ${currentSession.pendingSwapCount} in attesa di scambio`
                  : null}
                {degraded ? " · aggiornamento in ritardo" : null}
              </p>

              {currentSession.nominationMode === "turn_based" && currentSession.turnOrder.length > 0 ? (
                <p data-testid="auction-live-turn-order" className="fa-field__hint">
                  Ordine di chiamata (estratto a sorte):{" "}
                  {currentSession.turnOrder.map((entry) => entry.fantasyTeamName).join(" → ")}
                </p>
              ) : null}

              {currentSession.status === "open" ? (
                <LiveAuctionTable
                  teams={teams}
                  currentLot={currentLot}
                  secondsRemaining={secondsRemaining}
                  currentTurnTeamId={currentLot === null ? currentTurnTeamId : null}
                />
              ) : null}

              {isOperator && currentSession.status === "scheduled" ? (
                <Button variant="primary" disabled={actionBusy} onClick={handleStart}>
                  Avvia sessione
                </Button>
              ) : null}

              {canNominate && currentSession.status === "open" && !currentLot ? (
                <div className="fa-ds-showcase__row" data-testid="auction-live-nominate">
                  {needsExplicitAthlete ? (
                    <Select
                      label="Calciatore da chiamare"
                      name="manual-athlete"
                      value={manualAthleteId}
                      onChange={(e) => setManualAthleteId(e.target.value)}
                      placeholder="Scegli un giocatore…"
                      options={freeAgents.map((entry) => ({
                        value: entry.athleteId,
                        label: ownedAthleteIds.has(entry.athleteId)
                          ? `${entry.canonicalName} (assegnato)`
                          : entry.canonicalName,
                        disabled: ownedAthleteIds.has(entry.athleteId),
                      }))}
                    />
                  ) : null}
                  <Button
                    variant="primary"
                    disabled={actionBusy || (needsExplicitAthlete && !manualAthleteId)}
                    onClick={handleNominate}
                  >
                    Chiama
                  </Button>
                </div>
              ) : null}

              {!canNominate &&
              !isOperator &&
              currentSession.nominationMode === "turn_based" &&
              currentSession.status === "open" &&
              !currentLot ? (
                <UiStatePanel
                  state="empty"
                  title="In attesa del tuo turno"
                  message={`Tocca a ${currentTurnTeamName ?? "un altro fantallenatore"}: aspetta il tuo turno per chiamare un calciatore.`}
                  testId="auction-live-waiting-turn"
                />
              ) : null}

              {isOperator && currentSession.status === "open" && !currentLot ? (
                <Button variant="secondary" disabled={actionBusy} onClick={handleEnd}>
                  Termina sessione
                </Button>
              ) : null}

              {actionMessage ? <UiStatePanel state="success" title="Fatto" message={actionMessage} testId="auction-live-action-ok" /> : null}
              {actionError ? <UiStatePanel state="error" title="Operazione non riuscita" message={actionError} testId="auction-live-action-error" /> : null}

              {currentLot ? (
                <Card data-testid="auction-live-current-lot">
                  <CardHeader title={`Lotto: ${currentLot.athleteName}`} />
                  <CardBody>
                    <p>
                      Prezzo attuale: <strong>{currentLot.currentAmountCredits}</strong> crediti
                      {currentLot.currentLeaderTeamName ? ` · in testa: ${currentLot.currentLeaderTeamName}` : " · nessun rilancio"}
                    </p>
                    {secondsRemaining !== null ? <p data-testid="auction-live-countdown">Tempo residuo: {secondsRemaining}s</p> : null}
                    <p>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</p>

                    <div className="fa-ds-showcase__row">
                      <Button
                        variant="primary"
                        disabled={raiseBusy || minimumNextBid === null}
                        onClick={() => minimumNextBid !== null && handleRaise(minimumNextBid)}
                        data-testid="auction-live-raise-min"
                      >
                        Rilancia a {minimumNextBid ?? "—"}
                      </Button>
                    </div>
                    {raiseError ? <UiStatePanel state="error" title="Rilancio non riuscito" message={raiseError} testId="auction-live-raise-error" /> : null}

                    {isOperator ? (
                      <div className="fa-ds-showcase__row">
                        <Button variant="primary" disabled={actionBusy || !currentLot.currentLeaderTeamId} onClick={handleForceSell}>
                          Aggiudica
                        </Button>
                        <Button variant="secondary" disabled={actionBusy} onClick={handlePass}>
                          Salta
                        </Button>
                        <Button variant="secondary" disabled={actionBusy || !!currentLot.currentLeaderTeamId} onClick={handleCancel}>
                          Annulla
                        </Button>
                      </div>
                    ) : null}

                    {recentRaises.length > 0 ? (
                      <ul data-testid="auction-live-recent-raises">
                        {recentRaises.map((raise) => (
                          <li key={raise.id}>
                            {raise.fantasyTeamName}: {raise.amountCredits} crediti
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </CardBody>
                </Card>
              ) : null}

              {lotHistory.length > 0 ? (
                <div data-testid="auction-live-history">
                  <h3>Storico lotti</h3>
                  <ul>
                    {lotHistory.map((lot) => (
                      <li key={lot.id}>
                        {lot.athleteName}: {LOT_STATUS_LABEL[lot.status]}
                        {lot.status === "sold" ? ` (${lot.currentLeaderTeamName} · ${lot.currentAmountCredits} crediti)` : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </WireframeSection>
          ) : null}
        </div>
      ) : null}

      <Modal
        open={pendingSwap != null}
        onClose={() => setPendingSwap(null)}
        title="Rosa al completo"
        closeLabel="Chiudi"
      >
        {pendingSwap ? (
          <div data-testid="auction-live-swap-modal">
            <p>
              Hai aggiudicato <strong>{pendingSwap.athleteName}</strong> per{" "}
              {pendingSwap.amountCredits} crediti, ma la tua rosa di {pendingSwap.roleLabel} è al
              completo. Scegli chi scambiare, oppure rinuncia al giocatore.
            </p>
            {swapError ? (
              <UiStatePanel state="error" title="Scambio non riuscito" message={swapError} testId="auction-live-swap-error" />
            ) : null}
            <ul data-testid="auction-live-swap-candidates">
              {pendingSwap.candidates.map((candidate) => (
                <li key={candidate.athleteId} className="fa-ds-showcase__row">
                  <span>
                    {candidate.athleteName} ({candidate.purchaseCredits} crediti)
                  </span>
                  <Button
                    variant="primary"
                    disabled={swapBusy}
                    onClick={() => handleResolveSwap(candidate.athleteId)}
                    data-testid={`auction-live-swap-with-${candidate.athleteId}`}
                  >
                    Scambia
                  </Button>
                </li>
              ))}
            </ul>
            <Button
              variant="secondary"
              disabled={swapBusy}
              onClick={handleDeclineSwap}
              data-testid="auction-live-swap-decline"
            >
              Rinuncia al giocatore
            </Button>
          </div>
        ) : null}
      </Modal>
    </>
  );
}
