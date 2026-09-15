import { isMarketOpen } from "@fantappero/contracts";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchMarketGate, setMarketGate } from "../api/market";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

export type MarketGateContextValue = {
  marketOpen: boolean;
  canManage: boolean;
  toggling: boolean;
  error: string | null;
  setOpen: (open: boolean) => Promise<void>;
};

const MarketGateContext = createContext<MarketGateContextValue | null>(null);

const CLOSED_HINT = "Rosa e asta sono bloccate. Gli scambi restano disponibili.";
const OPEN_HINT = "Rosa e asta sono attive. Gli scambi restano sempre disponibili.";

export function marketGateHint(marketOpen: boolean): string {
  return marketOpen ? OPEN_HINT : CLOSED_HINT;
}

export function MarketGateProvider({ children }: { children: ReactNode }) {
  const { isDemoMode, activeLeagueId, activeLeague, can, patchLeague } = useAuth();
  const canManage = can(["market:manage"]);
  const [marketOpen, setMarketOpen] = useState(() => isMarketOpen(activeLeague));
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMarketOpen(isMarketOpen(activeLeague));
  }, [activeLeague]);

  useEffect(() => {
    if (isDemoMode || !activeLeagueId) {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    let cancelled = false;
    void fetchMarketGate(stored.accessToken, activeLeagueId)
      .then((gate) => {
        if (cancelled) {
          return;
        }
        setMarketOpen(gate.marketOpen);
        patchLeague(activeLeagueId, { marketOpen: gate.marketOpen });
      })
      .catch(() => {
        // Keep the last known value from the league summary.
      });
    return () => {
      cancelled = true;
    };
  }, [activeLeagueId, isDemoMode, patchLeague]);

  const setOpen = useCallback(
    async (open: boolean) => {
      if (!canManage) {
        return;
      }
      if (isDemoMode) {
        setMarketOpen(open);
        if (activeLeagueId) {
          patchLeague(activeLeagueId, { marketOpen: open });
        }
        return;
      }
      if (!activeLeagueId) {
        return;
      }
      const stored = loadStoredSession();
      if (!stored?.accessToken) {
        setError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setToggling(true);
      setError(null);
      try {
        const gate = await setMarketGate(stored.accessToken, activeLeagueId, { open });
        setMarketOpen(gate.marketOpen);
        patchLeague(activeLeagueId, { marketOpen: gate.marketOpen });
      } catch (cause) {
        setError(getApiErrorMessage(cause, "Impossibile aggiornare lo stato del mercato."));
      } finally {
        setToggling(false);
      }
    },
    [activeLeagueId, canManage, isDemoMode, patchLeague],
  );

  const value = useMemo<MarketGateContextValue>(
    () => ({ marketOpen, canManage, toggling, error, setOpen }),
    [canManage, error, marketOpen, setOpen, toggling],
  );

  return <MarketGateContext.Provider value={value}>{children}</MarketGateContext.Provider>;
}

export function useMarketGate(): MarketGateContextValue {
  const context = useContext(MarketGateContext);
  if (!context) {
    return {
      marketOpen: true,
      canManage: false,
      toggling: false,
      error: null,
      setOpen: async () => undefined,
    };
  }
  return context;
}
