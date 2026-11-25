import {
  type ReplacementBanner,
  type TradeReplacementStatus,
  replacementBanner,
  replacementPromptStorageKey,
  shouldAutoOpenReplacement,
} from "@fantappero/contracts";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { fetchTradeReplacements } from "../api/market";
import { useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { TradeReplacementModal } from "./TradeReplacementModal";

export type TradeReplacementContextValue = {
  /** I sostituti da scegliere della mia squadra nella lega attiva (`null` finché non si sa). */
  status: TradeReplacementStatus | null;
  /** Il riquadro «Rosa incompleta: 34/35» per Rosa e Formazione, `null` se non manca nessuno. */
  banner: ReplacementBanner | null;
  /** Apre la finestra «Scegli il sostituto». */
  open: () => void;
  /** Rilegge i sostituti (dopo uno scambio accettato o approvato); apre la finestra se `openIfPending`. */
  refresh: (options?: { openIfPending?: boolean }) => Promise<TradeReplacementStatus | null>;
};

const TradeReplacementContext = createContext<TradeReplacementContextValue | null>(null);

function readShown(leagueId: string): boolean {
  try {
    return window.sessionStorage.getItem(replacementPromptStorageKey(leagueId)) === "1";
  } catch {
    return false;
  }
}

function markShown(leagueId: string) {
  try {
    window.sessionStorage.setItem(replacementPromptStorageKey(leagueId), "1");
  } catch {
    // Senza sessionStorage la finestra può riaprirsi a ogni caricamento: nessun danno.
  }
}

/**
 * Sostituto dopo uno scambio sbilanciato (1.5), per tutta l'app della lega attiva: legge i
 * sostituti da scegliere, apre da sola la finestra una volta per sessione (con «Più tardi» non si
 * riapre fino alla sessione dopo; i riquadri in Rosa e Formazione restano) e la apre sempre dal
 * link della notifica (`?sostituto=1`).
 */
export function TradeReplacementProvider({ children }: { children: ReactNode }) {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const enabled = !isDemoMode && Boolean(activeLeagueId) && can(["market:view"]);
  const [status, setStatus] = useState<TradeReplacementStatus | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const leagueRef = useRef(activeLeagueId);
  leagueRef.current = activeLeagueId;

  const load = useCallback(async (): Promise<TradeReplacementStatus | null> => {
    const leagueId = leagueRef.current;
    const stored = loadStoredSession();
    if (!enabled || !leagueId || !stored?.accessToken) {
      return null;
    }
    try {
      const next = await fetchTradeReplacements(stored.accessToken, leagueId);
      if (leagueRef.current !== leagueId) {
        return null;
      }
      const valid = next && Array.isArray(next.pending) ? next : null;
      setStatus(valid);
      return valid;
    } catch {
      // Chi non ha una squadra (operatore) o un backend più vecchio: nessun sostituto.
      if (leagueRef.current === leagueId) {
        setStatus(null);
      }
      return null;
    }
  }, [enabled]);

  useEffect(() => {
    setStatus(null);
    setIsOpen(false);
    if (!enabled || !activeLeagueId) {
      return;
    }
    let cancelled = false;
    void load().then((next) => {
      if (cancelled || !next) {
        return;
      }
      if (shouldAutoOpenReplacement(next, readShown(activeLeagueId))) {
        markShown(activeLeagueId);
        setIsOpen(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activeLeagueId, enabled, load]);

  // Link della notifica «Scegli il sostituto dopo lo scambio» (`/rosa?sostituto=1`).
  const handledSearch = useRef<string | null>(null);
  const fromNotification = new URLSearchParams(search).get("sostituto") === "1";
  useEffect(() => {
    if (!fromNotification || handledSearch.current === search || !enabled) {
      return;
    }
    handledSearch.current = search;
    void load().then((next) => {
      if (next && next.pending.length > 0) {
        if (activeLeagueId) {
          markShown(activeLeagueId);
        }
        setIsOpen(true);
      }
    });
  }, [activeLeagueId, enabled, fromNotification, load, search]);

  const refresh = useCallback(
    async (options?: { openIfPending?: boolean }) => {
      const next = await load();
      if (options?.openIfPending && next && next.pending.length > 0) {
        setIsOpen(true);
      }
      return next;
    },
    [load],
  );

  const value = useMemo<TradeReplacementContextValue>(
    () => ({
      status,
      banner: replacementBanner(status),
      open: () => setIsOpen(true),
      refresh,
    }),
    [refresh, status],
  );

  return (
    <TradeReplacementContext.Provider value={value}>
      {children}
      <TradeReplacementModal
        open={isOpen && Boolean(status && status.pending.length > 0)}
        leagueId={activeLeagueId}
        status={status}
        onClose={() => setIsOpen(false)}
        onStatusChange={setStatus}
      />
    </TradeReplacementContext.Provider>
  );
}

const FALLBACK: TradeReplacementContextValue = {
  status: null,
  banner: null,
  open: () => undefined,
  refresh: async () => null,
};

export function useTradeReplacement(): TradeReplacementContextValue {
  return useContext(TradeReplacementContext) ?? FALLBACK;
}
