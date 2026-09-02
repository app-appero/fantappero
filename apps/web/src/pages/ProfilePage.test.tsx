import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { AppRoutes } from "../routes";
import { MemoryRouter } from "../router/simpleRouter";

vi.mock("../api/auth", () => ({
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

vi.mock("../api/profile", () => ({
  fetchProfile: vi.fn(),
  updateProfile: vi.fn(),
  uploadAvatar: vi.fn(),
  removeAvatar: vi.fn(),
  recordPolicyConsent: vi.fn(),
}));

vi.mock("../api/privacy", () => ({
  exportAccountData: vi.fn(),
  deleteAccount: vi.fn(),
}));

function renderProfile(path = "/profilo?persona") {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [path],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

describe("EP02-02 profile page", () => {
  it("renders demo profile form with preferences", () => {
    const html = renderProfile();
    expect(html).toContain('data-testid="profile-form"');
    expect(html).toContain("Nome visualizzato");
    expect(html).toContain("Fuso orario");
    expect(html).toContain('data-testid="profile-notifications-email"');
  });

  it("shows accepted policy in demo mode", () => {
    const html = renderProfile();
    expect(html).toContain('data-testid="profile-policy-accepted"');
  });

  it("renders privacy data rights controls in demo mode", () => {
    const html = renderProfile();
    expect(html).toContain('data-testid="profile-privacy-actions"');
    expect(html).toContain('data-testid="profile-export-data"');
    expect(html).toContain('data-testid="profile-delete-submit"');
    expect(html).toContain("Esporta i miei dati");
    expect(html).toContain("Elimina il mio account");
  });

  it("renders loading state for authenticated non-demo without session", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/profilo"],
        children: createElement(AuthProvider, {
          children: createElement(AppRoutes),
        }),
      }),
    );
    expect(html).toContain('data-testid="auth-redirect"');
  });
});
