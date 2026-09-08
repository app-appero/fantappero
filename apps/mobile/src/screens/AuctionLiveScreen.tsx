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
import { useCallback, useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, Text, TextInput, View } from "react-native";
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
import { OptionPicker } from "../components/OptionPicker";
import { StatusBadge } from "../components/StatusBadge";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { parseLocalDateTimeInput } from "../market/dateTimeInput";
import {
  AUTO_QUEUE_MODES,
  LIVE_LOT_STATUS_LABEL,
  LIVE_SESSION_STATUS_COLOR,
  LIVE_SESSION_STATUS_LABEL,
  NOMINATION_MODE_HINT,
  NOMINATION_MODE_OPTIONS,
  NOMINATION_MODE_SHORT_LABEL,
} from "../market/liveAuctionLabels";
import { marketUiStyles as styles } from "../market/marketUiStyles";
import { useLiveAuctionPolling } from "../market/useLiveAuctionPolling";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { LiveAuctionTable } from "./auction-live/LiveAuctionTable";

/**
 * Asta a rilanci: sessione live, lotti e rilanci collegati alle API reali
 * (EP08-09). Contenuto puro, senza PageContainer/ScreenTabs propri — viene
 * montato dentro la sotto-scheda "Live" di `AuctionHubScreen`.
 */
