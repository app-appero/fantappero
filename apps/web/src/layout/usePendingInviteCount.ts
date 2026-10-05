import { useCallback, useEffect, useRef, useState } from "react";
import { fetchPendingInviteCount } from "../api/managerInvites";
import { loadStoredSession } from "../auth/sessionStorage";

const listeners = new Set<() => void>();

/**
 * Chiede al badge rosso degli inviti di rileggere il conteggio.
 * Va chiamato dopo un'accettazione o un rifiuto: il conteggio non ha polling.
 */
export function notifyPendingInvitesChanged(): void {
  for (const listener of listeners) {
    listener();
  }
}

/**
 * Conteggio inviti pendenti per il badge (EP13-P07).
 *
 * Nessun polling: il dato cambia raramente e si aggiorna all'apertura, quando
 * la finestra torna in primo piano e dopo ogni azione su un invito.
 */
export function usePendingInviteCount(enabled: boolean): number {
  const [count, setCount] = useState(0);
  const requestSeq = useRef(0);

  const refresh = useCallback(async () => {
    const requestId = ++requestSeq.current;
    if (!enabled) {
      setCount(0);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCount(0);
      return;
    }
    try {
      const result = await fetchPendingInviteCount(stored.accessToken);
      if (requestId !== requestSeq.current) {
        return;
      }
      setCount(result.pendingInviteCount);
    } catch {
      if (requestId !== requestSeq.current) {
        return;
      }
      // Il badge è accessorio: un errore non deve rompere la navigazione.
      setCount(0);
    }
  }, [enabled]);

  useEffect(() => {
    void refresh();
    listeners.add(refresh);
    if (typeof window === "undefined") {
      return () => {
        listeners.delete(refresh);
      };
    }
    const onFocus = () => {
      void refresh();
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.removeEventListener("focus", onFocus);
      listeners.delete(refresh);
    };
  }, [refresh]);

  return count;
}
