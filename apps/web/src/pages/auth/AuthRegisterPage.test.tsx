import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAuthOptionsMock = vi.fn();
const registerMock = vi.fn();
const loginMock = vi.fn();
let googleClientId = "";

vi.mock("../../api/auth", () => ({
  fetchAuthOptions: (...args: unknown[]) => fetchAuthOptionsMock(...args),
  register: (...args: unknown[]) => registerMock(...args),
  submitTesterRequest: vi.fn(),
}));
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ login: loginMock, loginWithGoogle: vi.fn() }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../../config/env", () => ({
  getWebEnv: () => ({ viteGoogleClientId: googleClientId }),
}));
vi.mock("../../auth/googleIdentity", () => ({
  renderGoogleButton: vi.fn(() => Promise.resolve()),
}));

import { ApiError } from "../../api/client";
import { MemoryRouter } from "../../router/simpleRouter";
import { AuthRegisterPage } from "./AuthPages";

describe("AuthRegisterPage — /accedi/registrati", () => {
  let container: HTMLDivElement;
  let root: Root;

  const text = () => container.textContent ?? "";
  const hasField = (name: string) => container.textContent?.includes(name) ?? false;
  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

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

  async function type(name: string, value: string) {
    const input = container.querySelector<HTMLInputElement>(`input[name="${name}"]`);
    expect(input).not.toBeNull();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setter?.call(input, value);
      input?.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  async function fillAndSubmit() {
    await type("displayName", "Lucia Bianchi");
    await type("email", "lucia@example.com");
    await type("password", "Password123!");
    const form = container.querySelector<HTMLFormElement>('[data-testid="auth-form-layout"]');
    expect(form).not.toBeNull();
    await act(async () => {
      form?.requestSubmit();
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchAuthOptionsMock.mockReset();
    registerMock.mockReset();
    loginMock.mockReset();
    googleClientId = "";
    window.localStorage.clear();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("con la registrazione con email spenta mostra solo Google e nessun modulo", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render();
    expect(byTestId("register-google-only")).not.toBeNull();
    // Nessun testo né link: con Google si accede e ci si registra nello stesso gesto.
    expect(text()).not.toContain("solo con Google");
    expect(text()).not.toContain("Hai già un account");
    // Il tasto «Continua con Apple» è nascosto finché non c'è la versione iPhone.
    expect(byTestId("auth-apple-disabled")).toBeNull();
    expect(container.textContent).not.toContain("Apple");
    expect(text()).toContain("Continua con Google");
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(hasField("Crea account")).toBe(false);
    expect(byTestId("auth-email-toggle")).toBeNull();
    // I passi non parlano più di email da confermare.
    expect(text()).not.toContain("Conferma l'email");
    expect(container.querySelector('a[href="/accedi"]')).toBeNull();
    expect(container.querySelector('[data-testid="register-privacy-link"]')).toBeNull();
  });

  it("non mostra il modulo con email nemmeno mentre il server non ha ancora risposto", async () => {
    fetchAuthOptionsMock.mockReturnValue(new Promise(() => {}));
    await render();
    expect(container.querySelector("form")).toBeNull();
    expect(byTestId("register-google-only")).not.toBeNull();
  });

  it("con la registrazione con email attiva apre la pagina di accesso sulla scheda «Registrati», anche con Google", async () => {
    googleClientId = "client-id";
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    expect(byTestId("login-page")).not.toBeNull();
    expect(byTestId("auth-google-button")).not.toBeNull();
    expect(byTestId("auth-email-panel")).not.toBeNull();
    expect(byTestId("auth-email-toggle")).toBeNull();
    expect(byTestId("auth-email-tab-register")?.getAttribute("aria-selected")).toBe("true");
    expect(container.querySelector('input[name="displayName"]')).not.toBeNull();
    expect(container.querySelector('input[type="password"]')).not.toBeNull();
    expect(container.querySelector('button[type="submit"]')?.textContent).toBe("Crea account");
    expect(byTestId("login-privacy-link")?.textContent).toContain("Registrandoti accetti");
    expect(byTestId("register-google-only")).toBeNull();
  });

  it("nella scheda «Registrati» la password è nuova (autocomplete new-password), in «Accedi» quella attuale", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    const password = () => container.querySelector<HTMLInputElement>('input[name="password"]');
    expect(byTestId("auth-email-tab-register")?.getAttribute("aria-selected")).toBe("true");
    expect(password()?.getAttribute("autocomplete")).toBe("new-password");

    await act(async () => {
      byTestId("auth-email-tab-login")?.click();
    });
    expect(byTestId("auth-email-tab-login")?.getAttribute("aria-selected")).toBe("true");
    expect(password()?.getAttribute("autocomplete")).toBe("current-password");
  });

  it("se non riesce a leggere le opzioni (server irraggiungibile) resta il solo Google", async () => {
    fetchAuthOptionsMock.mockRejectedValue(new Error("rete assente"));
    await render();
    expect(container.querySelector("form")).toBeNull();
    expect(byTestId("register-google-only")).not.toBeNull();
  });

  it("con la verifica email spenta, dopo la registrazione entra subito", async () => {
    fetchAuthOptionsMock.mockResolvedValue({
      emailRegistrationEnabled: true,
      emailVerificationRequired: false,
    });
    registerMock.mockResolvedValue({ message: "Registrazione completata: ora puoi accedere." });
    loginMock.mockResolvedValue(undefined);
    await render();
    await fillAndSubmit();

    expect(registerMock).toHaveBeenCalledWith({
      email: "lucia@example.com",
      password: "Password123!",
      displayName: "Lucia Bianchi",
    });
    expect(loginMock).toHaveBeenCalledWith("lucia@example.com", "Password123!");
    expect(byTestId("auth-register-success")).toBeNull();
    expect(byTestId("auth-form-error")).toBeNull();
  });

  it("con la verifica email spenta un non tester appena registrato vede la richiesta di accesso", async () => {
    fetchAuthOptionsMock.mockResolvedValue({
      emailRegistrationEnabled: true,
      emailVerificationRequired: false,
    });
    registerMock.mockResolvedValue({ message: "Registrazione completata: ora puoi accedere." });
    loginMock.mockRejectedValue(
      new ApiError("Non autorizzato", 403, "tester_only", {
        requestStatus: "none",
        requestToken: "gettone",
        requestEmail: "lucia@example.com",
        requestName: "Lucia Bianchi",
      }),
    );
    await render();
    await fillAndSubmit();

    expect(byTestId("tester-request-page")).not.toBeNull();
    expect(byTestId("tester-request-account")?.textContent).toContain("lucia@example.com");
  });

  it("se l'indirizzo aveva già un account con un'altra password passa ad «Accedi» con l'avviso", async () => {
    fetchAuthOptionsMock.mockResolvedValue({
      emailRegistrationEnabled: true,
      emailVerificationRequired: false,
    });
    registerMock.mockResolvedValue({ message: "Registrazione completata: ora puoi accedere." });
    loginMock.mockRejectedValue(new ApiError("Email o password non validi.", 401, "invalid_credentials"));
    await render();
    await fillAndSubmit();

    expect(byTestId("auth-email-tab-login")?.getAttribute("aria-selected")).toBe("true");
    expect(byTestId("auth-form-error")?.textContent).toContain("se avevi già un account");
    expect(container.querySelector<HTMLInputElement>('input[name="email"]')?.value).toBe("lucia@example.com");
    expect(container.querySelector<HTMLInputElement>('input[name="password"]')?.value).toBe("");
  });

  it("con la verifica email accesa chiede di controllare la posta e non entra", async () => {
    fetchAuthOptionsMock.mockResolvedValue({
      emailRegistrationEnabled: true,
      emailVerificationRequired: true,
    });
    registerMock.mockResolvedValue({
      message: "Se l'indirizzo email è valido, riceverai un messaggio con le istruzioni.",
    });
    await render();
    await fillAndSubmit();

    expect(byTestId("auth-register-success")?.textContent).toContain("Controlla la tua email");
    expect(loginMock).not.toHaveBeenCalled();
  });
});
