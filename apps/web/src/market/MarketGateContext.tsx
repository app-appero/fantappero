import {
  isMarketActive,
  isMarketOpen,
  marketNotFullNotice,
  marketSwitchLocked,
  type MarketGate,
} from "@fantappero/contracts";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { fetchMarketGate, setMarketGate } from "../api/market";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";

export type MarketGateContextValue = {
  /** Interruttore dell'amministratore. */
  marketOpen: boolean;
  /**
   * Interruttore acceso e lega al completo (decisione del 20/11): rosa, aste e scambi del
   * partecipante. Le operazioni dell'amministratore sulle rose non dipendono né da questo
   * né dall'interruttore: si fermano solo a turno in corso.
   */
  marketActive: boolean;
  /** `false` finché non sono occupati tutti i posti della lega. */
  leagueFull: boolean;
  /** «Il mercato si apre quando la lega è al completo (5/8).», o `null` a lega al completo. */
  notFullNotice: string | null;
  /** A lega incompleta l'interruttore spento non si accende (spegnerlo resta possibile). */
  switchLocked: boolean;
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

/** Stato demo «lega non al completo» (`?mercato=incompleto`): 5 iscritti su 8. */
const DEMO_NOT_FULL_GATE: MarketGate = {
  marketOpen: false,
  memberCount: 5,
  participantCount: 8,
  leagueFull: false,
  marketBlockedReason: "league_not_full",
};

function demoGateFromSearch(search: string): MarketGate | null {
  return new URLSearchParams(search).get("mercato") === "incompleto" ? DEMO_NOT_FULL_GATE : null;
}

export function MarketGateProvider({
  children,
  reloadToken = 0,
}: {
  children: ReactNode;
  /** Cambia quando gli iscritti cambiano (es. Amministrazione lega): rilegge lo stato. */
  reloadToken?: number;
}) {
  const { isDemoMode, activeLeagueId, activeLeague, can, patchLeague } = useAuth();
  const { search } = useLocation();
  const canManage = can(["market:manage"]);
  const demoGate = isDemoMode ? demoGateFromSearch(search) : null;
  const [gate, setGate] = useState<MarketGate>(
    () => demoGate ?? { marketOpen: isMarketOpen(activeLeague) },
  );
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lastLeagueIdRef = useRef(activeLeagueId);
  useEffect(() => {
    if (lastLeagueIdRef.current === activeLeagueId) {
      return;
    }
    lastLeagueIdRef.current = activeLeagueId;
    setGate({ marketOpen: isMarketOpen(activeLeague) });
  }, [activeLeague, activeLeagueId]);

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
      .then((next) => {
        if (cancelled) {
          return;
        }
        setGate(next);
        patchLeague(activeLeagueId, { marketOpen: next.marketOpen });
      })
      .catch(() => {
        // Keep the last known value from the league summary.
      });
    return () => {
      cancelled = true;
    };
  }, [activeLeagueId, isDemoMode, patchLeague, reloadToken]);

  const setOpen = useCallback(
    async (open: boolean) => {
      if (!canManage) {
        return;
      }
      if (isDemoMode) {
        setGate((current) => ({ ...current, marketOpen: open }));
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
        const next = await setMarketGate(stored.accessToken, activeLeagueId, { open });
        setGate(next);
        patchLeague(activeLeagueId, { marketOpen: next.marketOpen });
      } catch (cause) {
        setError(getApiErrorMessage(cause, "Impossibile aggiornare lo stato del mercato."));
      } finally {
        setToggling(false);
      }
    },
    [activeLeagueId, canManage, isDemoMode, patchLeague],
  );

  const value = useMemo<MarketGateContextValue>(
    () => ({
      marketOpen: gate.marketOpen,
      marketActive: isMarketActive(gate),
      leagueFull: gate.leagueFull !== false,
      notFullNotice: marketNotFullNotice(gate),
      switchLocked: marketSwitchLocked(gate),
      canManage,
      toggling,
      error,
      setOpen,
    }),
    [canManage, error, gate, setOpen, toggling],
  );

  return <MarketGateContext.Provider value={value}>{children}</MarketGateContext.Provider>;
}

export function useMarketGate(): MarketGateContextValue {
  const context = useContext(MarketGateContext);
  if (!context) {
    return {
      marketOpen: true,
      marketActive: true,
      leagueFull: true,
      notFullNotice: null,
      switchLocked: false,
      canManage: false,
      toggling: false,
      error: null,
      setOpen: async () => undefined,
    };
  }
  return context;
}
