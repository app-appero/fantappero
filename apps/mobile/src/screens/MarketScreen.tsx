import type {
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  MarketReleasePreview,
  MarketReleaseReason,
  RosterOccupancyEntry,
  TeamRosterPlayer,
} from "@fantappero/contracts";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, Text, View } from "react-native";
import {
  fetchFantasyTeams,
  fetchLeagueListone,
  fetchMyCredits,
  fetchMyFantasyTeam,
  fetchRosterOccupancy,
  fetchTeamPlayersForTrade,
} from "../api/leagues";
import { applyVoluntaryRelease, previewVoluntaryRelease } from "../api/market";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { marketUiStyles as styles } from "../market/marketUiStyles";
import { useMarketHistory } from "../market/useMarketHistory";
import { useTradeFlow } from "../market/useTradeFlow";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { MarketHistorySection } from "./market/MarketHistorySection";
import { MarketReleaseSection } from "./market/MarketReleaseSection";
import { MarketTradeCreateForm } from "./market/MarketTradeCreateForm";
import { MarketTradeList } from "./market/MarketTradeList";

/** Mercato: svincolo volontario + proposte di scambio tra squadre (EP08-04/05/06/07/08). */
export function MarketScreen() {
  const { can, accessToken, activeLeagueId } = useAuthSession();
  const canManageMarket = can(["market:manage"]);

  const [team, setTeam] = useState<FantasyTeam | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [teams, setTeams] = useState<FantasyTeamSummary[]>([]);
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>([]);
  const [listoneEntries, setListoneEntries] = useState<LeagueListoneEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadTeam = useCallback(async () => {
    if (!activeLeagueId) {
      setLoading(false);
      setTeam(null);
      setLoadError(null);
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
      const [myTeam, credits, allTeams, allOccupancy, listone] = await Promise.all([
        fetchMyFantasyTeam(accessToken, activeLeagueId),
        fetchMyCredits(accessToken, activeLeagueId).catch(() => null),
        fetchFantasyTeams(accessToken, activeLeagueId).catch(() => []),
        fetchRosterOccupancy(accessToken, activeLeagueId).catch(() => []),
        fetchLeagueListone(accessToken, activeLeagueId).catch(() => []),
      ]);
      setTeam(myTeam);
      if (credits) {
        setBalance(credits.balance);
      }
      setTeams(allTeams);
      setOccupancy(allOccupancy);
      setListoneEntries(listone);
    } catch (error) {
      setTeam(null);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la rosa."));
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId]);

  const { refreshing, onRefresh } = useScreenData(loadTeam);

  const athleteNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of listoneEntries) {
      map.set(entry.athleteId, entry.canonicalName);
    }
    return map;
  }, [listoneEntries]);

  const otherTeams = useMemo(() => teams.filter((row) => row.id !== team?.id), [teams, team]);

  const trade = useTradeFlow({ leagueId: activeLeagueId, accessToken, active: true });
  const history = useMarketHistory({ leagueId: activeLeagueId, accessToken, active: true });

  const ownedSlots = useMemo(
    () => (team?.slots ?? []).filter((slot) => slot.athleteId !== null),
    [team],
  );

  const slotOptions = useMemo(
    () =>
      ownedSlots.map((slot) => ({
        value: String(slot.slotIndex),
        label: `${slot.athleteName} (${slot.purchaseCredits ?? 0} crediti)`,
      })),
    [ownedSlots],
  );

  // -- Svincolo volontario (EP08-04) -------------------------------------------

  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [reason, setReason] = useState<MarketReleaseReason>("voluntary");
  const [preview, setPreview] = useState<MarketReleasePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applySuccess, setApplySuccess] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  async function handlePreview() {
    if (!activeLeagueId || selectedSlotIndex === "") {
      return;
    }
    if (!accessToken) {
      setPreviewError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    setApplySuccess(null);
    try {
      const result = await previewVoluntaryRelease(
        accessToken,
        activeLeagueId,
        Number(selectedSlotIndex),
        reason,
      );
      setPreview(result);
    } catch (error) {
      setPreviewError(getApiErrorMessage(error, "Impossibile calcolare il rimborso."));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleApply() {
    if (!activeLeagueId || selectedSlotIndex === "") {
      return;
    }
    if (!accessToken) {
      setApplyError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setApplying(true);
    setApplyError(null);
    try {
      const result = await applyVoluntaryRelease(
        accessToken,
        activeLeagueId,
        Number(selectedSlotIndex),
        reason,
      );
      setBalance(result.balance);
      setApplySuccess(`${result.athleteName} svincolato: rimborsati ${result.refundCredits} crediti.`);
      setPreview(null);
      setSelectedSlotIndex("");
      await loadTeam();
    } catch (error) {
      setApplyError(getApiErrorMessage(error, "Impossibile completare lo svincolo."));
    } finally {
      setApplying(false);
    }
  }

  // -- Scambi tra partecipanti (EP08-05/06) ------------------------------------

  const [recipientTeamId, setRecipientTeamId] = useState("");
  const [recipientPlayers, setRecipientPlayers] = useState<TeamRosterPlayer[]>([]);
  const [recipientRosterLoading, setRecipientRosterLoading] = useState(false);
  const [recipientRosterError, setRecipientRosterError] = useState<string | null>(null);
  const [offeredAthleteIds, setOfferedAthleteIds] = useState<string[]>([]);
  const [requestedAthleteIds, setRequestedAthleteIds] = useState<string[]>([]);
  const [offeredCredits, setOfferedCredits] = useState("0");
  const [requestedCredits, setRequestedCredits] = useState("0");
  const [expiresAt, setExpiresAt] = useState("");

  const recipientOptions = useMemo(
    () => otherTeams.map((row) => ({ value: row.id, label: row.name })),
    [otherTeams],
  );

  const loadRecipientRoster = useCallback(
    async (teamId: string) => {
      if (!teamId || !activeLeagueId) {
        setRecipientPlayers([]);
        setRecipientRosterLoading(false);
        setRecipientRosterError(null);
        return;
      }
      if (!accessToken) {
        setRecipientPlayers([]);
        setRecipientRosterError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setRecipientRosterLoading(true);
      setRecipientRosterError(null);
      try {
        const players = await fetchTeamPlayersForTrade(accessToken, activeLeagueId, teamId);
        setRecipientPlayers(players);
      } catch (error) {
        setRecipientPlayers([]);
        setRecipientRosterError(
          getApiErrorMessage(error, "Impossibile caricare la rosa della squadra selezionata."),
        );
      } finally {
        setRecipientRosterLoading(false);
      }
    },
    [accessToken, activeLeagueId],
  );

  function handleRecipientTeamIdChange(nextId: string) {
    setRecipientTeamId(nextId);
    setRequestedAthleteIds([]);
    void loadRecipientRoster(nextId);
  }

  function toggleAthleteId(list: string[], id: string): string[] {
    return list.includes(id) ? list.filter((row) => row !== id) : [...list, id];
  }

  function resetTradeForm() {
    setRecipientTeamId("");
    setRecipientPlayers([]);
    setRecipientRosterError(null);
    setOfferedAthleteIds([]);
    setRequestedAthleteIds([]);
    setOfferedCredits("0");
    setRequestedCredits("0");
    setExpiresAt("");
  }

  function handleCreateProposal() {
    if (!recipientTeamId || !expiresAt.trim()) {
      return;
    }
    const parsed = new Date(expiresAt.trim().replace(" ", "T"));
    if (Number.isNaN(parsed.getTime())) {
      return;
    }
    void trade
      .createProposal({
        recipientTeamId,
        offeredAthleteIds,
        requestedAthleteIds,
        offeredCredits: Number(offeredCredits) || 0,
        requestedCredits: Number(requestedCredits) || 0,
        expiresAt: parsed.toISOString(),
      })
      .then(resetTradeForm);
  }

  useEffect(() => {
    if (!recipientTeamId) {
      return;
    }
    // Re-fetch if the active league changes while a recipient is selected.
    void loadRecipientRoster(recipientTeamId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLeagueId]);

  return (
    <PageContainer title="Mercato" testID="screen-market" refreshing={refreshing} onRefresh={onRefresh}>
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento"
          message="Recupero la tua rosa…"
          testID="wireframe-market-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <View style={styles.field}>
          <UiStatePanel
            state="error"
            title="Rosa non disponibile"
            message={loadError}
            testID="wireframe-market-error"
          />
          <Pressable style={styles.secondaryButton} onPress={() => void loadTeam()} testID="market-reload">
            <Text style={styles.secondaryButtonLabel}>Ricarica</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Scegli una lega per accedere al mercato."
          testID="wireframe-market-no-league"
        />
      ) : null}

      {!loading && !loadError && activeLeagueId ? (
        <MarketReleaseSection
          ownedSlots={ownedSlots}
          balance={balance}
          slotOptions={slotOptions}
          selectedSlotIndex={selectedSlotIndex}
          onSelectedSlotIndexChange={(value) => {
            setSelectedSlotIndex(value);
            setPreview(null);
            setApplySuccess(null);
          }}
          reason={reason}
          onReasonChange={(value) => {
            setReason(value);
            setPreview(null);
          }}
          onPreview={() => void handlePreview()}
          onApply={() => void handleApply()}
          previewLoading={previewLoading}
          applying={applying}
          preview={preview}
          previewError={previewError}
          applyError={applyError}
          applySuccess={applySuccess}
        />
      ) : null}

      {!loading && !loadError && activeLeagueId ? (
        <MarketTradeCreateForm
          recipientOptions={recipientOptions}
          recipientTeamId={recipientTeamId}
          onRecipientTeamIdChange={handleRecipientTeamIdChange}
          ownedSlots={ownedSlots}
          offeredAthleteIds={offeredAthleteIds}
          onToggleOffered={(id) => setOfferedAthleteIds((prev) => toggleAthleteId(prev, id))}
          recipientPlayers={recipientPlayers}
          recipientRosterLoading={recipientRosterLoading}
          recipientRosterError={recipientRosterError}
          onRetryRecipientRoster={() => void loadRecipientRoster(recipientTeamId)}
          requestedAthleteIds={requestedAthleteIds}
          onToggleRequested={(id) => setRequestedAthleteIds((prev) => toggleAthleteId(prev, id))}
          offeredCredits={offeredCredits}
          onOfferedCreditsChange={setOfferedCredits}
          requestedCredits={requestedCredits}
          onRequestedCreditsChange={setRequestedCredits}
          expiresAt={expiresAt}
          onExpiresAtChange={setExpiresAt}
          createError={trade.createError}
          creating={trade.creating}
          onSubmit={handleCreateProposal}
        />
      ) : null}

      {activeLeagueId ? (
        <MarketTradeList
          trade={trade}
          selfTeamId={team?.id}
          teams={teams}
          occupancy={occupancy}
          athleteNameById={athleteNameById}
          ownedSlots={ownedSlots}
          canManageMarket={canManageMarket}
        />
      ) : null}

      {activeLeagueId ? <MarketHistorySection history={history} teams={teams} /> : null}
    </PageContainer>
  );
}
