import type { LeagueSummary, SessionUser } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "../router/simpleRouter";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();

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

import { AuthProvider, useAuth, type AuthContextValue } from "./AuthContext";
import { RequirePermissions } from "./RequirePermissions";
import {
  clearStoredSession,
  loadStoredActiveLeagueId,
  saveStoredActiveLeagueId,
  saveStoredMyLeagues,
  saveStoredSession,
} from "./sessionStorage";

const USER: SessionUser = { id: "user-1", displayName: "Giulia", globalRole: "member" };

/** Lega X: solo iscritta. Lega Y: amministratrice. */
const MEMBER_X: LeagueSummary = { id: "lega-x", name: "Lega X", role: "member", state: "draft" };
const ADMIN_Y: LeagueSummary = {
  id: "lega-y",
  name: "Lega Y",
  role: "league_admin",
  state: "draft",
};
const ADMIN_X: LeagueSummary = { ...MEMBER_X, role: "league_admin" };
const MEMBER_Z: LeagueSummary = { id: "lega-z", name: "Lega Z", role: "member", state: "draft" };

let auth: AuthContextValue | null = null;

function CaptureAuth() {
  auth = useAuth();
  return null;
}

function ProtectedPage() {
  return createElement("p", { "data-testid": "protected-content" }, "Directory fantallenatori");
}

describe("RequirePermissions — /fantallenatori?lega=<lega senza permessi> (QA 21/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = (id: string) => container.querySelector(`[data-testid="${id}"]`);

  async function settle() {
    for (let round = 0; round < 4; round += 1) {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }

  /** Stesso albero a ogni chiamata: cambiare l'indirizzo è come navigare, lo stato resta. */
  async function renderAt(entry: string) {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: [entry],
          children: createElement(AuthProvider, {
            children: [
              createElement(CaptureAuth, { key: "capture" }),
              createElement(RequirePermissions, {
                key: "gate",
                required: ["league:admin"],
                children: createElement(ProtectedPage),
              }),
            ],
          }),
        }),
      );
    });
    await settle();
  }

  /** Ogni caricamento restituisce un elenco nuovo, come il server. */
  function serverLeagues(leagues: LeagueSummary[]) {
    fetchMyLeaguesMock.mockImplementation(async () => leagues.map((league) => ({ ...league })));
  }

  function expectPage() {
    expect(byTestId("route-switching-league")).toBeNull();
    expect(byTestId("route-forbidden")).toBeNull();
    expect(byTestId("protected-content")).not.toBeNull();
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    auth = null;
    clearStoredSession();
    saveStoredSession({ accessToken: "access-token", refreshToken: "refresh-token", user: USER });
    fetchMeMock.mockReset().mockResolvedValue(USER);
    fetchMyLeaguesMock.mockReset();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
  });

  it("con le leghe in cache e la lega attiva salvata uguale a ?lega=, ripiega sulla lega dove è admin", async () => {
    serverLeagues([MEMBER_X, ADMIN_Y]);
    saveStoredMyLeagues(USER.id, [MEMBER_X, ADMIN_Y]);
    saveStoredActiveLeagueId(MEMBER_X.id);

    await renderAt(`/fantallenatori?lega=${MEMBER_X.id}`);

    expectPage();
    expect(auth?.activeLeagueId).toBe(ADMIN_Y.id);
    expect(loadStoredActiveLeagueId()).toBe(ADMIN_Y.id);
  });

  it("senza leghe in cache e la lega attiva salvata uguale a ?lega=, ripiega lo stesso", async () => {
    serverLeagues([MEMBER_X, ADMIN_Y]);
    saveStoredActiveLeagueId(MEMBER_X.id);

    await renderAt(`/fantallenatori?lega=${MEMBER_X.id}`);

    expectPage();
    expect(auth?.activeLeagueId).toBe(ADMIN_Y.id);
    expect(loadStoredActiveLeagueId()).toBe(ADMIN_Y.id);
  });

  it("se nessuna lega dà i permessi mostra «Permessi insufficienti», non «Selezione lega»", async () => {
    serverLeagues([MEMBER_X, MEMBER_Z]);
    saveStoredMyLeagues(USER.id, [MEMBER_X, MEMBER_Z]);
    saveStoredActiveLeagueId(MEMBER_Z.id);

    await renderAt(`/fantallenatori?lega=${MEMBER_X.id}`);

    expect(byTestId("route-switching-league")).toBeNull();
    expect(byTestId("protected-content")).toBeNull();
    expect(byTestId("route-forbidden")?.textContent).toContain("Permessi insufficienti");
    // Il link della notifica ha comunque aperto la sua lega.
    expect(auth?.activeLeagueId).toBe(MEMBER_X.id);
  });

  it("se nella lega di ?lega= ha i permessi, quella resta attiva (link delle notifiche)", async () => {
    serverLeagues([ADMIN_X, ADMIN_Y]);
    saveStoredMyLeagues(USER.id, [ADMIN_X, ADMIN_Y]);
    saveStoredActiveLeagueId(ADMIN_Y.id);

    await renderAt(`/fantallenatori?lega=${ADMIN_X.id}`);

    expectPage();
    expect(auth?.activeLeagueId).toBe(ADMIN_X.id);
    expect(loadStoredActiveLeagueId()).toBe(ADMIN_X.id);
  });

  it("?lega= si applica una volta: una lega scelta dopo resta anche se le leghe si ricaricano", async () => {
    serverLeagues([ADMIN_X, ADMIN_Y]);
    saveStoredActiveLeagueId(ADMIN_Y.id);
    await renderAt(`/fantallenatori?lega=${ADMIN_X.id}`);
    expect(auth?.activeLeagueId).toBe(ADMIN_X.id);

    // Cambio lega dal selettore, poi un nuovo elenco di leghe dal server: resta la scelta.
    await act(async () => {
      auth?.setActiveLeagueId(ADMIN_Y.id);
    });
    await act(async () => {
      await auth?.refreshLeagues();
    });
    await settle();
    expect(auth?.activeLeagueId).toBe(ADMIN_Y.id);
    expectPage();

    // Tolto il parametro e aperto un nuovo link con la stessa lega, la riapre.
    await renderAt("/fantallenatori");
    expect(auth?.activeLeagueId).toBe(ADMIN_Y.id);
    await renderAt(`/fantallenatori?lega=${ADMIN_X.id}`);
    expect(auth?.activeLeagueId).toBe(ADMIN_X.id);
    expectPage();
  });
});
