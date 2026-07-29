import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type {
  AuthSessionResponse,
  CompetitionResponse,
  LeagueResponse,
  MessageResponse,
  UserDataExportResponse,
  UserProfileResponse,
} from "@fantappero/contracts";
import { AuthApp } from "./auth/AuthApp";
import { CreateLeaguePanel } from "./leagues/CreateLeaguePanel";
import { ProfilePanel } from "./profile/ProfilePanel";
import { PrivacyPanel } from "./profile/PrivacyPanel";
import type { AuthClient } from "./api/auth";
import type { LeagueClient } from "./api/leagues";

const session: AuthSessionResponse = {
  access_token: "token-123",
  token_type: "bearer",
  expires_at: "2026-07-28T12:00:00Z",
};

const profile: UserProfileResponse = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "player@example.com",
  email_verified: false,
  created_at: "2026-07-28T10:00:00Z",
  display_name: null,
  avatar_url: null,
  language: "it",
  timezone: "Europe/Rome",
  notifications: { email: true, push: true },
  policy_consent_at: null,
  policy_version: null,
};

const exportBundle: UserDataExportResponse = {
  format_version: "2026-01",
  exported_at: "2026-07-29T10:00:00Z",
  account: {
    id: profile.id,
    email: profile.email,
    email_verified: false,
    created_at: profile.created_at,
    deleted_at: null,
  },
  profile: {
    display_name: null,
    language: "it",
    timezone: "Europe/Rome",
    notifications_email: true,
    notifications_push: true,
    policy_consent_at: null,
    policy_version: null,
    avatar_present: false,
  },
  league_memberships: [],
  sessions: [],
  competitive_summary: {
    league_memberships_preserved: 0,
    competitive_tables_present: false,
  },
};

const competitions: CompetitionResponse[] = [
  { id: "c1", provider_id: 39, name: "Premier League", country: "England" },
  { id: "c2", provider_id: 140, name: "La Liga", country: "Spain" },
  { id: "c3", provider_id: 135, name: "Serie A", country: "Italy" },
  { id: "c4", provider_id: 78, name: "Bundesliga", country: "Germany" },
  { id: "c5", provider_id: 61, name: "Ligue 1", country: "France" },
];

const league: LeagueResponse = {
  id: "00000000-0000-0000-0000-000000000010",
  name: "Draft League",
  season_year: 2025,
  state: "draft",
  role: "owner",
  competitions: competitions.slice(0, 3).map(({ id, provider_id, name, country }) => ({
    id,
    provider_id,
    name,
    country,
  })),
};

function mockLeagueClient(overrides: Partial<LeagueClient> = {}): LeagueClient {
  return {
    listCompetitions: vi.fn().mockResolvedValue(competitions),
    createLeague: vi.fn().mockResolvedValue(league),
    getLeague: vi.fn().mockResolvedValue(league),
    ...overrides,
  };
}

function mockClient(overrides: Partial<AuthClient> = {}): AuthClient {
  return {
    register: vi.fn().mockResolvedValue(session),
    login: vi.fn().mockResolvedValue(session),
    logout: vi.fn().mockResolvedValue({ message: "Logged out." } satisfies MessageResponse),
    me: vi.fn().mockResolvedValue(profile),
    getProfile: vi.fn().mockResolvedValue(profile),
    updateProfile: vi.fn().mockResolvedValue({ ...profile, display_name: "Mario Rossi" }),
    uploadAvatar: vi.fn().mockResolvedValue(profile),
    verifyEmail: vi.fn().mockResolvedValue({ ...profile, email_verified: true }),
    requestPasswordReset: vi.fn().mockResolvedValue({ message: "Sent." }),
    resetPassword: vi.fn().mockResolvedValue({ message: "Updated." }),
    exportData: vi.fn().mockResolvedValue(exportBundle),
    deleteAccount: vi.fn().mockResolvedValue({ message: "Account deleted." }),
    ...overrides,
  };
}

describe("AuthApp UI states", () => {
  it("renders empty-state hint before submit", () => {
    const html = renderToStaticMarkup(createElement(AuthApp, { client: mockClient() }));
    expect(html).not.toContain('data-testid="auth-error"');
  });

  it("renders login form fields", () => {
    const html = renderToStaticMarkup(createElement(AuthApp, { client: mockClient() }));
    expect(html).toContain('data-testid="auth-email"');
    expect(html).toContain('data-testid="auth-password"');
    expect(html).toContain('data-testid="auth-submit"');
  });

  it("shows verify-email form for verification links", () => {
    const html = renderToStaticMarkup(
      createElement(AuthApp, { client: mockClient(), initialView: "verify-email" }),
    );
    expect(html).toContain('data-testid="auth-verify-token"');
  });

  it("shows reset-password form for reset links", () => {
    const html = renderToStaticMarkup(
      createElement(AuthApp, { client: mockClient(), initialView: "reset-password" }),
    );
    expect(html).toContain('data-testid="auth-new-password"');
  });
});

