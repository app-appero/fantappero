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

  function dialog(): HTMLElement | null {
    return container.querySelector<HTMLElement>('[role="dialog"]');
  }

  async function click(testId: string) {
    await act(async () => {
      container.querySelector<HTMLButtonElement>(`[data-testid="${testId}"]`)?.click();
    });
  }

  async function fillVersion14() {
    await act(async () => {
      setValue(field("app-version-name"), "1.4.0");
      setValue(field("app-version-code"), "5");
      setValue(field("app-version-url"), "https://drive.google.com/drive/folders/fantappero-1-4");
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
    // Prima la conferma, poi il salvataggio.
    expect(saveMock).not.toHaveBeenCalled();
    await click("admin-appversion-confirm");
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
    await click("admin-appversion-confirm");
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "Dati non validi: downloadUrl.",
    );
  });

  describe("«Sei sicuro?» prima di salvare (Rosario 23/11)", () => {
    it("chiede conferma in un dialogo accessibile; «Annulla» non salva nulla", async () => {
      fetchMock.mockResolvedValue({ android: SAVED });
      await render();
      await fillVersion14();
      await submit();

      const shown = dialog();
      expect(shown).not.toBeNull();
      expect(shown?.getAttribute("aria-modal")).toBe("true");
      const titleId = shown?.getAttribute("aria-labelledby") ?? "";
      expect(document.getElementById(titleId)?.textContent).toBe(
        "Annunciare la versione 1.4.0 (versionCode 5)?",
      );
      expect(shown?.textContent).toContain(
        "Tutti gli utenti che usano l'app Android (o il sito da un telefono Android) e non hanno ancora questa versione riceveranno una notifica; nell'app vedranno anche l'avviso di aggiornamento.",
      );
      const buttons = [...(shown?.querySelectorAll("footer button") ?? [])].map(
        (button) => button.textContent,
      );
      expect(buttons).toEqual(["Annulla", "Annuncia"]);
      // Il focus va nel dialogo.
      expect(document.activeElement).toBe(shown);

      await click("admin-appversion-confirm-cancel");
      expect(dialog()).toBeNull();
      expect(saveMock).not.toHaveBeenCalled();
      expect(container.textContent).toContain("Ora annunciata: 1.3.0 (versionCode 4).");
      // I campi restano come scritti, per correggerli o riprovare.
      expect(field("app-version-code").value).toBe("5");
    });

    it("«Annuncia» salva la versione scritta e chiude il dialogo", async () => {
      fetchMock.mockResolvedValue({ android: SAVED });
      const announced = {
        latestVersionName: "1.4.0",
        latestVersionCode: 5,
        downloadUrl: "https://drive.google.com/drive/folders/fantappero-1-4",
        message: null,
      };
      saveMock.mockResolvedValue({ android: announced, notifiedUsers: 3 });
      await render();
      await fillVersion14();
      await submit();
      await click("admin-appversion-confirm");

      expect(dialog()).toBeNull();
      expect(saveMock).toHaveBeenCalledTimes(1);
      expect(saveMock).toHaveBeenCalledWith("t", announced);
      expect(container.textContent).toContain(
        "Versione salvata: notifica inviata a 3 utenti che non hanno ancora questa versione.",
      );
    });

    it("Esc chiude il dialogo senza salvare", async () => {
      fetchMock.mockResolvedValue({ android: SAVED });
      await render();
      await fillVersion14();
      await submit();
      await act(async () => {
        dialog()?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      });
      expect(dialog()).toBeNull();
      expect(saveMock).not.toHaveBeenCalled();
    });

    it("stesso versionCode già annunciato: la conferma dice che la notifica non riparte", async () => {
      fetchMock.mockResolvedValue({ android: SAVED });
      saveMock.mockResolvedValue({ android: SAVED, notifiedUsers: 0 });
      await render();
      await submit();
      const shown = dialog();
      expect(shown?.textContent).toContain("Salvare le modifiche alla versione 1.3.0 (versionCode 4)?");
      expect(shown?.textContent).toContain("la notifica non parte di nuovo");
      expect(
        container.querySelector('[data-testid="admin-appversion-confirm"]')?.textContent,
      ).toBe("Salva");
      await click("admin-appversion-confirm");
      expect(saveMock).toHaveBeenCalledTimes(1);
    });

    it("con un campo non valido non chiede conferma", async () => {
      fetchMock.mockResolvedValue({ android: null });
      await render();
      await submit();
      expect(dialog()).toBeNull();
      expect(saveMock).not.toHaveBeenCalled();
    });
  });
});
