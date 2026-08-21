import type { H2HCalendar } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { fetchH2HCalendar } from "../api/leagues";
import { loadStoredSession } from "../auth/sessionStorage";

const BASE_INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 120_000;

/**
 * Polls the H2H calendar aggregate while any linked european turn is live
 * (open/locked, not homologated). Same backoff pattern as useLiveTurnPolling.
 */
export function useLiveH2HPolling(
  leagueId: string | null,
  calendar: H2HCalendar | null,
  onUpdate: (next: H2HCalendar | null) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const shouldPoll = enabled && !!leagueId && !!calendar?.live;

  useEffect(() => {
    if (!shouldPoll || !leagueId) {
      setDegraded(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let intervalMs = BASE_INTERVAL_MS;

    async function tick() {
      const session = loadStoredSession();
      if (!session?.accessToken) {
        return;
      }
      try {
        const next = await fetchH2HCalendar(session.accessToken, leagueId as string);
        if (cancelled) {
          return;
        }
        intervalMs = BASE_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(next);
        if (!next?.live) {
          return;
        }
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
      clearTimeout(timer);
    };
  }, [shouldPoll, leagueId]);

  return { degraded };
}
