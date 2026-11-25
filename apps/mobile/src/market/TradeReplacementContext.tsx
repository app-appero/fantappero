import {
  type ReplacementBanner,
  type TradeReplacementPurchase,
  type TradeReplacementStatus,
  replacementBanner,
  replacementPurchasedMessage,
  shouldAutoOpenReplacement,
} from "@fantappero/contracts";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { fetchTradeReplacements } from "../api/market";
import { useAuthSession } from "../session/DemoSessionContext";
import { TradeReplacementSheet } from "./TradeReplacementSheet";
import { markReplacementPromptShown, replacementPromptShown } from "./tradeReplacementPrompt";

export type TradeReplacementContextValue = {
  /** I sostituti da scegliere della mia squadra nella lega attiva (`null` finché non si sa). */
  status: TradeReplacementStatus | null;
  /** Il riquadro «Rosa incompleta: 34/35» per Rosa e Formazione, `null` se non manca nessuno. */
  banner: ReplacementBanner | null;
  /** Apre il foglio «Scegli il sostituto». */
  open: () => void;
  /** Rilegge i sostituti (dopo uno scambio accettato o approvato); apre il foglio se `openIfPending`. */
  refresh: (options?: { openIfPending?: boolean }) => Promise<TradeReplacementStatus | null>;
  /** Cresce a ogni sostituto comprato: Rosa e Formazione si rileggono. */
  purchaseCount: number;
};

const TradeReplacementContext = createContext<TradeReplacementContextValue | null>(null);

/**
 * Sostituto dopo uno scambio sbilanciato (1.5) per tutte le schede della lega attiva: legge i
 * sostituti da scegliere e apre da solo il foglio una volta per sessione dell'app (con «Più tardi»
 * non si riapre fino al prossimo avvio; i riquadri in Rosa e Formazione restano).
 */
export function TradeReplacementProvider({ children }: { children: ReactNode }) {
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const enabled = Boolean(accessToken && activeLeagueId) && can(["market:view"]);
  const [status, setStatus] = useState<TradeReplacementStatus | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [purchaseCount, setPurchaseCount] = useState(0);
  const leagueRef = useRef(activeLeagueId);
  leagueRef.current = activeLeagueId;

  const load = useCallback(async (): Promise<TradeReplacementStatus | null> => {
    const leagueId = leagueRef.current;
    if (!enabled || !accessToken || !leagueId) {
      return null;
    }
    try {
      const next = await fetchTradeReplacements(accessToken, leagueId);
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
  }, [accessToken, enabled]);

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
      if (shouldAutoOpenReplacement(next, replacementPromptShown(activeLeagueId))) {
        markReplacementPromptShown(activeLeagueId);
        setIsOpen(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activeLeagueId, enabled, load]);

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

  const onPurchased = useCallback((purchase: TradeReplacementPurchase) => {
    setStatus(purchase.status);
    setPurchaseCount((value) => value + 1);
    if (purchase.status.pending.length === 0) {
      setIsOpen(false);
    }
    Alert.alert("Sostituto preso", replacementPurchasedMessage(purchase));
  }, []);

  const value = useMemo<TradeReplacementContextValue>(
    () => ({
      status,
      banner: replacementBanner(status),
      open: () => setIsOpen(true),
      refresh,
      purchaseCount,
    }),
    [purchaseCount, refresh, status],
  );

  return (
    <TradeReplacementContext.Provider value={value}>
      {children}
      <TradeReplacementSheet
        visible={isOpen && Boolean(status && status.pending.length > 0)}
        accessToken={accessToken}
        leagueId={activeLeagueId}
        status={status}
        onClose={() => setIsOpen(false)}
        onPurchased={onPurchased}
      />
    </TradeReplacementContext.Provider>
  );
}

const FALLBACK: TradeReplacementContextValue = {
  status: null,
  banner: null,
  open: () => undefined,
  refresh: async () => null,
  purchaseCount: 0,
};

export function useTradeReplacement(): TradeReplacementContextValue {
  return useContext(TradeReplacementContext) ?? FALLBACK;
}
