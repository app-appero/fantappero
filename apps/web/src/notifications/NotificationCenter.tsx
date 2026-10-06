import type { NotificationItem } from "@fantappero/contracts";
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useNavigate } from "../router/simpleRouter";
import { IconBell } from "../navigation/NavIcons";
import { resolveNotificationDestination } from "./notificationDestination";
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
    void reload("refresh");

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

  function openNotification(item: NotificationItem) {
    const destination = resolveNotificationDestination(item);
    if (!item.read) {
      void markRead(item.id);
    }
    setOpen(false);
    if (destination) {
      navigate(destination);
    }
  }

  function handleItemClick(event: ReactMouseEvent<HTMLAnchorElement>, item: NotificationItem) {
    const modified =
      event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
    if (modified) {
      if (!item.read) {
        void markRead(item.id);
      }
      setOpen(false);
      return;
    }
    event.preventDefault();
    openNotification(item);
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
            <p className="fa-notification-center__status" data-testid="notification-loading">
              Caricamento…
            </p>
          ) : loadError ? (
            <p className="fa-notification-center__status fa-notification-center__status--error" data-testid="notification-error">
              {loadError}
            </p>
          ) : items.length === 0 ? (
            <p className="fa-notification-center__empty" data-testid="notification-empty">
              Nessuna notifica
            </p>
          ) : (
            <ul className="fa-notification-center__list">
              {items.map((item) => {
                const destination = resolveNotificationDestination(item);
                const className = `fa-notification-center__item${item.read ? "" : " fa-notification-center__item--unread"}`;
                const content = (
                  <>
                    <span className="fa-notification-center__item-category">
                      {CATEGORY_LABELS[item.category]}
                    </span>
                    <span className="fa-notification-center__item-title">{item.title}</span>
                    <span className="fa-notification-center__item-body">{item.body}</span>
                    <span className="fa-notification-center__item-time">
                      {formatTimestamp(item.createdAt)}
                    </span>
                  </>
                );
                return (
                  <li key={item.id}>
                    {destination ? (
                      <a
                        href={destination}
                        className={className}
                        onClick={(event) => handleItemClick(event, item)}
                        data-testid={`notification-item-${item.id}`}
                      >
                        {content}
                      </a>
                    ) : (
                      <button
                        type="button"
                        className={className}
                        onClick={() => openNotification(item)}
                        data-testid={`notification-item-${item.id}`}
                      >
                        {content}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
