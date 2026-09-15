import { act, createElement, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "../router/simpleRouter";

const logoutMock = vi.fn().mockResolvedValue(undefined);
const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();

vi.mock("../api/auth", () => ({
  logout: (...args: unknown[]) => logoutMock(...args),
  fetchMe: (...args: unknown[]) => fetchMeMock(...args),
  refresh: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../api/leagues", () => ({
  fetchMyLeagues: (...args: unknown[]) => fetchMyLeaguesMock(...args),
}));

import { AuthProvider, useAuth } from "./AuthContext";
import {
  clearStoredSession,
  loadStoredSession,
  saveStoredMyLeagues,
  saveStoredSession,
} from "./sessionStorage";

let logoutFn: (() => Promise<void>) | null = null;

function CaptureLogout() {
  const { logout } = useAuth();
  useEffect(() => {
    logoutFn = logout;
  }, [logout]);
  return null;
}

describe("AuthContext logout (EP02-01)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    logoutFn = null;
    logoutMock.mockClear();
    fetchMyLeaguesMock.mockReset();
    fetchMyLeaguesMock.mockResolvedValue([]);
    clearStoredSession();
    saveStoredSession({
      accessToken: "access-token",
      refreshToken: "refresh-token",
      user: { id: "user-1", displayName: "Test User", globalRole: "member" },
    });
    fetchMeMock.mockResolvedValue({
      id: "user-1",
      displayName: "Test User",
      globalRole: "member",
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
  });

  it("clears local session and revokes refresh token on logout", async () => {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/leghe"],
          children: createElement(AuthProvider, {
            children: createElement(CaptureLogout),
          }),
        }),
      );
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(logoutFn).not.toBeNull();

    await act(async () => {
      await logoutFn!();
    });

    expect(logoutMock).toHaveBeenCalledWith({ refreshToken: "refresh-token" });
    expect(loadStoredSession()).toBeNull();
  });
});

function CaptureLeagues() {
  const { leagues, leaguesError } = useAuth();
  return createElement(
    "div",
    { "data-testid": "leagues-snapshot", "data-error": leaguesError ?? "" },
    leagues.map((league) => league.name).join(","),
  );
}

describe("AuthContext membership cache", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchMyLeaguesMock.mockReset();
    clearStoredSession();
    saveStoredSession({
      accessToken: "access-token",
      refreshToken: "refresh-token",
      user: { id: "user-1", displayName: "Romy", globalRole: "global_operator" },
    });
    saveStoredMyLeagues("user-1", [
      {
        id: "lega-test",
        name: "Lega di test",
        role: "league_admin",
        state: "draft",
      },
    ]);
    fetchMeMock.mockResolvedValue({
      id: "user-1",
      displayName: "Romy",
      globalRole: "global_operator",
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
  });

  it("keeps cached test leagues when /leagues/mine fails", async () => {
    fetchMyLeaguesMock.mockRejectedValue(new Error("column leagues.market_open does not exist"));

    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/lega/amministrazione"],
          children: createElement(AuthProvider, {
            children: createElement(CaptureLeagues),
          }),
        }),
      );
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const snapshot = container.querySelector('[data-testid="leagues-snapshot"]');
    expect(snapshot?.textContent).toContain("Lega di test");
    expect(snapshot?.getAttribute("data-error")).toContain("market_open");
  });
});
