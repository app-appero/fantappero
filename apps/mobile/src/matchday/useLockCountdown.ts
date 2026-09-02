import type { LineupLockCountdown } from "@fantappero/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchLineupLockCountdown } from "../api/leagues";

const REFRESH_INTERVAL_MS = 90_000;

/**
 * Mobile port of `apps/web/src/matchday/useLockCountdown.ts` (EP-turni-automazione):
 * fetches on mount/league change and every 90s while a lock is actually
 * ticking down, pausing the poll while the app is backgrounded (`AppState`,
 * same adaptation as `useLiveTurnPolling`). `refetch` lets the ticking
 * `LockCountdown` component ask for a fresh value the instant it reaches
 * zero.
 */
export function useLockCountdown(
  accessToken: string | null,
  leagueId: string | null,
): { countdown: LineupLockCountdown | null; refetch: () => void } {
  const [countdown, setCountdown] = useState<LineupLockCountdown | null>(null);
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  const refresh = useCallback(async () => {
    const token = accessTokenRef.current;
    if (!leagueId || !token) {
      setCountdown(null);
      return;
    }
    try {
      const result = await fetchLineupLockCountdown(token, leagueId);
      setCountdown(result);
    } catch {
      // Widget accessorio: un errore non deve rompere la navigazione.
      setCountdown(null);
    }
  }, [leagueId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (countdown?.state !== "counting_down") {
      return;
    }
    const interval = setInterval(() => {
      if (AppState.currentState === "active") {
        void refresh();
      }
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [countdown?.state, refresh]);

  return { countdown, refetch: () => void refresh() };
}
