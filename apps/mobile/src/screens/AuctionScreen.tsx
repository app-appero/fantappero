import type { LeagueListoneEntry } from "@fantappero/contracts";
import { useCallback, useMemo, useState } from "react";
import { fetchLeagueListone, fetchMyCredits } from "../api/leagues";
import {
  closeAuctionSession,
  createAuctionSession,
  fetchAuctionSessions,
  fetchMyAuctionBids,
  resolveAuctionSession,
  submitAuctionBid,
  withdrawAuctionBid,
} from "../api/market";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { parseLocalDateTimeInput } from "../market/dateTimeInput";
import { useMarketSessionFlow } from "../market/useMarketSessionFlow";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { AuctionAdminPanel } from "./auction/AuctionAdminPanel";
import { AuctionBidPanel } from "./auction/AuctionBidPanel";
import { AuctionListone } from "./auction/AuctionListone";
import type { RoleTab } from "./auction/auctionListoneHelpers";

/** Asta a buste chiuse: gestione sessione admin, offerte e listone ufficiale (EP08-01/02). */
export function AuctionScreen() {
  const { can, accessToken, activeLeagueId, activeLeague } = useAuthSession();
  const canManageSession = can(["market:manage"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>([]);
  const [tab, setTab] = useState<RoleTab>("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);

  const loadListone = useCallback(async () => {
    if (!activeLeagueId) {
      setLoading(false);
      setEntries([]);
      setLoadError(null);
      return;
    }
    if (!accessToken) {
      setLoading(false);
      setEntries([]);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [rows, credits] = await Promise.all([
        fetchLeagueListone(accessToken, activeLeagueId),
        fetchMyCredits(accessToken, activeLeagueId).catch(() => null),
      ]);
      setEntries(rows);
      if (credits) {
        setBalance(credits.balance);
      }
    } catch (error) {
      setEntries([]);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare il listone."));
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId]);

  const { refreshing, onRefresh } = useScreenData(loadListone);

  const flow = useMarketSessionFlow(
    {
      fetchSessions: fetchAuctionSessions,
      createSession: createAuctionSession,
      closeSession: closeAuctionSession,
      resolveSession: resolveAuctionSession,
      submitBid: submitAuctionBid,
      withdrawBid: withdrawAuctionBid,
      fetchMyBids: fetchMyAuctionBids,
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

  function handleSubmitBid() {
    const amount = Number(bidAmount);
    if (!bidAthleteId || !Number.isFinite(amount) || amount <= 0) {
      return;
    }
    void flow.submitBid(bidAthleteId, { amountCredits: amount }).then(() => {
      setBidAthleteId("");
      setBidAmount("");
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
    <PageContainer
      title="Asta"
      testID="screen-auction"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {canManageSession ? (
        <AuctionAdminPanel
          flow={flow}
          opensAt={opensAt}
          onOpensAtChange={setOpensAt}
          closesAt={closesAt}
          onClosesAtChange={setClosesAt}
          onCreateSession={handleCreateSession}
          formError={sessionFormError}
          closeLabel="Chiudi asta"
          resolveLabel="Risolvi asta"
          emptyTitle="Nessuna sessione d'asta"
          emptyMessage="Crea la finestra d'asta a buste chiuse per iniziare."
          testIdPrefix="auction"
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
        testIdPrefix="auction"
      />

      <AuctionListone
        entries={entries}
        loading={loading}
        loadError={loadError}
        onRetry={() => void loadListone()}
        activeLeagueId={activeLeagueId}
        activeLeague={activeLeague}
        tab={tab}
        onTabChange={setTab}
      />
    </PageContainer>
  );
}
