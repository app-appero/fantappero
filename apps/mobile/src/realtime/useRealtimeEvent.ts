import type { RealtimeEvent } from "@fantappero/contracts";
import { useEffect, useRef } from "react";
import { useAuthSession } from "../session/DemoSessionContext";
import { setRealtimeAuth, subscribeRealtime } from "./realtimeClient";

/** Esegue `onEvent` a ogni evento in tempo reale mentre il componente è montato. */
export function useRealtimeEvent(onEvent: (event: RealtimeEvent) => void, enabled = true): void {
  const { accessToken, leagues } = useAuthSession();
  const ref = useRef(onEvent);
  ref.current = onEvent;
  const leagueKey = leagues.map((league) => league.id).join(",");

  useEffect(() => {
    setRealtimeAuth(
      accessToken ? { accessToken, leagueIds: leagueKey ? leagueKey.split(",") : [] } : null,
    );
  }, [accessToken, leagueKey]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    return subscribeRealtime((event) => ref.current(event));
  }, [enabled]);
}
