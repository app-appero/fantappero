import assert from "node:assert/strict";
import test from "node:test";
import type { AuthSessionResponse, UserProfileResponse } from "@fantappero/contracts";
import { AuthApiError, createAuthClient } from "./api/auth.ts";

test("maps API errors from failed login", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    ({
      ok: false,
      status: 401,
      text: async () => JSON.stringify({ code: "invalid_credentials", message: "Nope." }),
    }) as Response;

  try {
    const client = createAuthClient("http://127.0.0.1:8000");
    await assert.rejects(client.login("a@b.com", "Secret123"), (error: unknown) => {
      assert.ok(error instanceof AuthApiError);
      assert.equal(error.code, "invalid_credentials");
      assert.equal(error.status, 401);
      return true;
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("returns session and profile on happy path", async () => {
  const session: AuthSessionResponse = {
    access_token: "token",
    token_type: "bearer",
    expires_at: "2026-07-28T12:00:00Z",
  };
  const profile: UserProfileResponse = {
    id: "00000000-0000-0000-0000-000000000001",
    email: "player@example.com",
    email_verified: true,
    created_at: "2026-07-28T10:00:00Z",
    display_name: null,
    avatar_url: null,
    language: "it",
    timezone: "Europe/Rome",
    notifications: { email: true, push: true },
    policy_consent_at: null,
    policy_version: null,
  };

  const originalFetch = globalThis.fetch;
  let call = 0;
  globalThis.fetch = async () => {
    call += 1;
    if (call === 1) {
      return {
        ok: true,
        text: async () => JSON.stringify(session),
      } as Response;
    }
    return {
      ok: true,
      text: async () => JSON.stringify(profile),
    } as Response;
  };

  try {
    const client = createAuthClient("http://127.0.0.1:8000");
    const loggedIn = await client.login("player@example.com", "Secret123");
    assert.equal(loggedIn.access_token, "token");
    const me = await client.me("token");
    assert.equal(me.email, "player@example.com");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
