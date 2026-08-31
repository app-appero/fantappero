import type { H2HMatchupDetail } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchH2HMatchup } from "../api/leagues";

const BASE_INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 120_000;

/**
 * Mobile port of `apps/web/src/matchday/useLiveMatchupPolling.ts`: polls a single H2H
 * matchup detail while the linked european turn is live.
 *
 * Same adaptation as `useLiveH2HPolling`: the access token is passed in (reactive
 * session) instead of read from `loadStoredSession()`, and polling pauses while the
 * app is backgrounded via `AppState`.
 */
export function useLiveMatchupPolling(
  accessToken: string | null,
  leagueId: string | null,
  slotId: string | null,
  detail: H2HMatchupDetail | null,
  onUpdate: (next: H2HMatchupDetail) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  const monitoring =
    detail?.homologationStatus !== "homologated" &&
    (detail?.europeanTurnStatus === "open" || detail?.europeanTurnStatus === "locked");
  const shouldPoll = enabled && !!accessToken && !!leagueId && !!slotId && monitoring;

  useEffect(() => {
    if (!shouldPoll || !leagueId || !slotId) {
      setDegraded(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let intervalMs = BASE_INTERVAL_MS;

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
        const next = await fetchH2HMatchup(token, leagueId as string, slotId as string);
        if (cancelled) {
          return;
        }
        intervalMs = BASE_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(next);
        const nextMonitoring =
          next.homologationStatus !== "homologated" &&
          (next.europeanTurnStatus === "open" || next.europeanTurnStatus === "locked");
        if (!nextMonitoring) {
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
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [shouldPoll, leagueId, slotId]);

  return { degraded };
}
