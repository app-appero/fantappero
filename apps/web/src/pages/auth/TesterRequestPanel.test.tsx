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

import { TesterRequestPanel } from "./TesterRequestPanel";

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
    expect(text).toContain("gruppo WhatsApp dei tester");
    const submit = container.querySelector<HTMLButtonElement>('[data-testid="tester-request-submit"]');
    expect(submit?.disabled).toBe(true);
  });

  it("in valutazione e rifiutata mostra solo il messaggio, senza modulo", async () => {
    await render({ status: "pending", submittedAt: "2026-11-13T10:00:00Z" });
    expect(container.querySelector('[data-testid="tester-request-pending"]')).not.toBeNull();
    expect(container.querySelector("form")).toBeNull();
    await render({ status: "rejected" });
    expect(container.querySelector('[data-testid="tester-request-rejected"]')).not.toBeNull();
  });
});
