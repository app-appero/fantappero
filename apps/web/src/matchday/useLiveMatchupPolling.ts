import type { H2HMatchupDetail } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { fetchH2HMatchup } from "../api/leagues";
import { loadStoredSession } from "../auth/sessionStorage";

const BASE_INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 120_000;

/** Polls matchup detail while the linked european turn is live. */
export function useLiveMatchupPolling(
  leagueId: string | null,
  slotId: string | null,
  detail: H2HMatchupDetail | null,
  onUpdate: (next: H2HMatchupDetail) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const shouldPoll = enabled && !!leagueId && !!slotId && !!detail?.live;

  useEffect(() => {
    if (!shouldPoll || !leagueId || !slotId) {
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
        const next = await fetchH2HMatchup(
          session.accessToken,
          leagueId as string,
          slotId as string,
        );
        if (cancelled) {
          return;
        }
        intervalMs = BASE_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(next);
        if (!next.live) {
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
  }, [shouldPoll, leagueId, slotId]);

  return { degraded };
}
