import type { LineupLockCountdown } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { fetchLineupLockCountdown } from "../api/leagues";
import { loadStoredSession } from "../auth/sessionStorage";

const REFRESH_INTERVAL_MS = 90_000;

/**
 * Fetches the per-team lock countdown for a league (EP-turni-automazione):
 * on mount/league change, on window focus, and every 90s while a lock is
 * actually ticking down. `refetch` lets the ticking `LockCountdown` component
 * ask for a fresh value the instant it reaches zero, instead of waiting up to
 * 90s for the next scheduled poll.
 */
export function useLockCountdown(leagueId: string | null): {
  countdown: LineupLockCountdown | null;
  refetch: () => void;
} {
  const [countdown, setCountdown] = useState<LineupLockCountdown | null>(null);

  const refresh = useCallback(async () => {
    if (!leagueId) {
      setCountdown(null);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setCountdown(null);
      return;
    }
    try {
      const result = await fetchLineupLockCountdown(session.accessToken, leagueId);
      setCountdown(result);
    } catch {
      // Widget accessorio: un errore non deve rompere la navigazione.
      setCountdown(null);
    }
  }, [leagueId]);

  useEffect(() => {
    void refresh();
    if (typeof window === "undefined") {
      return;
    }
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  useEffect(() => {
    if (countdown?.state !== "counting_down") {
      return;
    }
    const interval = setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [countdown?.state, refresh]);

  return { countdown, refetch: () => void refresh() };
}
