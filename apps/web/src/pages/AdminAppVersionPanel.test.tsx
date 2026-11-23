import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();
const saveMock = vi.fn();

vi.mock("../api/admin", () => ({
  fetchAppVersionConfig: (...args: unknown[]) => fetchMock(...args),
  saveAppVersionConfig: (...args: unknown[]) => saveMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "t", refreshToken: "r", user: { id: "u" } }),
}));

import { AdminAppVersionPanel } from "./AdminAppVersionPanel";

const SAVED = {
  latestVersionName: "1.3.0",
  latestVersionCode: 4,
  downloadUrl: "https://drive.google.com/drive/folders/prova",
  message: null,
};

function setValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("AdminAppVersionPanel", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchMock.mockReset();
    saveMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function render() {
    await act(async () => {
      root.render(createElement(AdminAppVersionPanel));
    });
  }

  function field(name: string): HTMLInputElement {
    const input = container.querySelector<HTMLInputElement>(`input[name="${name}"]`);
    expect(input).not.toBeNull();
    return input as HTMLInputElement;
  }

  async function submit() {
    await act(async () => {
      container
        .querySelector<HTMLButtonElement>('[data-testid="admin-appversion-save"]')
        ?.click();
    });
  }

  it("senza versione impostata spiega che non c'è avviso e mostra il suggerimento", async () => {
    fetchMock.mockResolvedValue({ android: null });
    await render();
    const text = container.textContent ?? "";
    expect(text).toContain("Versione dell'app Android");
    expect(text).toContain(
      "Quando pubblichi un nuovo APK, aggiorna qui versione e link: chi usa l'app Android o il sito da Android e non ha ancora quella versione riceve una notifica (nell'elenco e push) e, a ogni ingresso nell'app, l'avviso con «Scarica».",
    );
    expect(text).toContain("Nessuna versione impostata");
    expect(field("app-version-name").value).toBe("");
  });

  it("salva versione, versionCode, link e messaggio", async () => {
    fetchMock.mockResolvedValue({ android: null });
    saveMock.mockResolvedValue({ android: { ...SAVED, message: "Più veloce" }, notifiedUsers: 7 });
    await render();
    await act(async () => {
      setValue(field("app-version-name"), " 1.3.0 ");
      setValue(field("app-version-code"), "4");
      setValue(field("app-version-url"), "https://drive.google.com/drive/folders/prova");
      setValue(field("app-version-message"), "Più veloce");
    });
    await submit();
    expect(saveMock).toHaveBeenCalledWith("t", {
      latestVersionName: "1.3.0",
      latestVersionCode: 4,
      downloadUrl: "https://drive.google.com/drive/folders/prova",
      message: "Più veloce",
    });
    const text = container.textContent ?? "";
    // Release 1.4: il salvataggio dice a quanti è partita la notifica.
    expect(text).toContain(
      "Versione salvata: notifica inviata a 7 utenti che non hanno ancora questa versione.",
    );
    expect(text).toContain("Ora annunciata: 1.3.0 (versionCode 4).");
  });

  it("parte dai valori salvati e non invia un link senza https o un versionCode non valido", async () => {
    fetchMock.mockResolvedValue({ android: SAVED });
    await render();
    expect(field("app-version-name").value).toBe("1.3.0");
    expect(field("app-version-code").value).toBe("4");
    await act(async () => {
      setValue(field("app-version-url"), "http://drive.google.com/apk");
      setValue(field("app-version-code"), "0");
    });
    await submit();
    expect(saveMock).not.toHaveBeenCalled();
    const text = container.textContent ?? "";
    expect(text).toContain("Il link deve iniziare con https://");
    expect(text).toContain("Il versionCode è un numero intero maggiore di zero.");
  });

  it("mostra l'errore del server", async () => {
    fetchMock.mockResolvedValue({ android: SAVED });
    saveMock.mockRejectedValue(new Error("Dati non validi: downloadUrl."));
    await render();
    await submit();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "Dati non validi: downloadUrl.",
    );
  });
});
