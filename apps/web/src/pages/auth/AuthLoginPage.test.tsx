import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAuthOptionsMock = vi.fn();

vi.mock("../../api/auth", () => ({
  fetchAuthOptions: (...args: unknown[]) => fetchAuthOptionsMock(...args),
}));
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ login: vi.fn(), loginWithGoogle: vi.fn() }),
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
import { AuthLoginPage } from "./AuthPages";

describe("AuthLoginPage — accesso solo con Google nel pilota", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function render(path = "/accedi") {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, { initialEntries: [path], children: createElement(AuthLoginPage) }),
      );
    });
  }
  const passwordField = () => container.querySelector('input[type="password"]');
  const googleOnly = () => container.querySelector('[data-testid="login-google-only"]');

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchAuthOptionsMock.mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("con la registrazione con email spenta non mostra il modulo email e password", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render();
    expect(googleOnly()).not.toBeNull();
    expect(container.textContent).toContain("si accede solo con Google");
    // Il tasto «Continua con Apple» è nascosto finché non c'è la versione iPhone.
    expect(container.querySelector('[data-testid="auth-apple-disabled"]')).toBeNull();
    expect(container.textContent).not.toContain("Apple");
    expect(passwordField()).toBeNull();
    expect(container.querySelector("form")).toBeNull();
    expect(container.textContent).not.toContain("Password dimenticata");
    expect(container.querySelector('a[href="/accedi/registrati"]')).not.toBeNull();
  });

  it("non mostra il modulo nemmeno mentre il server non ha ancora risposto", async () => {
    fetchAuthOptionsMock.mockReturnValue(new Promise(() => {}));
    await render();
    expect(passwordField()).toBeNull();
    expect(googleOnly()).not.toBeNull();
  });

  it("chi ha un account con password apre /accedi?accesso=email e ritrova il modulo", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render("/accedi?accesso=email");
    expect(passwordField()).not.toBeNull();
    expect(container.textContent).toContain("Accedi con email");
    expect(googleOnly()).toBeNull();
  });

  it("con la registrazione con email attiva mostra il modulo come prima", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    expect(passwordField()).not.toBeNull();
    expect(container.textContent).toContain("Password dimenticata");
    expect(googleOnly()).toBeNull();
  });

  it("se non riesce a leggere le opzioni ripiega sul modulo (nessuno resta bloccato)", async () => {
    fetchAuthOptionsMock.mockRejectedValue(new Error("rete assente"));
    await render();
    expect(passwordField()).not.toBeNull();
  });
});
