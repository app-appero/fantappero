import { describe, expect, it } from "vitest";

import { loadWebEnv, WebEnvError } from "./env";

describe("loadWebEnv", () => {
  it("accepts a minimal valid configuration", () => {
    const env = loadWebEnv({ VITE_API_BASE_URL: "http://127.0.0.1:8000" });
    expect(env.viteApiBaseUrl).toBe("http://127.0.0.1:8000");
  });

  it("fails when VITE_API_BASE_URL is missing", () => {
    expect(() => loadWebEnv({})).toThrow(WebEnvError);
    expect(() => loadWebEnv({})).toThrow(/VITE_API_BASE_URL/);
  });

  it("fails when VITE_API_BASE_URL is malformed", () => {
    expect(() => loadWebEnv({ VITE_API_BASE_URL: "not-a-url" })).toThrow(/Malformed/);
  });
});
