import type { FixtureLiveDetail } from "@fantappero/contracts";
import { mapFixtureMatchStatus } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { fetchFixtureLiveDetail } from "../api/leagues";
import { loadStoredSession } from "../auth/sessionStorage";

const BASE_INTERVAL_MS = 30_000;
const MAX_INTERVAL_MS = 60_000;

/**
 * Polls a single fixture's live detail (score, minuto, formazioni, eventi)
 * while the match is actually in corso, stopping as soon as il provider la
 * segna come terminata/rinviata/programmata. Stesso pattern backoff di
 * `useLiveTurnPolling`/`useLiveMatchupPolling`, con intervallo più
 * conservativo (30-60s) perché qui si interroga una singola partita invece
 * dell'intero turno.
 */
export function useLiveFixturePolling(
  leagueId: string | null,
  turnId: string | null,
  fixtureId: string | null,
  detail: FixtureLiveDetail | null,
  onUpdate: (next: FixtureLiveDetail) => void,
  enabled: boolean,
): { degraded: boolean } {
  const [degraded, setDegraded] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const isLive = detail !== null && mapFixtureMatchStatus(detail.statusShort) === "live";
  const shouldPoll = enabled && !!leagueId && !!turnId && !!fixtureId && isLive;

  useEffect(() => {
    if (!shouldPoll || !leagueId || !turnId || !fixtureId) {
      setDegraded(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let intervalMs = BASE_INTERVAL_MS;

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
        const next = await fetchFixtureLiveDetail(
          session.accessToken,
          leagueId as string,
          turnId as string,
          fixtureId as string,
        );
        if (cancelled) {
          return;
        }
        intervalMs = BASE_INTERVAL_MS;
        setDegraded(false);
        onUpdateRef.current(next);
        if (mapFixtureMatchStatus(next.statusShort) !== "live") {
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
  }, [shouldPoll, leagueId, turnId, fixtureId]);

  return { degraded };
}