export function AuctionLiveScreen() {
  const { can, accessToken, activeLeagueId, user } = useAuthSession();
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

  const currentSession = sessions.find((row) => row.status !== "resolved") ?? null;
  const isOperator =
    !!currentSession && !!user && (canManageSession || currentSession.operatorUserId === user.id);
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
    if (!activeLeagueId) {
      setLoading(false);
      setSessions([]);
      return;
    }
    if (!accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [rows, listone, memberRows, teamRows, occupancyRows, credits] = await Promise.all([
        fetchLiveAuctionSessions(accessToken, activeLeagueId),
        fetchLeagueListone(accessToken, activeLeagueId),
        fetchLeagueMembersPublic(accessToken, activeLeagueId),
        fetchFantasyTeams(accessToken, activeLeagueId),
        fetchRosterOccupancy(accessToken, activeLeagueId).catch(() => []),
        fetchMyCredits(accessToken, activeLeagueId).catch(() => null),
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
  }, [accessToken, activeLeagueId]);

  useScreenData(load);

  const loadLots = useCallback(async () => {
    if (!activeLeagueId || !accessToken || !currentSession) {
      setLotHistory([]);
      return;
    }
    try {
      const result = await fetchLiveAuctionLots(accessToken, activeLeagueId, currentSession.id);
      setLotHistory(result.lots);
    } catch {
      // Storico non critico: la vista corrente resta comunque aggiornata dal polling.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeLeagueId, currentSession?.id]);

  useLiveAuctionPolling(
    accessToken,
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
    currentSession?.status === "open",
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

  function toggleQueueAthlete(athleteId: string) {
    setQueueAthleteIds((current) =>
      current.includes(athleteId)
        ? current.filter((id) => id !== athleteId)
        : [...current, athleteId],
    );
  }

  async function handleCreateSession() {
    if (!activeLeagueId || !accessToken) return;
    const opensAtIso = parseLocalDateTimeInput(opensAt);
    const closesAtIso = parseLocalDateTimeInput(closesAt);
    if (!opensAtIso || !closesAtIso) {
      setCreateError("Inserisci date valide nel formato AAAA-MM-GG HH:MM.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createLiveAuctionSession(accessToken, activeLeagueId, {
        opensAt: opensAtIso,
        closesAt: closesAtIso,
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

  // -- azioni operatore --------------------------------------------------------

  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

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
    if (!activeLeagueId || !accessToken || !currentSession) return;
    void runOperatorAction(
      () => startLiveAuctionSession(accessToken, activeLeagueId, currentSession.id),
      "Sessione avviata.",
    );
  }

  function handleEnd() {
    if (!activeLeagueId || !accessToken || !currentSession) return;
    void runOperatorAction(
      () => endLiveAuctionSession(accessToken, activeLeagueId, currentSession.id),
      "Sessione terminata.",
    );
  }

  function handleNominate() {
    if (!activeLeagueId || !accessToken || !currentSession) return;
    void runOperatorAction(async () => {
      const lot = await nominateLiveAuctionLot(accessToken, activeLeagueId, currentSession.id, {
        athleteId: needsExplicitAthlete ? manualAthleteId : null,
      });
      setCurrentLot(lot);
      setManualAthleteId("");
    }, "Calciatore chiamato.");
  }

  function handleForceSell() {
    if (!activeLeagueId || !accessToken || !currentSession || !currentLot) return;
    void runOperatorAction(
      () => forceSellLiveAuctionLot(accessToken, activeLeagueId, currentSession.id, currentLot.id),
      "Lotto aggiudicato.",
    );
  }

  function handlePass() {
    if (!activeLeagueId || !accessToken || !currentSession || !currentLot) return;
    void runOperatorAction(
      () => passLiveAuctionLot(accessToken, activeLeagueId, currentSession.id, currentLot.id),
      "Lotto saltato.",
    );
  }

  function handleCancel() {
    if (!activeLeagueId || !accessToken || !currentSession || !currentLot) return;
    void runOperatorAction(
      () => cancelLiveAuctionLot(accessToken, activeLeagueId, currentSession.id, currentLot.id),
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
    if (!activeLeagueId || !accessToken || !currentSession || !currentLot) return;
    setRaiseBusy(true);
    setRaiseError(null);
    placeLiveAuctionRaise(accessToken, activeLeagueId, currentSession.id, currentLot.id, {
      amountCredits: amount,
    })
      .then((lot) => {
        setCurrentLot(lot);
        return fetchMyCredits(accessToken, activeLeagueId).catch(() => null);
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
    if (!activeLeagueId || !accessToken || !currentSession || !pendingSwap) return;
    setSwapBusy(true);
    setSwapError(null);
    resolveLiveAuctionSwap(accessToken, activeLeagueId, currentSession.id, pendingSwap.lotId, {
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
    if (!activeLeagueId || !accessToken || !currentSession || !pendingSwap) return;
    setSwapBusy(true);
    setSwapError(null);
    declineLiveAuctionSwap(accessToken, activeLeagueId, currentSession.id, pendingSwap.lotId)
      .then(() => {
        setPendingSwap(null);
        return load();
      })
      .catch((error) => setSwapError(getApiErrorMessage(error, "Operazione non riuscita.")))
      .finally(() => setSwapBusy(false));
  }

  const ownedAthleteIds = useMemo(
    () => new Set(occupancy.map((row) => row.athleteId)),
    [occupancy],
  );

  const playerOptions = useMemo(
    () =>
      entries.map((entry) => ({
        value: entry.athleteId,
        label: ownedAthleteIds.has(entry.athleteId)
          ? `${entry.canonicalName} (assegnato)`
          : entry.canonicalName,
        disabled: ownedAthleteIds.has(entry.athleteId),
      })),
    [entries, ownedAthleteIds],
  );
  const memberOptions = useMemo(
    () => members.map((row) => ({ value: row.userId, label: row.displayName })),
    [members],
  );

  return (
    <>
      {loading ? (
        <UiStatePanel state="loading" title="Caricamento" message="Recupero l'asta a rilanci…" testID="auction-live-loading" />
      ) : null}
      {!loading && loadError ? (
        <UiStatePanel state="error" title="Errore" message={loadError} testID="auction-live-error" />
      ) : null}

      {!loading && !loadError && canManageSession && !currentSession ? (
        <View style={styles.section} testID="auction-live-create">
          <Text style={styles.sectionTitle}>Crea sessione asta a rilanci</Text>

          <Text style={styles.fieldLabel}>Apertura (AAAA-MM-GG HH:MM)</Text>
          <TextInput style={styles.input} value={opensAt} onChangeText={setOpensAt} placeholder="2026-09-10 20:00" autoCapitalize="none" autoCorrect={false} testID="auction-live-opens-at" />
          <Text style={styles.fieldLabel}>Chiusura (AAAA-MM-GG HH:MM)</Text>
          <TextInput style={styles.input} value={closesAt} onChangeText={setClosesAt} placeholder="2026-09-10 23:00" autoCapitalize="none" autoCorrect={false} testID="auction-live-closes-at" />

          <Text style={styles.fieldLabel}>Modalità di chiamata</Text>
          <View style={styles.chipRow}>
            {NOMINATION_MODE_OPTIONS.map((option) => (
              <Pressable
                key={option.value}
                style={[styles.chip, nominationMode === option.value && styles.chipActive]}
                onPress={() => setNominationMode(option.value)}
                testID={`auction-live-mode-${option.value}`}
              >
                <Text style={[styles.chipLabel, nominationMode === option.value && styles.chipLabelActive]}>
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
          <Text style={styles.meta} testID="auction-live-mode-hint">
            {NOMINATION_MODE_HINT[nominationMode]}
          </Text>

          <Text style={styles.fieldLabel}>Incremento minimo (crediti)</Text>
          <TextInput style={styles.input} value={minIncrement} onChangeText={setMinIncrement} keyboardType="numeric" testID="auction-live-min-increment" />
          <Text style={styles.fieldLabel}>Soft-close (secondi)</Text>
          <TextInput style={styles.input} value={softClose} onChangeText={setSoftClose} keyboardType="numeric" testID="auction-live-soft-close" />
          <Text style={styles.fieldLabel}>Durata lotto (secondi)</Text>
          <TextInput style={styles.input} value={lotDuration} onChangeText={setLotDuration} keyboardType="numeric" testID="auction-live-lot-duration" />

          <OptionPicker
            label="Delegato (opzionale)"
            options={memberOptions}
            value={operatorUserId}
            onChange={setOperatorUserId}
            placeholder="Nessun delegato — solo admin"
            testID="auction-live-operator"
          />

          {nominationMode === "sequential" ? (
            <View testID="auction-live-queue-picker">
              <Text style={styles.fieldLabel}>Lista di chiamata</Text>
              <View style={styles.chipRow}>
                {entries.map((entry) => {
                  const owned = ownedAthleteIds.has(entry.athleteId);
                  const active = queueAthleteIds.includes(entry.athleteId);
                  return (
                    <Pressable
                      key={entry.athleteId}
                      disabled={owned}
                      style={[styles.chip, active && styles.chipActive, owned && styles.disabled]}
                      onPress={() => toggleQueueAthlete(entry.athleteId)}
                    >
                      <Text style={[styles.chipLabel, active && styles.chipLabelActive]}>
                        {entry.canonicalName}
                        {owned ? " (assegnato)" : ""}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ) : null}

          {createError ? <Text style={styles.error} testID="auction-live-create-error">{createError}</Text> : null}
          <Pressable style={[styles.button, creating && styles.disabled]} disabled={creating} onPress={() => void handleCreateSession()} testID="auction-live-create-submit">
            <Text style={styles.buttonLabel}>{creating ? "Creazione…" : "Crea sessione"}</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !loadError && !canManageSession && !currentSession ? (
        <UiStatePanel
          state="empty"
          title="Nessuna asta a rilanci in corso"
          message="L'amministratore della lega non ha ancora aperto una sessione."
          testID="auction-live-empty"
        />
      ) : null}

      {!loading && !loadError && currentSession ? (
        <View style={styles.section} testID="auction-live-session">
          <View style={styles.rowActions}>
            <StatusBadge
              label={LIVE_SESSION_STATUS_LABEL[currentSession.status]}
              color={LIVE_SESSION_STATUS_COLOR[currentSession.status].background}
              textColor={LIVE_SESSION_STATUS_COLOR[currentSession.status].text}
            />
            <Text style={styles.meta}>
              {NOMINATION_MODE_SHORT_LABEL[currentSession.nominationMode] ?? currentSession.nominationMode}
              {AUTO_QUEUE_MODES.includes(currentSession.nominationMode)
                ? ` (${currentSession.queueRemaining} rimasti)`
                : ""}
              {currentSession.nominationMode === "turn_based" && currentLot === null
                ? ` · turno di: ${currentTurnTeamName ?? "—"}`
                : ""}
              {currentSession.pendingSwapCount > 0
                ? ` · ${currentSession.pendingSwapCount} in attesa di scambio`
                : ""}
            </Text>
          </View>

          {currentSession.nominationMode === "turn_based" && currentSession.turnOrder.length > 0 ? (
            <Text style={styles.meta} testID="auction-live-turn-order">
              Ordine di chiamata (estratto a sorte):{" "}
              {currentSession.turnOrder.map((entry) => entry.fantasyTeamName).join(" → ")}
            </Text>
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
            <Pressable style={[styles.button, actionBusy && styles.disabled]} disabled={actionBusy} onPress={handleStart} testID="auction-live-start">
              <Text style={styles.buttonLabel}>Avvia sessione</Text>
            </Pressable>
          ) : null}

          {canNominate && currentSession.status === "open" && !currentLot ? (
            <View style={styles.field} testID="auction-live-nominate">
              {needsExplicitAthlete ? (
                <OptionPicker
                  label="Calciatore da chiamare"
                  options={playerOptions}
                  value={manualAthleteId}
                  onChange={setManualAthleteId}
                  placeholder="Scegli un giocatore…"
                  searchable
                  testID="auction-live-manual-athlete"
                />
              ) : null}
              <Pressable
                style={[styles.button, (actionBusy || (needsExplicitAthlete && !manualAthleteId)) && styles.disabled]}
                disabled={actionBusy || (needsExplicitAthlete && !manualAthleteId)}
                onPress={handleNominate}
                testID="auction-live-nominate-submit"
              >
                <Text style={styles.buttonLabel}>Chiama</Text>
              </Pressable>
            </View>
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
              testID="auction-live-waiting-turn"
            />
          ) : null}

          {isOperator && currentSession.status === "open" && !currentLot ? (
            <Pressable style={[styles.secondaryButton, actionBusy && styles.disabled]} disabled={actionBusy} onPress={handleEnd} testID="auction-live-end">
              <Text style={styles.secondaryButtonLabel}>Termina sessione</Text>
            </Pressable>
          ) : null}

          {actionMessage ? <UiStatePanel state="success" title="Fatto" message={actionMessage} testID="auction-live-action-ok" /> : null}
          {actionError ? <UiStatePanel state="error" title="Operazione non riuscita" message={actionError} testID="auction-live-action-error" /> : null}


          {currentLot ? (
            <View style={styles.section} testID="auction-live-current-lot">
              <Text style={styles.sectionTitle}>{currentLot.athleteName}</Text>
              <Text style={styles.meta}>
                Prezzo attuale: {currentLot.currentAmountCredits} crediti
                {currentLot.currentLeaderTeamName ? ` · in testa: ${currentLot.currentLeaderTeamName}` : " · nessun rilancio"}
              </Text>
              {secondsRemaining !== null ? <Text style={styles.meta} testID="auction-live-countdown">Tempo residuo: {secondsRemaining}s</Text> : null}
              <Text style={styles.meta}>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</Text>

              <Pressable
                style={[styles.button, (raiseBusy || minimumNextBid === null) && styles.disabled]}
                disabled={raiseBusy || minimumNextBid === null}
                onPress={() => minimumNextBid !== null && handleRaise(minimumNextBid)}
                testID="auction-live-raise-min"
              >
                <Text style={styles.buttonLabel}>Rilancia a {minimumNextBid ?? "—"}</Text>
              </Pressable>
              {raiseError ? <Text style={styles.error} testID="auction-live-raise-error">{raiseError}</Text> : null}

              {isOperator ? (
                <View style={styles.rowActions}>
                  <Pressable style={[styles.button, (actionBusy || !currentLot.currentLeaderTeamId) && styles.disabled]} disabled={actionBusy || !currentLot.currentLeaderTeamId} onPress={handleForceSell} testID="auction-live-force-sell">
                    <Text style={styles.buttonLabel}>Aggiudica</Text>
                  </Pressable>
                  <Pressable style={[styles.secondaryButton, actionBusy && styles.disabled]} disabled={actionBusy} onPress={handlePass} testID="auction-live-pass">
                    <Text style={styles.secondaryButtonLabel}>Salta</Text>
                  </Pressable>
                  <Pressable style={[styles.secondaryButton, (actionBusy || !!currentLot.currentLeaderTeamId) && styles.disabled]} disabled={actionBusy || !!currentLot.currentLeaderTeamId} onPress={handleCancel} testID="auction-live-cancel">
                    <Text style={styles.secondaryButtonLabel}>Annulla</Text>
                  </Pressable>
                </View>
              ) : null}

              {recentRaises.length > 0 ? (
                <View testID="auction-live-recent-raises">
                  {recentRaises.map((raise) => (
                    <Text key={raise.id} style={styles.meta}>
                      {raise.fantasyTeamName}: {raise.amountCredits} crediti
                    </Text>
                  ))}
                </View>
              ) : null}
            </View>
          ) : null}

          {lotHistory.length > 0 ? (
            <View testID="auction-live-history">
              <Text style={styles.sectionTitle}>Storico lotti</Text>
              {lotHistory.map((lot) => (
                <Text key={lot.id} style={styles.meta}>
                  {lot.athleteName}: {LIVE_LOT_STATUS_LABEL[lot.status]}
                  {lot.status === "sold" ? ` (${lot.currentLeaderTeamName} · ${lot.currentAmountCredits} crediti)` : null}
                </Text>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}

      <Modal
        visible={pendingSwap != null}
        transparent
        animationType="fade"
        onRequestClose={() => setPendingSwap(null)}
        testID="auction-live-swap-modal"
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            {pendingSwap ? (
              <ScrollView>
                <Text style={styles.sectionTitle}>Rosa al completo</Text>
                <Text style={styles.meta}>
                  Hai aggiudicato {pendingSwap.athleteName} per {pendingSwap.amountCredits} crediti,
                  ma la tua rosa di {pendingSwap.roleLabel} è al completo. Scegli chi scambiare,
                  oppure rinuncia al giocatore.
                </Text>
                {swapError ? <Text style={styles.error} testID="auction-live-swap-error">{swapError}</Text> : null}
                {pendingSwap.candidates.map((candidate) => (
                  <View key={candidate.athleteId} style={styles.rowActions}>
                    <Text style={styles.meta}>
                      {candidate.athleteName} ({candidate.purchaseCredits} crediti)
                    </Text>
                    <Pressable
                      style={[styles.button, swapBusy && styles.disabled]}
                      disabled={swapBusy}
                      onPress={() => handleResolveSwap(candidate.athleteId)}
                      testID={`auction-live-swap-with-${candidate.athleteId}`}
                    >
                      <Text style={styles.buttonLabel}>Scambia</Text>
                    </Pressable>
                  </View>
                ))}
                <Pressable
                  style={[styles.secondaryButton, swapBusy && styles.disabled]}
                  disabled={swapBusy}
                  onPress={handleDeclineSwap}
                  testID="auction-live-swap-decline"
                >
                  <Text style={styles.secondaryButtonLabel}>Rinuncia al giocatore</Text>
                </Pressable>
              </ScrollView>
            ) : null}
          </View>
        </View>
      </Modal>
    </>
  );
}
