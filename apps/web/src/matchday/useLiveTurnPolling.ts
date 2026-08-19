import type { FantasyTurnDetail } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { fetchFantasyTurn } from "../api/leagues";
import { loadStoredSession } from "../auth/sessionStorage";

const BASE_INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 120_000;

function isRoundLive(detail: FantasyTurnDetail): boolean {
  if (detail.homologationStatus === "homologated") {
    return false;
  }
  return detail.effectiveStatus === "open" || detail.effectiveStatus === "locked";
}

/**
 * Polls a fantasy turn's detail while it is live (open/locked, not yet
 * homologated), stopping once the round is final. On repeated failures the
 * interval backs off (up to MAX_INTERVAL_MS) instead of erroring the page —
 * the automatic fallback required by EP09-04 — and recovers to the base
 * interval as soon as a poll succeeds again.
 */
export function useLiveTurnPolling(
  leagueId: string | null,
  turn: FantasyTurnDetail | null,
  onUpdate: (detail: FantasyTurnDetail) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const turnId = turn?.id ?? null;
  const shouldPoll = enabled && !!leagueId && !!turn && isRoundLive(turn);

  useEffect(() => {
    if (!shouldPoll || !leagueId || !turnId) {
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
        const detail = await fetchFantasyTurn(session.accessToken, leagueId as string, turnId as string);
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
      clearTimeout(timer);
    };
  }, [shouldPoll, leagueId, turnId]);

  return { degraded };
}
