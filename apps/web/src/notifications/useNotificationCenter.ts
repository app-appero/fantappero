import type { NotificationItem } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/notifications";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const PAGE_SIZE = 20;

/** In-app notification center: list, unread count, read state (EP09-01). */
export function useNotificationCenter() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchNotifications(stored.accessToken, { pageSize: PAGE_SIZE });
      setItems(result.items);
      setUnreadCount(result.unreadCount);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare le notifiche."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const markRead = useCallback(async (notificationId: string) => {
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    try {
      const updated = await markNotificationRead(stored.accessToken, notificationId);
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setUnreadCount((current) => Math.max(0, current - 1));
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile aggiornare la notifica."));
    }
  }, []);

  const markAllRead = useCallback(async () => {
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    try {
      await markAllNotificationsRead(stored.accessToken);
      setItems((current) => current.map((item) => ({ ...item, read: true })));
      setUnreadCount(0);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile aggiornare le notifiche."));
    }
  }, []);

  return { items, unreadCount, loading, loadError, reload: load, markRead, markAllRead };
}
