import type { LiveLotState } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { fetchLiveAuctionState } from "../api/marketLive";
import { loadStoredSession } from "../auth/sessionStorage";
import { useRealtimeEvent } from "../realtime/useRealtimeEvent";

const POLL_INTERVAL_MS = 2_500;
const MAX_INTERVAL_MS = 15_000;

/**
 * Polling ogni ~2.5s dello stato dell'asta live (lotto corrente, rilanci
 * recenti, secondi residui) — stesso principio di `useLiveFixturePolling`
 * (setTimeout ricorsivo, pausa a tab nascosta, backoff sugli errori), ma con
 * intervallo fisso più stretto: qui "live" significa davvero in corso adesso,
 * non un'attesa di minuti come per un match reale.
 */
export function useLiveAuctionPolling(
  leagueId: string | null,
  sessionId: string | null,
  onUpdate: (next: LiveLotState) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const shouldPoll = enabled && !!leagueId && !!sessionId;
  const nudge = useRef<(() => void) | null>(null);

  useRealtimeEvent((event) => {
    if (event.type === "market.updated" && event.kind === "auction_live" && event.sessionId === sessionId) {
      nudge.current?.();
    }
  }, shouldPoll);

  useEffect(() => {
    if (!shouldPoll || !leagueId || !sessionId) {
      setDegraded(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let intervalMs = POLL_INTERVAL_MS;

    async function tick() {
      if (typeof document !== "undefined" && document.hidden) {
        timer = setTimeout(() => void tick(), intervalMs);
        return;
      }
      const session = loadStoredSession();
      if (!session?.accessToken) {
        return;
      }
      try {
        const next = await fetchLiveAuctionState(
          session.accessToken,
          leagueId as string,
          sessionId as string,
        );
        if (cancelled) {
          return;
        }
        intervalMs = POLL_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(next);
      } catch {
        if (cancelled) {
          return;
        }
        intervalMs = Math.min(intervalMs * 2, MAX_INTERVAL_MS);
        setDegraded(true);
      }
      if (!cancelled) {
        timer = setTimeout(() => void tick(), intervalMs);
      }
    }

    timer = setTimeout(() => void tick(), intervalMs);
    // Evento in tempo reale: ricarica subito invece di aspettare il giro successivo.
    nudge.current = () => {
      clearTimeout(timer);
      void tick();
    };
    return () => {
      nudge.current = null;
      cancelled = true;
      clearTimeout(timer);
    };
  }, [shouldPoll, leagueId, sessionId]);

  return { degraded };
}
