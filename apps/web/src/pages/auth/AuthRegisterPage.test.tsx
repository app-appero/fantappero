import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAuthOptionsMock = vi.fn();
const registerMock = vi.fn();

vi.mock("../../api/auth", () => ({
  fetchAuthOptions: (...args: unknown[]) => fetchAuthOptionsMock(...args),
  register: (...args: unknown[]) => registerMock(...args),
}));
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ loginWithGoogle: vi.fn() }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../../config/env", () => ({
  getWebEnv: () => ({ viteGoogleClientId: "" }),
}));
vi.mock("../../auth/googleIdentity", () => ({
  renderGoogleButton: vi.fn(() => Promise.resolve()),
}));

import { MemoryRouter } from "../../router/simpleRouter";
import { AuthRegisterPage } from "./AuthPages";

describe("AuthRegisterPage — registrazione solo con Google nel pilota", () => {
  let container: HTMLDivElement;
  let root: Root;

  const text = () => container.textContent ?? "";
  const hasField = (name: string) => container.textContent?.includes(name) ?? false;

  async function render() {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/accedi/registrati"],
          children: createElement(AuthRegisterPage),
        }),
      );
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchAuthOptionsMock.mockReset();
    registerMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("con la registrazione con email spenta mostra solo Google e nessun modulo", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render();
    expect(container.querySelector('[data-testid="register-google-only"]')).not.toBeNull();
    // Nessun testo né link: con Google si accede e ci si registra nello stesso gesto.
    expect(text()).not.toContain("solo con Google");
    expect(text()).not.toContain("Hai già un account");
    // Il tasto «Continua con Apple» è nascosto finché non c'è la versione iPhone.
    expect(container.querySelector('[data-testid="auth-apple-disabled"]')).toBeNull();
    expect(container.textContent).not.toContain("Apple");
    expect(text()).toContain("Continua con Google");
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(hasField("Crea account con email")).toBe(false);
    // I passi non parlano più di email da confermare.
    expect(text()).not.toContain("Conferma l'email");
    expect(container.querySelector('a[href="/accedi"]')).toBeNull();
  });

  it("non mostra il modulo con email nemmeno mentre il server non ha ancora risposto", async () => {
    fetchAuthOptionsMock.mockReturnValue(new Promise(() => {}));
    await render();
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('[data-testid="register-google-only"]')).not.toBeNull();
  });

  it("con la registrazione con email attiva mostra il modulo completo", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    expect(container.querySelector("form")).not.toBeNull();
    expect(container.querySelector('input[type="password"]')).not.toBeNull();
    expect(text()).toContain("Crea account con email");
    expect(container.querySelector('[data-testid="register-google-only"]')).toBeNull();
  });

  it("se non riesce a leggere le opzioni (server irraggiungibile) resta il solo Google", async () => {
    fetchAuthOptionsMock.mockRejectedValue(new Error("rete assente"));
    await render();
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('[data-testid="register-google-only"]')).not.toBeNull();
  });
});
