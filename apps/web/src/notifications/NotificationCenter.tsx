import type { NotificationItem } from "@fantappero/contracts";
import { UiStatePanel } from "@fantappero/ui";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "../router/simpleRouter";
import { IconBell } from "../navigation/NavIcons";
import { useNotificationCenter } from "./useNotificationCenter";

const CATEGORY_LABELS: Record<NotificationItem["category"], string> = {
  sistema: "Sistema",
  formazione: "Formazione",
  mercato: "Mercato",
  risultati: "Risultati",
};

function formatTimestamp(value: string): string {
  try {
    return new Date(value).toLocaleString("it-IT", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
}

/** Bell + panel for the in-app notification center (EP09-01). */
export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { items, unreadCount, loading, loadError, reload, markRead, markAllRead } =
    useNotificationCenter();

  useEffect(() => {
    if (!open) {
      return;
    }
    void reload();

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function handleItemClick(item: NotificationItem) {
    if (!item.read) {
      await markRead(item.id);
    }
    setOpen(false);
    if (item.deepLink) {
      navigate(item.deepLink);
    }
  }

  return (
    <div className="fa-notification-center" ref={containerRef}>
      <button
        type="button"
        className="fa-notification-center__trigger"
        aria-label="Notifiche"
        aria-expanded={open}
        aria-haspopup="true"
        data-testid="notification-bell"
        onClick={() => setOpen((current) => !current)}
      >
        <IconBell />
        {unreadCount > 0 ? (
          <span className="fa-notification-center__badge" data-testid="notification-unread-badge">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="fa-notification-center__panel" data-testid="notification-panel">
          <div className="fa-notification-center__header">
            <span>Notifiche</span>
            {unreadCount > 0 ? (
              <button
                type="button"
                className="fa-link-muted"
                onClick={() => void markAllRead()}
                data-testid="notification-mark-all-read"
              >
                Segna tutte come lette
              </button>
            ) : null}
          </div>
          {loading ? (
            <UiStatePanel state="loading" title="Caricamento" message="Recupero le notifiche…" />
          ) : loadError ? (
            <UiStatePanel state="error" title="Errore" message={loadError} />
          ) : items.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessuna notifica"
              message="Non hai ancora notifiche."
            />
          ) : (
            <ul className="fa-notification-center__list">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`fa-notification-center__item${item.read ? "" : " fa-notification-center__item--unread"}`}
                    onClick={() => void handleItemClick(item)}
                    data-testid={`notification-item-${item.id}`}
                  >
                    <span className="fa-notification-center__item-category">
                      {CATEGORY_LABELS[item.category]}
                    </span>
                    <span className="fa-notification-center__item-title">{item.title}</span>
                    <span className="fa-notification-center__item-body">{item.body}</span>
                    <span className="fa-notification-center__item-time">
                      {formatTimestamp(item.createdAt)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
