import type { NotificationItem, NotificationList } from "@fantappero/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/notifications";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const PAGE_SIZE = 20;

/**
 * Letture già confermate in questa scheda.
 *
 * Il centro notifiche si rimonta a ogni cambio pagina: una GET partita prima
 * del POST «letta» non deve riaccendere il badge.
 */
const locallyReadIds = new Set<string>();
const readListeners = new Set<() => void>();

function notifyReadListeners(): void {
  for (const listener of readListeners) {
    listener();
  }
}

export function resetLocalNotificationReads(): void {
  locallyReadIds.clear();
}

function applyLocalReads(result: NotificationList): {
  items: NotificationItem[];
  unreadCount: number;
} {
  let hiddenUnread = 0;
  const items = result.items.map((item) => {
    if (item.read) {
      locallyReadIds.delete(item.id);
      return item;
    }
    if (locallyReadIds.has(item.id)) {
      hiddenUnread += 1;
      return { ...item, read: true };
    }
    return item;
  });
  return {
    items,
    unreadCount: Math.max(0, result.unreadCount - hiddenUnread),
  };
}

/** In-app notification center: list, unread count, read state (EP09-01). */
export function useNotificationCenter() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const requestSeq = useRef(0);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const load = useCallback(async (mode: "initial" | "refresh" = "initial") => {
    const requestId = ++requestSeq.current;
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      if (requestId !== requestSeq.current) {
        return;
      }
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    if (mode === "initial") {
      setLoading(true);
    }
    setLoadError(null);
    try {
      const result = await fetchNotifications(stored.accessToken, { pageSize: PAGE_SIZE });
      if (requestId !== requestSeq.current) {
        return;
      }
      const reconciled = applyLocalReads(result);
      setItems(reconciled.items);
      setUnreadCount(reconciled.unreadCount);
    } catch (error) {
      if (requestId !== requestSeq.current) {
        return;
      }
      setLoadError(getApiErrorMessage(error, "Impossibile caricare le notifiche."));
    } finally {
      if (requestId === requestSeq.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load("initial");
  }, [load]);

  useEffect(() => {
    const refresh = () => {
      void load("refresh");
    };
    readListeners.add(refresh);
    return () => {
      readListeners.delete(refresh);
    };
  }, [load]);

  const markRead = useCallback(async (notificationId: string) => {
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    const target = itemsRef.current.find((item) => item.id === notificationId);
    const wasUnread = Boolean(target && !target.read && !locallyReadIds.has(notificationId));
    locallyReadIds.add(notificationId);
    requestSeq.current += 1;
    setLoading(false);
    if (wasUnread) {
      setItems((current) =>
        current.map((item) => (item.id === notificationId ? { ...item, read: true } : item)),
      );
      setUnreadCount((current) => Math.max(0, current - 1));
    }
    try {
      const updated = await markNotificationRead(stored.accessToken, notificationId);
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      locallyReadIds.delete(notificationId);
      if (wasUnread) {
        setItems((current) =>
          current.map((item) =>
            item.id === notificationId ? { ...item, read: false } : item,
          ),
        );
        setUnreadCount((current) => current + 1);
      }
      setLoadError(getApiErrorMessage(error, "Impossibile aggiornare la notifica."));
      notifyReadListeners();
    }
  }, []);

  const markAllRead = useCallback(async () => {
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    const snapshot = itemsRef.current;
    for (const item of snapshot) {
      if (!item.read) {
        locallyReadIds.add(item.id);
      }
    }
    requestSeq.current += 1;
    setLoading(false);
    setItems((current) => current.map((item) => ({ ...item, read: true })));
    setUnreadCount(0);
    try {
      await markAllNotificationsRead(stored.accessToken);
    } catch (error) {
      for (const item of snapshot) {
        if (!item.read) {
          locallyReadIds.delete(item.id);
        }
      }
      setItems(snapshot);
      setUnreadCount(snapshot.filter((item) => !item.read).length);
      setLoadError(getApiErrorMessage(error, "Impossibile aggiornare le notifiche."));
    }
  }, []);

  return { items, unreadCount, loading, loadError, reload: load, markRead, markAllRead };
}