describe("ProfilePanel UI states", () => {
  it("renders profile form with defaults", () => {
    const html = renderToStaticMarkup(
      createElement(ProfilePanel, {
        client: mockClient(),
        token: "token-123",
        profile,
        onUpdated: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="profile-display-name"');
    expect(html).toContain('data-testid="profile-language"');
    expect(html).toContain('data-testid="profile-timezone"');
    expect(html).toContain('data-testid="profile-avatar-empty"');
  });

  it("shows policy acceptance when not yet recorded", () => {
    const html = renderToStaticMarkup(
      createElement(ProfilePanel, {
        client: mockClient(),
        token: "token-123",
        profile,
        onUpdated: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="profile-accept-policy"');
  });

  it("shows policy accepted state", () => {
    const html = renderToStaticMarkup(
      createElement(ProfilePanel, {
        client: mockClient(),
        token: "token-123",
        profile: {
          ...profile,
          policy_consent_at: "2026-07-29T10:00:00Z",
          policy_version: "2026-01",
        },
        onUpdated: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="profile-policy-accepted"');
  });
});

describe("PrivacyPanel UI states", () => {
  it("renders export and delete controls", () => {
    const html = renderToStaticMarkup(
      createElement(PrivacyPanel, {
        client: mockClient(),
        token: "token-123",
        onDeleted: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="privacy-export"');
    expect(html).toContain('data-testid="privacy-delete-submit"');
    expect(html).toContain('data-testid="privacy-export-empty"');
  });

  it("renders empty delete hint state marker", () => {
    const html = renderToStaticMarkup(
      createElement(PrivacyPanel, {
        client: mockClient(),
        token: "token-123",
        onDeleted: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="privacy-delete-password"');
    expect(html).toContain('data-testid="privacy-delete-confirm"');
  });
});

describe("AuthApp privacy navigation", () => {
  it("shows privacy link on account panel", () => {
    const html = renderToStaticMarkup(
      createElement(AuthApp, {
        client: mockClient(),
        initialView: "account",
        initialToken: "token-123",
        initialUser: profile,
      }),
    );
    expect(html).toContain('data-testid="account-privacy"');
    expect(html).toContain('data-testid="account-create-league"');
  });

  it("renders privacy panel view", () => {
    const html = renderToStaticMarkup(
      createElement(AuthApp, {
        client: mockClient(),
        initialView: "privacy",
        initialToken: "token-123",
      }),
    );
    expect(html).toContain('data-testid="privacy-panel"');
  });

  it("renders create-league panel view", () => {
    const html = renderToStaticMarkup(
      createElement(AuthApp, {
        client: mockClient(),
        initialView: "create-league",
        initialToken: "token-123",
        initialUser: profile,
      }),
    );
    expect(html).toContain('data-testid="create-league-panel"');
  });
});

describe("CreateLeaguePanel UI states", () => {
  it("renders league form fields", () => {
    const client = mockLeagueClient();
    const html = renderToStaticMarkup(
      createElement(CreateLeaguePanel, {
        client,
        token: "token-123",
        locale: "it",
        emailVerified: true,
        onCreated: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="league-name"');
    expect(html).toContain('data-testid="league-season-year"');
    expect(html).toContain('data-testid="league-submit"');
    expect(html).toContain('data-testid="league-catalog-empty"');
  });

  it("renders empty-state marker in markup", () => {
    const html = renderToStaticMarkup(
      createElement(CreateLeaguePanel, {
        client: mockLeagueClient(),
        token: "token-123",
        locale: "it",
        emailVerified: true,
        onCreated: () => undefined,
      }),
    );
    expect(html).not.toContain('data-testid="league-error"');
  });

  it("renders permission error when catalog load fails", async () => {
    const client = mockLeagueClient({
      listCompetitions: vi.fn().mockRejectedValue(
        Object.assign(new Error("forbidden"), {
          name: "AuthApiError",
          code: "email_not_verified",
          status: 403,
        }),
      ),
    });
    const { AuthApiError } = await import("./api/auth");
    (client.listCompetitions as ReturnType<typeof vi.fn>).mockRejectedValue(
      new AuthApiError(403, {
        code: "email_not_verified",
        message: "Email address is not verified.",
      }),
    );
    const html = renderToStaticMarkup(
      createElement(CreateLeaguePanel, {
        client,
        token: "token-123",
        locale: "it",
        emailVerified: true,
        onCreated: () => undefined,
      }),
    );
    expect(html).toContain('data-testid="create-league-panel"');
  });
});

describe("resolveInitialAuthView", () => {
  it("maps verify and reset query params", async () => {
    const { resolveInitialAuthView } = await import("./auth/AuthApp");
    expect(resolveInitialAuthView("?token=abc")).toBe("verify-email");
    expect(resolveInitialAuthView("?token=abc&mode=reset")).toBe("reset-password");
    expect(resolveInitialAuthView("")).toBe("login");
  });
});
