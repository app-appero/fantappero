import { REALTIME_STREAM_PATH, type RealtimeEvent } from "@fantappero/contracts";
import { getWebEnv, resolveApiBaseUrl } from "../config/env";
import { loadStoredMyLeagues, loadStoredSession } from "../auth/sessionStorage";

/**
 * Un'unica connessione SSE per scheda, condivisa da tutti gli iscritti (EP09-07).
 * `EventSource` non sa mandare l'header Authorization: leggiamo il flusso con
 * `fetch`. Senza tempo reale (503, rete, nessuna sessione) si resta sul polling
 * già presente: questo modulo non fa mai fallire nessuno.
 */
type Handler = (event: RealtimeEvent) => void;

const handlers = new Set<Handler>();
let abort: AbortController | null = null;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let failures = 0;

function parseEvents(buffer: string): { events: RealtimeEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: RealtimeEvent[] = [];
  for (const part of parts) {
    for (const line of part.split("\n")) {
      if (!line.startsWith("data:")) {
        continue;
      }
      try {
        events.push(JSON.parse(line.slice(5).trim()) as RealtimeEvent);
      } catch {
        // messaggio non leggibile: ignorato
      }
    }
  }
  return { events, rest };
}

function dispatch(event: RealtimeEvent): void {
  for (const handler of handlers) {
    handler(event);
  }
}

async function connect(signal: AbortSignal): Promise<void> {
  const session = loadStoredSession();
  if (!session?.accessToken) {
    throw new Error("no-session");
  }
  const leagueIds = loadStoredMyLeagues(session.user.id).map((league) => league.id);
  const base = resolveApiBaseUrl(getWebEnv().viteApiBaseUrl);
  const response = await fetch(
    `${base}${REALTIME_STREAM_PATH}?leagueIds=${encodeURIComponent(leagueIds.join(","))}`,
    {
      headers: { Authorization: `Bearer ${session.accessToken}`, Accept: "text/event-stream" },
      signal,
    },
  );
  if (!response.ok || !response.body) {
    throw new Error(`stream-${response.status}`);
  }
  failures = 0;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      return;
    }
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseEvents(buffer);
    buffer = parsed.rest;
    parsed.events.forEach(dispatch);
  }
}

function start(): void {
  if (abort || handlers.size === 0) {
    return;
  }
  const controller = new AbortController();
  abort = controller;
  void connect(controller.signal)
    .catch(() => {
      failures += 1;
    })
    .finally(() => {
      if (abort === controller) {
        abort = null;
      }
      if (controller.signal.aborted || handlers.size === 0) {
        return;
      }
      // Chiusura normale (~10 min): riconnessione rapida; errori: backoff fino a 60 s.
      const delay = failures === 0 ? 1_000 : Math.min(60_000, 3_000 * 2 ** (failures - 1));
      retryTimer = setTimeout(start, delay);
    });
}

/** Riceve gli eventi finché non si chiama la funzione restituita. */
export function subscribeRealtime(handler: Handler): () => void {
  handlers.add(handler);
  start();
  return () => {
    handlers.delete(handler);
    if (handlers.size === 0) {
      clearTimeout(retryTimer);
      abort?.abort();
      abort = null;
    }
  };
}
