import type { FantasyTurnDetail } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchFantasyTurn } from "../api/leagues";

const BASE_INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 120_000;

function isRoundLive(detail: FantasyTurnDetail): boolean {
  if (detail.homologationStatus === "homologated") {
    return false;
  }
  return detail.effectiveStatus === "open" || detail.effectiveStatus === "locked";
}

/**
 * Mobile port of `apps/web/src/matchday/useLiveTurnPolling.ts`: polls a fantasy turn's
 * detail while it is live (open/locked, not yet homologated), stopping once the round is
 * final.
 *
 * Same adaptation as `useLiveH2HPolling`/`useLiveMatchupPolling`: the access token is
 * passed in (reactive session) instead of read from `loadStoredSession()`, and polling
 * pauses while the app is backgrounded via `AppState`.
 */
export function useLiveTurnPolling(
  accessToken: string | null,
  leagueId: string | null,
  turn: FantasyTurnDetail | null,
  onUpdate: (detail: FantasyTurnDetail) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  const turnId = turn?.id ?? null;
  const shouldPoll = enabled && !!accessToken && !!leagueId && !!turn && isRoundLive(turn);

  useEffect(() => {
    if (!shouldPoll || !leagueId || !turnId) {
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
        const detail = await fetchFantasyTurn(token, leagueId as string, turnId as string);
        if (cancelled) {
          return;
        }
        intervalMs = BASE_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(detail);
        if (!isRoundLive(detail)) {
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
  }, [shouldPoll, leagueId, turnId]);

  return { degraded };
}
