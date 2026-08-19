import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
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
  it("renders login form at /accedi", () => {
    const html = renderAuth("/accedi");
    expect(html).toContain('data-testid="auth-form-layout"');
    expect(html).toContain("Accedi al tuo account");
    expect(html).toContain("/accedi/recupera");
    expect(html).not.toContain('data-testid="app-shell"');
  });

  it("renders register form at /accedi/registrati", () => {
    const html = renderAuth("/accedi/registrati");
    expect(html).toContain("Crea account");
    expect(html).toContain('name="displayName"');
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
