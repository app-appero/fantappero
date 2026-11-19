import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const submitMock = vi.fn();

vi.mock("../../api/auth", () => ({
  submitTesterRequest: (...args: unknown[]) => submitMock(...args),
}));
vi.mock("../../auth/AuthContext", () => ({
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { ApiError } from "../../api/client";
import { TesterRequestPanel, testerGateFromError } from "./TesterRequestPanel";

describe("TesterRequestPanel — richiesta di accesso al pilota", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function render(info: Parameters<typeof TesterRequestPanel>[0]["info"]) {
    await act(async () => {
      root.render(createElement(TesterRequestPanel, { info, onBack: vi.fn() }));
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    submitMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("mostra il modulo con la nota sul telefono e blocca l'invio senza consenso", async () => {
    await render({ status: "none", requestToken: "tok" });
    const text = container.textContent ?? "";
    expect(text).toContain("chat WhatsApp dei tester");
    const phone = container.querySelector<HTMLInputElement>('[data-testid="tester-request-phone"] input, input[data-testid="tester-request-phone"]');
    expect(phone?.required ?? false).toBe(false);
    const submit = container.querySelector<HTMLButtonElement>('[data-testid="tester-request-submit"]');
    expect(submit?.disabled).toBe(true);
  });

  it("precompila nome e cognome con quelli separati di Google", async () => {
    await render({
      status: "none",
      requestToken: "tok",
      name: "Maria Rosa De Luca",
      firstName: "Maria Rosa",
      lastName: "De Luca",
    });
    const first = container.querySelector<HTMLInputElement>('input[data-testid="tester-request-first-name"], [data-testid="tester-request-first-name"] input');
    const last = container.querySelector<HTMLInputElement>('input[data-testid="tester-request-last-name"], [data-testid="tester-request-last-name"] input');
    expect(first?.value).toBe("Maria Rosa");
    expect(last?.value).toBe("De Luca");
  });

  it("per chi accede con email i testi non parlano di Google", async () => {
    await render({ status: "none", requestToken: "tok", email: "lucia@example.com", provider: "email" });
    expect(container.querySelector('[data-testid="tester-request-account"]')?.textContent).not.toContain("Google");
    expect(container.textContent).toContain("entri con la stessa email e password");
    await render({ status: "pending", email: "lucia@example.com", provider: "email" });
    expect(container.textContent).toContain("potrai accedere con la stessa email e password");
    expect(container.textContent).not.toContain("Google");
  });

  it("in valutazione e rifiutata mostra solo il messaggio, senza modulo", async () => {
    await render({ status: "pending", submittedAt: "2026-11-13T10:00:00Z" });
    expect(container.querySelector('[data-testid="tester-request-pending"]')).not.toBeNull();
    expect(container.querySelector("form")).toBeNull();
    await render({ status: "rejected" });
    expect(container.querySelector('[data-testid="tester-request-rejected"]')).not.toBeNull();
  });

  it("riconosce il rifiuto tester_only e ne estrae il gettone", () => {
    const error = new ApiError("Non autorizzato", 403, "tester_only", {
      requestStatus: "none",
      requestToken: "tok",
    });
    expect(testerGateFromError(error)).toEqual({
      status: "none",
      requestToken: "tok",
      submittedAt: undefined,
    });
    expect(testerGateFromError(new ApiError("x", 400, "altro"))).toBeNull();
    expect(testerGateFromError(new Error("rete"))).toBeNull();
  });
});
