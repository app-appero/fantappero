import type { LeagueListoneEntry } from "@fantappero/contracts";
import { useCallback, useMemo, useState } from "react";
import { View } from "react-native";
import { fetchLeagueListone, fetchMyCredits, fetchMyFantasyTeam } from "../api/leagues";
import {
  closeWaiverSession,
  createWaiverSession,
  fetchMyWaiverBids,
  fetchWaiverSessions,
  resolveWaiverSession,
  submitWaiverBid,
  withdrawWaiverBid,
} from "../api/market";
import { OptionPicker } from "../components/OptionPicker";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { parseLocalDateTimeInput } from "../market/dateTimeInput";
import { marketUiStyles as styles } from "../market/marketUiStyles";
import { useMarketSessionFlow } from "../market/useMarketSessionFlow";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { AuctionAdminPanel } from "./auction/AuctionAdminPanel";
import { AuctionBidPanel } from "./auction/AuctionBidPanel";

/** Mercato svincolati: asta a buste chiuse con giocatore da tagliare abbinato all'offerta (EP08-03). */
export function WaiverScreen() {
  const { can, accessToken, activeLeagueId } = useAuthSession();
  const canManageSession = can(["market:manage"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [rosterOptions, setRosterOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!activeLeagueId) {
      setLoading(false);
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
      const [listoneRows, credits, myTeam] = await Promise.all([
        fetchLeagueListone(accessToken, activeLeagueId),
        fetchMyCredits(accessToken, activeLeagueId).catch(() => null),
        fetchMyFantasyTeam(accessToken, activeLeagueId).catch(() => null),
      ]);
      setEntries(listoneRows);
      if (credits) {
        setBalance(credits.balance);
      }
      if (myTeam) {
        setRosterOptions(
          myTeam.slots
            .filter((slot) => slot.athleteId !== null)
            .map((slot) => ({
              value: slot.athleteId as string,
              label: slot.athleteName ?? "Giocatore",
            })),
        );
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i dati del mercato svincolati."));
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId]);

  const { refreshing, onRefresh } = useScreenData(loadData);

  const flow = useMarketSessionFlow(
    {
      fetchSessions: fetchWaiverSessions,
      createSession: createWaiverSession,
      closeSession: closeWaiverSession,
      resolveSession: resolveWaiverSession,
      submitBid: submitWaiverBid,
      withdrawBid: withdrawWaiverBid,
      fetchMyBids: fetchMyWaiverBids,
    },
    { leagueId: activeLeagueId, accessToken, active: true },
  );

  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [sessionFormError, setSessionFormError] = useState<string | null>(null);

  function handleCreateSession() {
    const opensAtIso = parseLocalDateTimeInput(opensAt);
    const closesAtIso = parseLocalDateTimeInput(closesAt);
    if (!opensAtIso || !closesAtIso) {
      setSessionFormError("Inserisci date valide nel formato AAAA-MM-GG HH:MM.");
      return;
    }
    setSessionFormError(null);
    void flow.createSession({ opensAt: opensAtIso, closesAt: closesAtIso });
  }

  const [bidAthleteId, setBidAthleteId] = useState("");
  const [bidAmount, setBidAmount] = useState("");
  const [releaseAthleteId, setReleaseAthleteId] = useState("");

  function handleSubmitBid() {
    const amount = Number(bidAmount);
    if (!bidAthleteId || !releaseAthleteId || !Number.isFinite(amount) || amount <= 0) {
      return;
    }
    void flow
      .submitBid(bidAthleteId, { amountCredits: amount, releaseAthleteId })
      .then(() => {
        setBidAthleteId("");
        setBidAmount("");
        setReleaseAthleteId("");
      });
  }

  const playerOptions = useMemo(
    () => entries.map((entry) => ({ value: entry.athleteId, label: entry.canonicalName })),
    [entries],
  );

  const athleteNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of entries) {
      map.set(entry.athleteId, entry.canonicalName);
    }
    return map;
  }, [entries]);

  return (
    <PageContainer title="Svincolati" testID="screen-waiver" refreshing={refreshing} onRefresh={onRefresh}>
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento"
          message="Recupero i dati del mercato svincolati…"
          testID="waiver-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel state="error" title="Dati non disponibili" message={loadError} testID="waiver-load-error" />
      ) : null}

      {!loading && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Scegli una lega per accedere al mercato svincolati."
          testID="waiver-no-league"
        />
      ) : null}

      {!loading && !loadError && activeLeagueId ? (
        <>
          {canManageSession ? (
            <AuctionAdminPanel
              flow={flow}
              opensAt={opensAt}
              onOpensAtChange={setOpensAt}
              closesAt={closesAt}
              onClosesAtChange={setClosesAt}
              onCreateSession={handleCreateSession}
              formError={sessionFormError}
              closeLabel="Chiudi svincolati"
              resolveLabel="Risolvi svincolati"
              emptyTitle="Nessuna sessione svincolati"
              emptyMessage="Crea la finestra svincolati a buste chiuse per iniziare."
              testIdPrefix="waiver"
            />
          ) : null}

          <AuctionBidPanel
            flow={flow}
            balance={balance}
            playerOptions={playerOptions}
            bidAthleteId={bidAthleteId}
            onBidAthleteIdChange={setBidAthleteId}
            bidAmount={bidAmount}
            onBidAmountChange={setBidAmount}
            onSubmit={handleSubmitBid}
            athleteNameById={athleteNameById}
            notOpenMessage="Le offerte si possono inviare solo mentre la sessione è aperta."
            statusMessage="Offerta valida solo se abbinata a un giocatore da svincolare."
            testIdPrefix="waiver"
            extraField={
              <View style={styles.field}>
                <OptionPicker
                  label="Giocatore da svincolare"
                  options={rosterOptions}
                  value={releaseAthleteId}
                  onChange={setReleaseAthleteId}
                  placeholder="Scegli chi tagliare…"
                  testID="waiver-release-athlete"
                />
              </View>
            }
          />
        </>
      ) : null}
    </PageContainer>
  );
}
