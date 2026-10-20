import type { RealtimeEvent } from "@fantappero/contracts";
import { useEffect, useRef } from "react";
import { subscribeRealtime } from "./realtimeClient";

/** Esegue `onEvent` a ogni evento in tempo reale mentre il componente è montato. */
export function useRealtimeEvent(onEvent: (event: RealtimeEvent) => void, enabled = true): void {
  const ref = useRef(onEvent);
  ref.current = onEvent;
  useEffect(() => {
    if (!enabled) {
      return;
    }
    return subscribeRealtime((event) => ref.current(event));
  }, [enabled]);
}
