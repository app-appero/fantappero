import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { fetchNotifications } from "../api/notifications";

const POLL_MS = 30_000;

/** Numero di notifiche non lette per la campanella dell'header: si aggiorna ogni 30 s e al ritorno in primo piano. */
export function useUnreadNotifications(accessToken: string | null | undefined): {
  unreadCount: number;
  refresh: () => void;
} {
  const [unreadCount, setUnreadCount] = useState(0);
  const tokenRef = useRef(accessToken);
  tokenRef.current = accessToken;

  const refresh = useCallback(() => {
    const token = tokenRef.current;
    if (!token) {
      setUnreadCount(0);
      return;
    }
    fetchNotifications(token, { pageSize: 1 })
      .then((result) => setUnreadCount(result.unreadCount))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        refresh();
      }
    });
    return () => {
      clearInterval(timer);
      subscription.remove();
    };
  }, [accessToken, refresh]);

  return { unreadCount, refresh };
}
