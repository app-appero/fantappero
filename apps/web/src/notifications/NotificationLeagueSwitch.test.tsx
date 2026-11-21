import type { LeagueSummary, NotificationItem, NotificationList, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchNotificationsMock = vi.fn();
const markNotificationReadMock = vi.fn();

vi.mock("../api/auth", () => ({
  logout: vi.fn().mockResolvedValue(undefined),
  fetchMe: (...args: unknown[]) => fetchMeMock(...args),
  refresh: vi.fn(),
  login: vi.fn(),
  loginWithGoogle: vi.fn(),
  register: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../api/leagues", () => ({
  fetchMyLeagues: (...args: unknown[]) => fetchMyLeaguesMock(...args),
}));

vi.mock("../api/notifications", () => ({
  fetchNotifications: (...args: unknown[]) => fetchNotificationsMock(...args),
  markNotificationRead: (...args: unknown[]) => markNotificationReadMock(...args),
  markAllNotificationsRead: vi.fn(),
  fetchNotificationPreferences: vi.fn(),
  updateNotificationPreference: vi.fn(),
}));

import { AuthProvider, useAuth, type AuthContextValue } from "../auth/AuthContext";
import { RequirePermissions } from "../auth/RequirePermissions";
import {
  clearStoredSession,
  loadStoredActiveLeagueId,
  saveStoredActiveLeagueId,
  saveStoredMyLeagues,
  saveStoredSession,
} from "../auth/sessionStorage";
import { BrowserRouter } from "../router/simpleRouter";
import { NotificationCenter } from "./NotificationCenter";
import { resetLocalNotificationReads } from "./useNotificationCenter";

const USER: SessionUser = { id: "user-1", displayName: "Rosario", globalRole: "member" };
const LEAGUE_A: LeagueSummary = { id: "lega-a", name: "Lega A", role: "member", state: "active" };
const LEAGUE_B: LeagueSummary = { id: "lega-b", name: "Lega B", role: "member", state: "active" };
const LEAGUE_C: LeagueSummary = { id: "lega-c", name: "Lega C", role: "member", state: "active" };

function notification(id: string, title: string, deepLink: string): NotificationItem {
  return {
    id,
    category: "mercato",
    title,
    body: "",
    deepLink,
    read: false,
    readAt: null,
    createdAt: "2026-11-21T10:00:00Z",
  };
}

const TRADE_A = notification("trade-a", "Squadra X ti propone uno scambio", "/mercato?scambio=p-1&lega=lega-a");
const LOCK_A = notification("lock-a", "Blocco formazione in arrivo", "/formazione?lega=lega-a");
const ROUND_C = notification("round-c", "Turno omologato", "/classifica?lega=lega-c");
const OLD_LEAGUE = notification("gone", "Turno omologato", "/classifica?lega=lega-lasciata");

let auth: AuthContextValue | null = null;

function CaptureAuth() {
  auth = useAuth();
  return null;
}

async function settle(rounds = 4): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("Clic su una notifica di un'altra lega (Rosario 21/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function renderApp() {
    await act(async () => {
      root.render(
        createElement(BrowserRouter, {
          children: createElement(AuthProvider, {
            children: [
              createElement(CaptureAuth, { key: "capture" }),
              createElement(NotificationCenter, { key: "bell" }),
            ],
          }),
        }),
      );
    });
    await settle();
  }

  /** Apre la campanella e clicca la notifica, come l'utente. */
  async function clickNotification(item: NotificationItem) {
    const bell = container.querySelector('[data-testid="notification-bell"]') as HTMLElement;
    await act(async () => {
      bell.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await settle();
    const link = document.querySelector(`[data-testid="notification-item-${item.id}"]`) as HTMLElement;
    expect(link).not.toBeNull();
    await act(async () => {
      link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await settle();
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    auth = null;
    clearStoredSession();
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    saveStoredMyLeagues(USER.id, [LEAGUE_A, LEAGUE_B, LEAGUE_C]);
    saveStoredActiveLeagueId(LEAGUE_B.id);
    fetchMeMock.mockReset().mockResolvedValue(USER);
    // Ogni caricamento restituisce un elenco nuovo, come il server (si ricarica a ogni pagina).
    fetchMyLeaguesMock
      .mockReset()
      .mockImplementation(async () => [LEAGUE_A, LEAGUE_B, LEAGUE_C].map((league) => ({ ...league })));
    const items = [TRADE_A, LOCK_A, ROUND_C, OLD_LEAGUE];
    fetchNotificationsMock.mockReset().mockImplementation(async (): Promise<NotificationList> => ({
      items,
      page: 1,
      pageSize: 20,
      total: items.length,
      totalPages: 1,
      unreadCount: items.length,
    }));
    markNotificationReadMock.mockReset().mockImplementation(async (_token: string, id: string) => ({
      ...items.find((item) => item.id === id),
      read: true,
    }));
    window.history.pushState(null, "", "/formazione");
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

  it("con attiva la lega B, la notifica della lega A apre la pagina nella lega A", async () => {
    await renderApp();
    expect(auth?.activeLeagueId).toBe(LEAGUE_B.id);

    await clickNotification(TRADE_A);

    expect(window.location.pathname).toBe("/mercato");
    expect(new URLSearchParams(window.location.search).get("scambio")).toBe("p-1");
    expect(auth?.activeLeagueId).toBe(LEAGUE_A.id);
    expect(loadStoredActiveLeagueId()).toBe(LEAGUE_A.id);
  });

  it("due notifiche di leghe diverse una dopo l'altra cambiano lega ogni volta", async () => {
    await renderApp();

    await clickNotification(TRADE_A);
    expect(auth?.activeLeagueId).toBe(LEAGUE_A.id);

    await clickNotification(ROUND_C);
    expect(window.location.pathname).toBe("/classifica");
    expect(auth?.activeLeagueId).toBe(LEAGUE_C.id);

    await clickNotification(LOCK_A);
    expect(window.location.pathname).toBe("/formazione");
    expect(auth?.activeLeagueId).toBe(LEAGUE_A.id);
    expect(loadStoredActiveLeagueId()).toBe(LEAGUE_A.id);
  });

  it("dopo un cambio lega dal selettore, un'altra notifica della stessa lega del link la riapre", async () => {
    await renderApp();
    await clickNotification(TRADE_A);
    expect(auth?.activeLeagueId).toBe(LEAGUE_A.id);

    // Sulla pagina aperta dalla notifica (l'indirizzo ha ancora ?lega=lega-a) si sceglie B.
    await act(async () => {
      auth?.setActiveLeagueId(LEAGUE_B.id);
    });
    await settle();
    expect(auth?.activeLeagueId).toBe(LEAGUE_B.id);

    await clickNotification(LOCK_A);
    expect(window.location.pathname).toBe("/formazione");
    expect(auth?.activeLeagueId).toBe(LEAGUE_A.id);
  });

  it("riaprire la stessa notifica dopo un cambio lega dal selettore riporta nella sua lega", async () => {
    await renderApp();
    await clickNotification(TRADE_A);
    await act(async () => {
      auth?.setActiveLeagueId(LEAGUE_B.id);
    });
    await settle();
    expect(auth?.activeLeagueId).toBe(LEAGUE_B.id);

    // Stesso indirizzo di prima: il router non vede nessun cambio di ?lega=.
    await clickNotification(TRADE_A);
    expect(window.location.pathname).toBe("/mercato");
    expect(auth?.activeLeagueId).toBe(LEAGUE_A.id);
  });

  it("la notifica di una lega di cui non si fa più parte apre la pagina nella lega attiva", async () => {
    await renderApp();

    await clickNotification(OLD_LEAGUE);

    expect(window.location.pathname).toBe("/classifica");
    expect(auth?.activeLeagueId).toBe(LEAGUE_B.id);
    expect(loadStoredActiveLeagueId()).toBe(LEAGUE_B.id);
  });

  it("su una pagina senza permessi nella lega della notifica il ripiego resta (nessuna «Selezione lega» infinita)", async () => {
    // Lega A: solo iscritto. Lega B: amministratore. La pagina chiede i permessi da amministratore.
    const memberA: LeagueSummary = { ...LEAGUE_A, role: "member" };
    const adminB: LeagueSummary = { ...LEAGUE_B, role: "league_admin" };
    saveStoredMyLeagues(USER.id, [memberA, adminB]);
    fetchMyLeaguesMock.mockImplementation(async () => [memberA, adminB].map((league) => ({ ...league })));
    const directoryA = notification("dir-a", "Nuovo partecipante in lega", "/fantallenatori?lega=lega-a");
    fetchNotificationsMock.mockImplementation(async (): Promise<NotificationList> => ({
      items: [directoryA],
      page: 1,
      pageSize: 20,
      total: 1,
      totalPages: 1,
      unreadCount: 1,
    }));

    await act(async () => {
      root.render(
        createElement(BrowserRouter, {
          children: createElement(AuthProvider, {
            children: [
              createElement(CaptureAuth, { key: "capture" }),
              createElement(NotificationCenter, { key: "bell" }),
              createElement(RequirePermissions, {
                key: "gate",
                required: ["league:admin"],
                children: createElement("p", { "data-testid": "protected-content" }, "Pagina"),
              }),
            ],
          }),
        }),
      );
    });
    await settle();

    await clickNotification(directoryA);

    expect(window.location.pathname).toBe("/fantallenatori");
    expect(container.querySelector('[data-testid="route-switching-league"]')).toBeNull();
    expect(container.querySelector('[data-testid="protected-content"]')).not.toBeNull();
    expect(auth?.activeLeagueId).toBe(adminB.id);
  });
});
