import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createBroadcastMock = vi.fn();

vi.mock("../api/notifications", () => ({
  createBroadcast: (...args: unknown[]) => createBroadcastMock(...args),
  fetchBroadcasts: vi.fn(),
  fetchNotificationRecipients: vi.fn(),
  fetchTestSamples: vi.fn(),
  sendTestSamples: vi.fn(),
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token-op", user: { id: "op-1" } }),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

import { ComposeTab } from "./AdminNotificationsPage";

const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype,
  "value",
)!.set!;
const nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(
  window.HTMLTextAreaElement.prototype,
  "value",
)!.set!;

/** «Invia a N utenti» chiede «Sei sicuro?» con il numero di destinatari (release 1.5). */
describe("AdminNotificationsPage — conferma prima di inviare a tutti (1.5)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function click(id: string) {
    const element = byTestId(id);
    expect(element, id).not.toBeNull();
    await act(async () => {
      element!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
  }

  async function write(id: string, value: string) {
    const element = byTestId(id) as HTMLInputElement | HTMLTextAreaElement | null;
    expect(element, id).not.toBeNull();
    await act(async () => {
      const setter = element instanceof HTMLTextAreaElement ? nativeTextareaValueSetter : nativeInputValueSetter;
      setter.call(element, value);
      element!.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  beforeEach(async () => {
    createBroadcastMock.mockReset();
    createBroadcastMock.mockResolvedValue({ status: "sent", recipientCount: 40, pushCount: 31 });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(createElement(ComposeTab));
    });
    await write("admin-notifications-title", "Nuova versione");
    await write("admin-notifications-body", "Aggiorna l'app.");
    await click("admin-notifications-audience-all");
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("«Invia» apre «Sei sicuro?» con i destinatari e non invia", async () => {
    await click("admin-notifications-send");

    expect(container.querySelector('[role="dialog"]')?.textContent).toContain("Sei sicuro?");
    expect(byTestId("admin-notifications-confirm-text")?.textContent).toBe(
      "Stai per inviare la notifica «Nuova versione» a tutti gli utenti. Canali: App + push. Dopo l'invio non si può annullare.",
    );
    expect(byTestId("admin-notifications-confirm-send")?.textContent).toBe("Invia");
    expect(byTestId("admin-notifications-confirm-cancel")?.textContent).toBe("Annulla");
    expect(createBroadcastMock).not.toHaveBeenCalled();
  });

  it("«Annulla» chiude la finestra senza inviare", async () => {
    await click("admin-notifications-send");
    await click("admin-notifications-confirm-cancel");

    expect(byTestId("admin-notifications-confirm-text")).toBeNull();
    expect(createBroadcastMock).not.toHaveBeenCalled();
    expect(byTestId("admin-notifications-done")).toBeNull();
  });

  it("la conferma invia la notifica a tutti", async () => {
    await click("admin-notifications-send");
    await click("admin-notifications-confirm-send");

    expect(createBroadcastMock).toHaveBeenCalledTimes(1);
    const [, body] = createBroadcastMock.mock.calls[0] ?? [];
    expect(body).toMatchObject({
      title: "Nuova versione",
      audience: { mode: "all" },
      channels: { inApp: true, push: true, email: false },
    });
    expect(byTestId("admin-notifications-confirm-text")).toBeNull();
    expect(byTestId("admin-notifications-done")?.textContent).toBe(
      "Inviata a 40 utenti (31 con push).",
    );
  });

  it("senza titolo la finestra non si apre e compare l'errore", async () => {
    await write("admin-notifications-title", "");
    await click("admin-notifications-send");

    expect(byTestId("admin-notifications-confirm-text")).toBeNull();
    expect(byTestId("admin-notifications-error")?.textContent).toContain(
      "Titolo e testo sono obbligatori.",
    );
    expect(createBroadcastMock).not.toHaveBeenCalled();
  });

  it("«Invia a me come prova» non chiede conferma", async () => {
    await click("admin-notifications-send-me");

    expect(byTestId("admin-notifications-confirm-text")).toBeNull();
    expect(createBroadcastMock).toHaveBeenCalledTimes(1);
    const [, body] = createBroadcastMock.mock.calls[0] ?? [];
    expect(body).toMatchObject({ kind: "test", audience: { mode: "users", userIds: ["op-1"] } });
  });

  it("con un solo destinatario l'esito dice «1 utente», non «1 utenti» (QA 28/11)", async () => {
    createBroadcastMock.mockResolvedValue({ status: "sent", recipientCount: 1, pushCount: 0 });
    await click("admin-notifications-send-me");

    expect(byTestId("admin-notifications-done")?.textContent).toBe(
      "Inviata a 1 utente (0 con push).",
    );
  });
});
