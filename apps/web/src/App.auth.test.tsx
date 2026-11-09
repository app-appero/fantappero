import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
import { GoogleAppHandoffLink } from "./pages/auth/AuthPages";
import { AppRoutes } from "./routes";
import { MemoryRouter } from "./router/simpleRouter";

vi.mock("./api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  fetchMe: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  resendVerification: vi.fn(),
}));

function renderAuth(path: string) {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

describe("EP02-01 auth pages", () => {
  it("renders the Google-only login before the server options are known", () => {
    // Il modulo email e password compare solo se il server lo consente (nel pilota è spento):
    // la sua presenza è coperta da AuthLoginPage.test.tsx.
    const html = renderAuth("/accedi");
    expect(html).toContain('data-testid="login-google-only"');
    expect(html).not.toContain('data-testid="auth-form-layout"');
    expect(html).not.toContain("/accedi/recupera");
    expect(html).not.toContain('data-testid="app-shell"');
  });

  it("rejects a google handoff without an app return url", () => {
    const html = renderAuth("/accedi/google-app");
    expect(html).toContain("Collegamento non valido");
    expect(html).not.toContain('data-testid="app-shell"');
  });

  it("renders the mobile google handoff for an app return url", () => {
    const html = renderAuth("/accedi/google-app?return=fantappero%3A%2F%2Fgoogle-auth");
    expect(html).toContain("Continua con Google per tornare all&#x27;app.");
    expect(html).not.toContain("Collegamento non valido");
  });

  it("offers a link back to the app after the one-time pickup code", () => {
    const html = renderToStaticMarkup(
      createElement(GoogleAppHandoffLink, {
        href: "fantappero://google-auth?code=one-time-code",
      }),
    );
    expect(html).toContain("Apri FantApperò");
    expect(html).toContain('href="fantappero://google-auth?code=one-time-code"');
  });

  it("renders the Google-only registration before the server options are known", () => {
    // Nel pilota la registrazione con email è spenta: finché le opzioni non arrivano dal server
    // non si mostra il modulo. Il modulo completo, quando attivo, è coperto da AuthRegisterPage.test.tsx.
    const html = renderAuth("/accedi/registrati");
    expect(html).toContain('data-testid="register-google-only"');
    expect(html).not.toContain("solo con Google");
    expect(html).not.toContain('name="displayName"');
  });

  it("renders forgot password form at /accedi/recupera", () => {
    const html = renderAuth("/accedi/recupera");
    expect(html).toContain("Password dimenticata");
    expect(html).not.toContain('name="password"');
  });

  it("renders reset password form when token is present", () => {
    const html = renderAuth("/accedi/reimposta-password?token=abc");
    expect(html).toContain("Scegli una nuova password");
    expect(html).toContain('name="confirmPassword"');
  });

  it("renders logout control in authenticated app shell", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/leghe?persona=admin&stato=success"],
        children: createElement(AuthProvider, {
          children: createElement(AppRoutes),
        }),
      }),
    );
    expect(html).toContain('data-testid="logout-button"');
    expect(html).toContain("Esci");
  });
});
