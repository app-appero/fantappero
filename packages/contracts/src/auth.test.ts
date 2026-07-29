import assert from "node:assert/strict";
import test from "node:test";
import type { AuthSessionResponse, UserProfileResponse } from "./index.ts";
import { DEFAULT_UI_LOCALE, ui } from "./i18n.ts";

test("exports auth session shape", () => {
  const session: AuthSessionResponse = {
    access_token: "abc",
    token_type: "bearer",
    expires_at: "2026-07-28T12:00:00Z",
  };
  assert.equal(session.token_type, "bearer");
});

test("exports user profile shape", () => {
  const user: UserProfileResponse = {
    id: "00000000-0000-0000-0000-000000000001",
    email: "player@example.com",
    email_verified: false,
    created_at: "2026-07-28T10:00:00Z",
    display_name: "Mario",
    avatar_url: null,
    language: "it",
    timezone: "Europe/Rome",
    notifications: { email: true, push: false },
    policy_consent_at: null,
    policy_version: null,
  };
  assert.equal(user.notifications.push, false);
});

test("exports league configuration shape", () => {
  const league: import("./index.ts").LeagueResponse = {
    id: "00000000-0000-0000-0000-000000000010",
    name: "Draft League",
    season_year: 2025,
    state: "draft",
    role: "owner",
    competitions: [{ id: "c1", provider_id: 135, name: "Serie A", country: "Italy" }],
  };
  assert.equal(league.state, "draft");
  assert.equal(league.competitions.length, 1);
});

test("exports privacy data bundle shape", () => {
  const bundle: import("./index.ts").UserDataExportResponse = {
    format_version: "2026-01",
    exported_at: "2026-07-29T10:00:00Z",
    account: {
      id: "00000000-0000-0000-0000-000000000001",
      email: "player@example.com",
      email_verified: true,
      created_at: "2026-07-28T10:00:00Z",
      deleted_at: null,
    },
    profile: {
      display_name: "Mario",
      language: "it",
      timezone: "Europe/Rome",
      notifications_email: true,
      notifications_push: false,
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
  assert.equal(bundle.format_version, "2026-01");
});

test("defaults UI locale to Italian", () => {
  assert.equal(DEFAULT_UI_LOCALE, "it");
  assert.equal(ui().signIn, "Accedi");
});
