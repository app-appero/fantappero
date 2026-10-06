import type { NotificationItem, NotificationList } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchNotificationsMock = vi.fn();
const markNotificationReadMock = vi.fn();
const markAllNotificationsReadMock = vi.fn();

vi.mock("../api/notifications", () => ({
  fetchNotifications: (...args: unknown[]) => fetchNotificationsMock(...args),
  markNotificationRead: (...args: unknown[]) => markNotificationReadMock(...args),
  markAllNotificationsRead: (...args: unknown[]) => markAllNotificationsReadMock(...args),
  fetchNotificationPreferences: vi.fn(),
  updateNotificationPreference: vi.fn(),
}));

import { ToastProvider } from "@fantappero/ui";
import { saveStoredSession, clearStoredSession } from "../auth/sessionStorage";
import { BrowserRouter, MemoryRouter } from "../router/simpleRouter";
import { NotificationCenter } from "./NotificationCenter";
import { resetLocalNotificationReads } from "./useNotificationCenter";

const ITEM: NotificationItem = {
  id: "notif-1",
  category: "sistema",
  title: "Benvenuto",
  body: "Ciao su FantApperò",
  deepLink: "/leghe",
  read: false,
  readAt: null,
  createdAt: "2026-08-19T10:00:00Z",
};

function emptyList(): NotificationList {
  return { items: [], page: 1, pageSize: 20, total: 0, totalPages: 0, unreadCount: 0 };
}

function listWith(items: NotificationItem[]): NotificationList {
  const unreadCount = items.filter((item) => !item.read).length;
  return { items, page: 1, pageSize: 20, total: items.length, totalPages: 1, unreadCount };
}

async function flushAsync(rounds = 4): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("NotificationCenter (EP09-01)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    saveStoredSession({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { id: "user-1", displayName: "Membro Test", globalRole: "member" },
    });
    fetchNotificationsMock.mockReset().mockResolvedValue(emptyList());
    markNotificationReadMock.mockReset();
    markAllNotificationsReadMock.mockReset();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
    resetLocalNotificationReads();
    window.history.pushState(null, "", "/");
  });

  async function renderCenter() {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/leghe"],
          children: createElement(ToastProvider, { children: createElement(NotificationCenter) }),
        }),
      );
    });
    await flushAsync();
  }

  it("shows the unread badge from the initial load", async () => {
    fetchNotificationsMock.mockResolvedValue(listWith([ITEM]));
    await renderCenter();
    const badge = container.querySelector('[data-testid="notification-unread-badge"]');
    expect(badge?.textContent).toBe("1");
  });

  it("empty state: no badge and empty panel message when opened", async () => {
    await renderCenter();
    expect(container.querySelector('[data-testid="notification-unread-badge"]')).toBeNull();

    const trigger = container.querySelector('[data-testid="notification-bell"]') as HTMLElement;
    await act(async () => {
      trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushAsync();

    const panel = document.querySelector('[data-testid="notification-panel"]');
    expect(panel?.parentElement).toBe(document.body);
    expect(panel?.querySelector('[data-testid="notification-empty"]')).not.toBeNull();
    expect(panel?.textContent).toContain("Nessuna notifica");
  });

  it("error state: shows the error panel when the list fails to load", async () => {
    fetchNotificationsMock.mockRejectedValue(new Error("boom"));
    await renderCenter();

    const trigger = container.querySelector('[data-testid="notification-bell"]') as HTMLElement;
    await act(async () => {
      trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushAsync();

    const panel = document.querySelector('[data-testid="notification-panel"]');
    expect(panel?.querySelector('[data-testid="notification-error"]')).not.toBeNull();
  });

  it("clicking an unread item marks it read and closes the panel", async () => {
    fetchNotificationsMock.mockResolvedValue(listWith([ITEM]));
    markNotificationReadMock.mockResolvedValue({ ...ITEM, read: true, readAt: "2026-08-19T10:05:00Z" });
    await renderCenter();

    const trigger = container.querySelector('[data-testid="notification-bell"]') as HTMLElement;
    await act(async () => {
      trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushAsync();

    const item = document.querySelector(
      `[data-testid="notification-item-${ITEM.id}"]`,
    ) as HTMLElement;
    expect(item).not.toBeNull();
    await act(async () => {
      item.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await flushAsync();

    expect(markNotificationReadMock).toHaveBeenCalledWith("token-123", ITEM.id);
    expect(document.querySelector('[data-testid="notification-panel"]')).toBeNull();
    expect(container.querySelector('[data-testid="notification-unread-badge"]')).toBeNull();
  });

  it("opens the invite page and keeps the bell badge off after a stale reload", async () => {
    window.history.pushState(null, "", "/leghe");
    const invite: NotificationItem = {
      ...ITEM,
      id: "invite-notif",
      title: "Nuovo invito a una lega",
      body: "Rosario ti ha invitato a «Lega Demo».",
      deepLink: "/inviti",
    };
    fetchNotificationsMock.mockResolvedValue(listWith([invite]));
    markNotificationReadMock.mockResolvedValue({
      ...invite,
      read: true,
      readAt: "2026-10-03T12:17:00Z",
    });

    await act(async () => {
      root.render(createElement(BrowserRouter, { children: createElement(NotificationCenter) }));
    });
    await flushAsync();
    expect(container.querySelector('[data-testid="notification-unread-badge"]')?.textContent).toBe(
      "1",
    );

    let resolveStale: (value: NotificationList) => void = () => {};
    const stale = new Promise<NotificationList>((resolve) => {
      resolveStale = resolve;
    });
    fetchNotificationsMock.mockImplementationOnce(() => stale);

    const trigger = container.querySelector('[data-testid="notification-bell"]') as HTMLElement;
    await act(async () => {
      trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const item = document.querySelector(
      `[data-testid="notification-item-${invite.id}"]`,
    ) as HTMLAnchorElement;
    expect(item.getAttribute("href")).toBe("/inviti");
    await act(async () => {
      item.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await flushAsync();

    expect(window.location.pathname).toBe("/inviti");
    expect(markNotificationReadMock).toHaveBeenCalledWith("token-123", invite.id);
    expect(container.querySelector('[data-testid="notification-unread-badge"]')).toBeNull();

    await act(async () => {
      resolveStale(listWith([invite]));
      await stale;
    });
    await flushAsync();

    expect(container.querySelector('[data-testid="notification-unread-badge"]')).toBeNull();

    await act(async () => {
      root.unmount();
    });
    root = createRoot(container);
    fetchNotificationsMock.mockResolvedValue(listWith([invite]));
    await act(async () => {
      root.render(createElement(BrowserRouter, { children: createElement(NotificationCenter) }));
    });
    await flushAsync();

    expect(window.location.pathname).toBe("/inviti");
    expect(container.querySelector('[data-testid="notification-unread-badge"]')).toBeNull();
  });

  it("mark-all-read clears the unread badge", async () => {
    fetchNotificationsMock.mockResolvedValue(listWith([ITEM]));
    markAllNotificationsReadMock.mockResolvedValue({ markedCount: 1 });
    await renderCenter();

    const trigger = container.querySelector('[data-testid="notification-bell"]') as HTMLElement;
    await act(async () => {
      trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushAsync();

    const markAll = document.querySelector(
      '[data-testid="notification-mark-all-read"]',
    ) as HTMLElement;
    await act(async () => {
      markAll.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushAsync();

    expect(markAllNotificationsReadMock).toHaveBeenCalledWith("token-123");
    expect(container.querySelector('[data-testid="notification-unread-badge"]')).toBeNull();
  });
});
