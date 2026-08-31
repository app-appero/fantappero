import type { H2HCalendar } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchH2HCalendar } from "../api/leagues";

const BASE_INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 120_000;

/**
 * Mobile port of `apps/web/src/matchday/useLiveH2HPolling.ts`: polls the H2H calendar
 * aggregate while any linked european turn is live (open/locked, not homologated).
 *
 * The web hook reads the access token from `loadStoredSession()` on every tick; on
 * mobile the session is reactive (`useAuthSession`), so the token is passed in and kept
 * fresh via a ref instead. It also checks `AppState` so polling pauses while the app is
 * backgrounded (there is no browser-tab equivalent on the web side to mirror).
 */
export function useLiveH2HPolling(
  accessToken: string | null,
  leagueId: string | null,
  calendar: H2HCalendar | null,
  onUpdate: (next: H2HCalendar | null) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  const monitoring = calendar?.rounds.some(
    (round) =>
      round.homologationStatus !== "homologated" &&
      (round.europeanTurnStatus === "open" || round.europeanTurnStatus === "locked"),
  );
  const shouldPoll = enabled && !!accessToken && !!leagueId && monitoring === true;

  useEffect(() => {
    if (!shouldPoll || !leagueId) {
      setDegraded(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let intervalMs = BASE_INTERVAL_MS;

    async function tick() {
      if (AppState.currentState !== "active") {
        // Backgrounded: skip this tick without penalizing the backoff.
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
        const next = await fetchH2HCalendar(token, leagueId as string);
        if (cancelled) {
          return;
        }
        intervalMs = BASE_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(next);
        const nextMonitoring = next?.rounds.some(
          (round) =>
            round.homologationStatus !== "homologated" &&
            (round.europeanTurnStatus === "open" || round.europeanTurnStatus === "locked"),
        );
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
  }, [shouldPoll, leagueId]);

  return { degraded };
}
