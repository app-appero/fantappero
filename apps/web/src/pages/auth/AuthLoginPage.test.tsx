import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAuthOptionsMock = vi.fn();
const loginMock = vi.fn();
const registerMock = vi.fn();
// Client id di Google: vuoto come in locale, oppure impostato come su dev e pilota.
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
import { AuthLoginPage } from "./AuthPages";

describe("AuthLoginPage — Google prima, email come alternativa", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function render(path = "/accedi") {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, { initialEntries: [path], children: createElement(AuthLoginPage) }),
      );
    });
  }
  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);
  const passwordField = () => container.querySelector('input[type="password"]');
  function expectPrivacyLink() {
    const notes = container.querySelectorAll('[data-testid="login-privacy-link"]');
    expect(notes).toHaveLength(1);
    expect(notes[0]?.textContent).toBe("Accedendo accetti l'informativa privacy.");
    expect(notes[0]?.querySelector('a[href="/privacy"]')?.textContent).toBe("informativa privacy");
  }
  const googleOnly = () => byTestId("login-google-only");
  const text = () => container.textContent ?? "";

  async function click(element: HTMLElement | null) {
    expect(element).not.toBeNull();
    await act(async () => {
      element?.click();
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

  async function submit() {
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
    loginMock.mockReset();
    registerMock.mockReset();
    googleClientId = "";
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
    // Con Google l'account si crea da solo: nessun testo esplicativo e nessun link «Registrati».
    expect(text()).not.toContain("solo con Google");
    expect(text()).not.toContain("Non hai un account");
    expect(container.querySelector('a[href="/accedi/registrati"]')).toBeNull();
    // Il tasto «Continua con Apple» è nascosto finché non c'è la versione iPhone.
    expect(byTestId("auth-apple-disabled")).toBeNull();
    expect(text()).not.toContain("Apple");
    expect(passwordField()).toBeNull();
    expect(container.querySelector("form")).toBeNull();
    expect(text()).not.toContain("Password dimenticata");
  });

  it("con la registrazione con email spenta non offre nessuna alternativa con email, nemmeno con Google", async () => {
    googleClientId = "client-id";
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render();
    expect(googleOnly()).not.toBeNull();
    expect(byTestId("auth-google-button")).not.toBeNull();
    expect(byTestId("auth-email-toggle")).toBeNull();
    expect(byTestId("auth-email-panel")).toBeNull();
    expect(byTestId("auth-email-divider")).toBeNull();
    expect(text()).not.toContain("Continua con email");
    expect(text()).not.toContain("oppure");
    // La pagina di oggi: nota su Google e informativa privacy.
    expect(text()).toContain("Niente password: un tocco e sei dentro");
    expect(byTestId("login-privacy-link")?.textContent).toContain("Accedendo accetti");
  });

  it("non mostra il modulo nemmeno mentre il server non ha ancora risposto", async () => {
    fetchAuthOptionsMock.mockReturnValue(new Promise(() => {}));
    await render();
    expect(passwordField()).toBeNull();
    expect(googleOnly()).not.toBeNull();
    expect(byTestId("auth-email-toggle")).toBeNull();
  });

  it("chi ha un account con password apre /accedi?accesso=email e ritrova il modulo", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render("/accedi?accesso=email");
    expect(passwordField()).not.toBeNull();
    expect(text()).toContain("Accedi con email");
    expect(googleOnly()).toBeNull();
    // Anche nell'accesso con email si vede il rimando all'informativa privacy.
    expectPrivacyLink();
  });

  it("con l'accesso solo Google il rimando all'informativa privacy resta", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: false });
    await render();
    expectPrivacyLink();
  });

  it("se non riesce a leggere le opzioni (server irraggiungibile) resta il solo accesso con Google", async () => {
    fetchAuthOptionsMock.mockRejectedValue(new Error("rete assente"));
    await render();
    expect(passwordField()).toBeNull();
    expect(googleOnly()).not.toBeNull();
  });

  it("con Google configurato l'alternativa con email è chiusa: oppure e «Continua con email»", async () => {
    googleClientId = "client-id";
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    expect(byTestId("auth-google-button")).not.toBeNull();
    expect(byTestId("auth-email-divider")?.textContent).toBe("oppure");
    expect(byTestId("auth-email-toggle")?.textContent).toBe("Continua con email");
    expect(byTestId("auth-email-panel")).toBeNull();
    expect(passwordField()).toBeNull();
    expect(container.querySelector("form")).toBeNull();
    expect(byTestId("login-privacy-link")?.textContent).toContain("Accedendo accetti");
    // La vecchia pagina con il modulo sempre aperto non compare più.
    expect(container.querySelector(".fa-login--home")).toBeNull();
    expect(text()).not.toContain("Accedi con email");
    // Google resta per primo: il tasto viene prima di «oppure» e di «Continua con email».
    const google = byTestId("auth-google-button");
    const toggle = byTestId("auth-email-toggle");
    expect(google && toggle && google.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("«Continua con email» apre nella stessa scheda il pannello su «Accedi», e «Chiudi» lo richiude", async () => {
    googleClientId = "client-id";
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();

    await click(byTestId("auth-email-toggle"));

    const panel = byTestId("auth-email-panel");
    expect(panel).not.toBeNull();
    expect(byTestId("login-email-option")?.contains(panel)).toBe(true);
    expect(byTestId("auth-email-toggle")).toBeNull();
    expect(byTestId("auth-email-tab-login")?.getAttribute("aria-selected")).toBe("true");
    expect(byTestId("auth-email-tab-register")?.getAttribute("aria-selected")).toBe("false");
    expect(container.querySelector('input[name="email"]')).not.toBeNull();
    expect(passwordField()).not.toBeNull();
    expect(container.querySelector('input[name="displayName"]')).toBeNull();
    expect(container.querySelector('button[type="submit"]')?.textContent).toBe("Accedi");
    expect(container.querySelector('a[href="/accedi/recupera"]')?.textContent).toBe("Password dimenticata?");
    // Una sola riga sull'informativa, quella del pannello.
    const privacy = container.querySelectorAll('[data-testid="login-privacy-link"]');
    expect(privacy).toHaveLength(1);
    expect(privacy[0]?.textContent).toContain("Accedendo accetti l'informativa privacy");
    expect(privacy[0]?.querySelector('a[href="/privacy"]')).not.toBeNull();

    await click(byTestId("auth-email-close"));

    expect(byTestId("auth-email-panel")).toBeNull();
    expect(byTestId("auth-email-toggle")).not.toBeNull();
    expect(passwordField()).toBeNull();
  });

  it("passa da «Accedi» a «Registrati» e ritorno", async () => {
    googleClientId = "client-id";
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    await click(byTestId("auth-email-toggle"));

    await click(byTestId("auth-email-tab-register"));

    expect(byTestId("auth-email-tab-register")?.getAttribute("aria-selected")).toBe("true");
    expect(container.querySelector('input[name="displayName"]')).not.toBeNull();
    expect(container.querySelector('input[name="email"]')).not.toBeNull();
    expect(passwordField()).not.toBeNull();
    // Niente conferma della password: nome, email, password e «Crea account».
    expect(container.querySelector('input[name="confirmPassword"]')).toBeNull();
    expect(container.querySelector('button[type="submit"]')?.textContent).toBe("Crea account");
    expect(text()).not.toContain("Password dimenticata");
    expect(byTestId("login-privacy-link")?.textContent).toContain("Registrandoti accetti l'informativa privacy");

    await click(byTestId("auth-email-tab-login"));

    expect(byTestId("auth-email-tab-login")?.getAttribute("aria-selected")).toBe("true");
    expect(container.querySelector('input[name="displayName"]')).toBeNull();
    expect(container.querySelector('button[type="submit"]')?.textContent).toBe("Accedi");
  });

  it("senza Google configurato (in locale) il pannello con email è già aperto", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render();
    expect(byTestId("auth-email-panel")).not.toBeNull();
    expect(byTestId("auth-email-toggle")).toBeNull();
    // Senza il tasto di Google non c'è nessun «oppure».
    expect(byTestId("auth-email-divider")).toBeNull();
    expect(passwordField()).not.toBeNull();
    expect(text()).toContain("Password dimenticata");
    expect(googleOnly()).toBeNull();
    expect(container.querySelector(".fa-login--home")).toBeNull();
  });

  it("con la registrazione accesa /accedi?accesso=email apre il pannello, non la vecchia pagina", async () => {
    googleClientId = "client-id";
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    await render("/accedi?accesso=email");
    expect(byTestId("auth-email-panel")).not.toBeNull();
    expect(byTestId("auth-email-tab-login")?.getAttribute("aria-selected")).toBe("true");
    expect(container.querySelector(".fa-login--home")).toBeNull();
  });

  it("accede con email e password", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    loginMock.mockResolvedValue(undefined);
    await render();
    await type("email", "lucia@example.com");
    await type("password", "Password123!");
    await submit();
    expect(loginMock).toHaveBeenCalledWith("lucia@example.com", "Password123!");
    expect(byTestId("auth-form-error")).toBeNull();
  });

  it("un non tester che accede con email vede la richiesta di accesso, come con Google", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    loginMock.mockRejectedValue(
      new ApiError("Non autorizzato: l'accesso è riservato ai tester del pilota.", 403, "tester_only", {
        requestStatus: "none",
        requestToken: "gettone",
        requestEmail: "lucia@example.com",
        requestName: "Lucia Bianchi",
        requestFirstName: null,
        requestLastName: null,
      }),
    );
    await render();
    await type("email", "lucia@example.com");
    await type("password", "Password123!");
    await submit();

    expect(byTestId("tester-request-page")).not.toBeNull();
    expect(byTestId("login-page")).toBeNull();
    const first = container.querySelector<HTMLInputElement>('input[data-testid="tester-request-first-name"]');
    const last = container.querySelector<HTMLInputElement>('input[data-testid="tester-request-last-name"]');
    expect(first?.value).toBe("Lucia");
    expect(last?.value).toBe("Bianchi");
    // L'account è quello con email, non Google.
    const account = byTestId("tester-request-account");
    expect(account?.textContent).toContain("lucia@example.com");
    expect(account?.textContent).not.toContain("Google");
    expect(text()).toContain("con la stessa email e password");
  });

  it("con password sbagliata resta sul modulo con l'errore", async () => {
    fetchAuthOptionsMock.mockResolvedValue({ emailRegistrationEnabled: true });
    loginMock.mockRejectedValue(new ApiError("Email o password non validi.", 401, "invalid_credentials"));
    await render();
    await type("email", "lucia@example.com");
    await type("password", "sbagliata");
    await submit();
    expect(byTestId("tester-request-page")).toBeNull();
    expect(byTestId("auth-form-error")?.textContent).toBe("Email o password non validi.");
  });
});
