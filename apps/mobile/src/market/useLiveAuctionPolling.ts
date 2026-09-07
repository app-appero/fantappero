import type { LiveLotState } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchLiveAuctionState } from "../api/marketLive";

const POLL_INTERVAL_MS = 2_500;
const MAX_INTERVAL_MS = 15_000;

/**
 * Mobile port of `apps/web/src/market/useLiveAuctionPolling.ts`: polls the
 * live-auction state (~2.5s) while a session is open, pausing while the app
 * is backgrounded via `AppState` (same adaptation as `useLiveFixturePolling`).
 */
export function useLiveAuctionPolling(
  accessToken: string | null,
  leagueId: string | null,
  sessionId: string | null,
  onUpdate: (next: LiveLotState) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  const shouldPoll = enabled && !!accessToken && !!leagueId && !!sessionId;

  useEffect(() => {
    if (!shouldPoll || !leagueId || !sessionId) {
      setDegraded(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let intervalMs = POLL_INTERVAL_MS;

    async function tick() {
      if (AppState.currentState !== "active") {
        if (!cancelled) {
          timer = setTimeout(() => void tick(), intervalMs);
        }
        return;
      }
      const token = accessTokenRef.current;
      if (!token) {
        if (!cancelled) {
          timer = setTimeout(() => void tick(), intervalMs);
        }
        return;
      }
      try {
        const next = await fetchLiveAuctionState(token, leagueId as string, sessionId as string);
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
    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [shouldPoll, leagueId, sessionId]);

  return { degraded };
}
