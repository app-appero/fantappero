import type { AdminAppUsage } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const usersMock = vi.fn();
const configMock = vi.fn();
const saveMock = vi.fn();

vi.mock("../api/admin", () => ({
  fetchAppVersionUsers: (...args: unknown[]) => usersMock(...args),
  fetchAppVersionConfig: (...args: unknown[]) => configMock(...args),
  saveAppVersionConfig: (...args: unknown[]) => saveMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "t", refreshToken: "r", user: { id: "u" } }),
}));

import { AdminAppUsagePanel } from "./AdminAppUsagePanel";
import { AdminAppVersionPage } from "./AdminAppVersionPage";

// 23/11/2026 alle 12:00 a Roma.
const NOW = new Date("2026-11-23T11:00:00Z");
const ANNOUNCED = {
  latestVersionName: "1.4.0",
  latestVersionCode: 5,
  downloadUrl: "https://drive.google.com/drive/folders/prova",
  message: null,
};

const USAGE: AdminAppUsage = {
  generatedAt: NOW.toISOString(),
  announced: ANNOUNCED,
  totalUsers: 12,
  appUsers: 9,
  upToDateUsers: 4,
  groups: [
    {
      kind: "version",
      platform: "android",
      versionName: "1.4.0",
      versionCode: 5,
      upToDate: true,
      users: [
        {
          userId: "u1",
          displayName: "Bomber",
          name: "Mario Rossi",
          email: "mario@example.com",
          firstSeenAt: "2026-11-23T08:00:00Z",
          lastSeenAt: "2026-11-23T09:30:00Z",
        },
      ],
    },
    {
      kind: "unknown_recent",
      platform: "android",
      versionName: null,
      versionCode: null,
      upToDate: false,
      users: [
        {
          userId: "u2",
          displayName: "Giulia",
          name: null,
          email: "giulia@example.com",
          firstSeenAt: "2026-11-22T08:00:00Z",
          lastSeenAt: "2026-11-22T20:00:00Z",
        },
      ],
    },
    {
      kind: "web_android",
      platform: "web-android",
      versionName: null,
      versionCode: null,
      upToDate: false,
      users: [
        {
          userId: "u4",
          displayName: "Sito Android",
          name: null,
          email: "android@example.com",
          firstSeenAt: "2026-11-20T08:00:00Z",
          lastSeenAt: "2026-11-23T10:15:00Z",
        },
      ],
    },
    {
      kind: "never",
      platform: null,
      versionName: null,
      versionCode: null,
      upToDate: false,
      users: [
        {
          userId: "u3",
          displayName: "Solo Sito",
          name: null,
          email: "sito@example.com",
          firstSeenAt: null,
          lastSeenAt: null,
        },
      ],
    },
  ],
};

describe("«Chi ha quale versione» (release 1.4, Rosario 23/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    usersMock.mockReset();
    configMock.mockReset();
    saveMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("un gruppo per versione con gli utenti, poi le versioni non note, il sito da Android e chi non usa l'app", async () => {
    usersMock.mockResolvedValue(USAGE);
    await act(async () => {
      root.render(createElement(AdminAppUsagePanel, { now: NOW }));
    });
    const text = container.textContent ?? "";
    expect(text).toContain("Chi ha quale versione");
    expect(text).toContain("4 utenti aggiornati su 9 che usano l'app · 12 utenti in tutto");
    const groups = [...container.querySelectorAll("details")];
    expect(groups.map((group) => group.querySelector("summary")?.textContent)).toEqual([
      "1.4.0 (5): 1 utenteaggiornati",
      "Versione non nota (app 1.2 o 1.3): 1 utente",
      "Sito da Android (app non installata o non ancora vista): 1 utente",
      "App mai usata / solo sito: 1 utente",
    ]);
    // «App mai usata» parte chiuso, gli altri aperti.
    expect(groups.map((group) => group.open)).toEqual([true, true, true, false]);
    expect(groups[0]?.textContent).toContain("Bomber (Mario Rossi)");
    expect(groups[0]?.textContent).toContain("mario@example.com");
    expect(groups[0]?.textContent).toContain("visto nell'app oggi alle 10:30");
    expect(groups[1]?.textContent).toContain("visto nell'app ieri alle 21:00");
    expect(groups[1]?.textContent).toContain("si vedrà dalla 1.4 in poi");
    // Sito da Android (Rosario 23/11): ultima visita sul sito, ricevono la notifica.
    expect(groups[2]?.textContent).toContain("Sito Android");
    expect(groups[2]?.textContent).toContain("visto sul sito da Android oggi alle 11:15");
    expect(groups[2]?.textContent).toContain("ricevono anche loro la notifica della nuova versione");
    expect(groups[3]?.textContent).toContain("non ricevono la notifica della nuova versione");
    expect(usersMock).toHaveBeenCalledWith("t");
  });

  it("un errore non nasconde il resto della pagina", async () => {
    usersMock.mockRejectedValue(new Error("Non hai i permessi."));
    configMock.mockResolvedValue({ android: ANNOUNCED });
    await act(async () => {
      root.render(createElement(AdminAppVersionPage));
    });
    const text = container.textContent ?? "";
    expect(text).toContain("Ora annunciata: 1.4.0 (versionCode 5).");
    expect(container.querySelector('[data-testid="admin-appversion-users"] [role="alert"]')?.textContent).toBe(
      "Non hai i permessi.",
    );
  });

  it("dopo il salvataggio l'elenco si rilegge", async () => {
    usersMock.mockResolvedValue(USAGE);
    configMock.mockResolvedValue({ android: ANNOUNCED });
    saveMock.mockResolvedValue({ android: ANNOUNCED, notifiedUsers: 0 });
    await act(async () => {
      root.render(createElement(AdminAppVersionPage));
    });
    expect(usersMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-testid="admin-appversion-save"]')?.click();
    });
    expect(saveMock).toHaveBeenCalledTimes(1);
    expect(usersMock).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain("Nessuna notifica nuova");
  });
});
