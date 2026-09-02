import type { FixtureLiveDetail } from "@fantappero/contracts";
import { mapFixtureMatchStatus } from "@fantappero/contracts";
import { useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchFixtureLiveDetail } from "../api/leagues";

const BASE_INTERVAL_MS = 30_000;
const MAX_INTERVAL_MS = 60_000;

/**
 * Mobile port of `apps/web/src/matchday/useLiveFixturePolling.ts`: polls a single
 * fixture's live detail (score, minuto, formazioni, eventi) while the match is
 * actually in corso.
 *
 * Same adaptation as `useLiveH2HPolling`/`useLiveTurnPolling`: the access token is
 * passed in (reactive session) instead of read from `loadStoredSession()`, and polling
 * pauses while the app is backgrounded via `AppState`.
 */
export function useLiveFixturePolling(
  accessToken: string | null,
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
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;

  const isLive = detail !== null && mapFixtureMatchStatus(detail.statusShort) === "live";
  const shouldPoll =
    enabled && !!accessToken && !!leagueId && !!turnId && !!fixtureId && isLive;

  useEffect(() => {
    if (!shouldPoll || !leagueId || !turnId || !fixtureId) {
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
        const next = await fetchFixtureLiveDetail(
          token,
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
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [shouldPoll, leagueId, turnId, fixtureId]);

  return { degraded };
}
