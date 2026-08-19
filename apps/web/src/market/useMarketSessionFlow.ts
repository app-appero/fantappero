import type {
  CreateMarketSessionRequest,
  MarketBid,
  MarketBidList,
  MarketResolution,
  MarketSession,
  SubmitMarketBidRequest,
} from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

/** Session/bid API bindings shared by the auction (EP08-01/02) and waiver (EP08-03) flows. */
export interface MarketSessionBindings {
  fetchSessions: (accessToken: string, leagueId: string) => Promise<MarketSession[]>;
  createSession: (
    accessToken: string,
    leagueId: string,
    body: CreateMarketSessionRequest,
  ) => Promise<MarketSession>;
  closeSession: (accessToken: string, leagueId: string, sessionId: string) => Promise<MarketSession>;
  resolveSession: (
    accessToken: string,
    leagueId: string,
    sessionId: string,
  ) => Promise<MarketResolution>;
  submitBid: (
    accessToken: string,
    leagueId: string,
    sessionId: string,
    athleteId: string,
    body: SubmitMarketBidRequest,
  ) => Promise<MarketBid>;
  withdrawBid: (
    accessToken: string,
    leagueId: string,
    sessionId: string,
    athleteId: string,
  ) => Promise<void>;
  fetchMyBids: (accessToken: string, leagueId: string, sessionId: string) => Promise<MarketBidList>;
}

export interface UseMarketSessionFlowOptions {
  leagueId: string | null;
  active: boolean;
}

export function useMarketSessionFlow(
  bindings: MarketSessionBindings,
  { leagueId, active }: UseMarketSessionFlowOptions,
) {
  const [sessions, setSessions] = useState<MarketSession[]>([]);
  const [loading, setLoading] = useState(active);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [myBids, setMyBids] = useState<MarketBid[]>([]);
  const [resolution, setResolution] = useState<MarketResolution | null>(null);

  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [sessionActionError, setSessionActionError] = useState<string | null>(null);
  const [sessionActionPending, setSessionActionPending] = useState(false);

  const [bidError, setBidError] = useState<string | null>(null);
  const [bidSubmitting, setBidSubmitting] = useState(false);
  const [bidSuccess, setBidSuccess] = useState<string | null>(null);

  const requireToken = useCallback((): string | null => {
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return null;
    }
    return stored.accessToken;
  }, []);

  const currentSession: MarketSession | null =
    sessions.find((row) => row.status === "open" || row.status === "closed") ??
    sessions[0] ??
    null;

  const loadMyBids = useCallback(
    async (accessToken: string, sessionId: string) => {
      try {
        const result = await bindings.fetchMyBids(accessToken, leagueId ?? "", sessionId);
        setMyBids(result.bids);
      } catch {
        setMyBids([]);
      }
    },
    [bindings, leagueId],
  );

  const loadSessions = useCallback(async () => {
    if (!active || !leagueId) {
      setLoading(false);
      setSessions([]);
      setLoadError(null);
      return;
    }
    const accessToken = requireToken();
    if (!accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const rows = await bindings.fetchSessions(accessToken, leagueId);
      setSessions(rows);
      const candidate = rows.find((row) => row.status === "open" || row.status === "closed") ??
        rows[0] ??
        null;
      if (candidate) {
        await loadMyBids(accessToken, candidate.id);
      } else {
        setMyBids([]);
      }
    } catch (error) {
      setSessions([]);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare le sessioni di mercato."));
    } finally {
      setLoading(false);
    }
  }, [active, bindings, leagueId, loadMyBids, requireToken]);

  useEffect(() => {
    void loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, leagueId]);

  const createSession = useCallback(
    async (body: CreateMarketSessionRequest) => {
      if (!leagueId) {
        return;
      }
      const accessToken = requireToken();
      if (!accessToken) {
        setCreateError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setCreating(true);
      setCreateError(null);
      try {
        await bindings.createSession(accessToken, leagueId, body);
        await loadSessions();
      } catch (error) {
        setCreateError(getApiErrorMessage(error, "Impossibile creare la sessione."));
      } finally {
        setCreating(false);
      }
    },
    [bindings, leagueId, loadSessions, requireToken],
  );

  const closeCurrentSession = useCallback(async () => {
    if (!leagueId || !currentSession) {
      return;
    }
    const accessToken = requireToken();
    if (!accessToken) {
      setSessionActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSessionActionPending(true);
    setSessionActionError(null);
    try {
      await bindings.closeSession(accessToken, leagueId, currentSession.id);
      await loadSessions();
    } catch (error) {
      setSessionActionError(getApiErrorMessage(error, "Impossibile chiudere la sessione."));
    } finally {
      setSessionActionPending(false);
    }
  }, [bindings, currentSession, leagueId, loadSessions, requireToken]);

  const resolveCurrentSession = useCallback(async () => {
    if (!leagueId || !currentSession) {
      return;
    }
    const accessToken = requireToken();
    if (!accessToken) {
      setSessionActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSessionActionPending(true);
    setSessionActionError(null);
    try {
      const result = await bindings.resolveSession(accessToken, leagueId, currentSession.id);
      setResolution(result);
      await loadSessions();
    } catch (error) {
      setSessionActionError(getApiErrorMessage(error, "Impossibile risolvere la sessione."));
    } finally {
      setSessionActionPending(false);
    }
  }, [bindings, currentSession, leagueId, loadSessions, requireToken]);

  const submitBid = useCallback(
    async (athleteId: string, body: SubmitMarketBidRequest) => {
      if (!leagueId || !currentSession) {
        return;
      }
      const accessToken = requireToken();
      if (!accessToken) {
        setBidError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setBidSubmitting(true);
      setBidError(null);
      setBidSuccess(null);
      try {
        await bindings.submitBid(accessToken, leagueId, currentSession.id, athleteId, body);
        setBidSuccess("Offerta inviata.");
        await loadMyBids(accessToken, currentSession.id);
      } catch (error) {
        setBidError(getApiErrorMessage(error, "Impossibile inviare l'offerta."));
      } finally {
        setBidSubmitting(false);
      }
    },
    [bindings, currentSession, leagueId, loadMyBids, requireToken],
  );

  const withdrawBid = useCallback(
    async (athleteId: string) => {
      if (!leagueId || !currentSession) {
        return;
      }
      const accessToken = requireToken();
      if (!accessToken) {
        setBidError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setBidError(null);
      setBidSuccess(null);
      try {
        await bindings.withdrawBid(accessToken, leagueId, currentSession.id, athleteId);
        setBidSuccess("Offerta ritirata.");
        await loadMyBids(accessToken, currentSession.id);
      } catch (error) {
        setBidError(getApiErrorMessage(error, "Impossibile ritirare l'offerta."));
      }
    },
    [bindings, currentSession, leagueId, loadMyBids, requireToken],
  );

  return {
    sessions,
    currentSession,
    loading,
    loadError,
    reload: loadSessions,
    myBids,
    resolution,
    createSession,
    creating,
    createError,
    closeCurrentSession,
    resolveCurrentSession,
    sessionActionPending,
    sessionActionError,
    submitBid,
    withdrawBid,
    bidSubmitting,
    bidError,
    bidSuccess,
  };
}
