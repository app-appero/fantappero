import assert from "node:assert/strict";
import test from "node:test";

import { loadMobileEnv, MobileEnvError } from "./env.ts";

test("loadMobileEnv accepts minimal valid configuration", () => {
  const env = loadMobileEnv({ EXPO_PUBLIC_API_BASE_URL: "http://127.0.0.1:8001" });
  assert.equal(env.expoPublicApiBaseUrl, "http://127.0.0.1:8001");
});

test("loadMobileEnv fails when EXPO_PUBLIC_API_BASE_URL is missing", () => {
  assert.throws(
    () => loadMobileEnv({}),
    (err: unknown) => err instanceof MobileEnvError && /EXPO_PUBLIC_API_BASE_URL/.test(String(err)),
  );
});

test("loadMobileEnv fails when URL is malformed", () => {
  assert.throws(
    () => loadMobileEnv({ EXPO_PUBLIC_API_BASE_URL: "not-a-url" }),
    (err: unknown) => err instanceof MobileEnvError && /Malformed/.test(String(err)),
  );
});
