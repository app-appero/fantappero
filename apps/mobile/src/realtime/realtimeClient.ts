import { REALTIME_STREAM_PATH, type RealtimeEvent } from "@fantappero/contracts";
import { fetch as streamingFetch } from "expo/fetch";
import { loadMobileEnv } from "../config/env";

/**
 * Un'unica connessione SSE per app, condivisa da tutti gli iscritti (EP09-07).
 * React Native non ha `EventSource` e il `fetch` classico non fa streaming:
 * usiamo `expo/fetch`. Senza tempo reale (503, rete, nessuna sessione) restano
 * i polling già presenti: questo modulo non fa mai fallire nessuno.
 */
type Handler = (event: RealtimeEvent) => void;
type Auth = { accessToken: string; leagueIds: readonly string[] } | null;

const handlers = new Set<Handler>();
let auth: Auth = null;
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

async function connect(signal: AbortSignal, current: NonNullable<Auth>): Promise<void> {
  const base = loadMobileEnv().expoPublicApiBaseUrl.replace(/\/$/, "");
  const query = encodeURIComponent(current.leagueIds.join(","));
  const response = await streamingFetch(`${base}${REALTIME_STREAM_PATH}?leagueIds=${query}`, {
    headers: { Authorization: `Bearer ${current.accessToken}`, Accept: "text/event-stream" },
    signal,
  });
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
    for (const event of parsed.events) {
      handlers.forEach((handler) => handler(event));
    }
  }
}

function stop(): void {
  clearTimeout(retryTimer);
  abort?.abort();
  abort = null;
}

function start(): void {
  if (abort || handlers.size === 0 || !auth) {
    return;
  }
  const controller = new AbortController();
  abort = controller;
  void connect(controller.signal, auth)
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

/** Aggiorna token e leghe; ricollega se cambiano (login, logout, cambio account). */
export function setRealtimeAuth(next: Auth): void {
  const changed =
    auth?.accessToken !== next?.accessToken ||
    auth?.leagueIds.join(",") !== next?.leagueIds.join(",");
  auth = next;
  if (!changed) {
    return;
  }
  stop();
  failures = 0;
  start();
}

export function subscribeRealtime(handler: Handler): () => void {
  handlers.add(handler);
  start();
  return () => {
    handlers.delete(handler);
    if (handlers.size === 0) {
      stop();
    }
  };
}
