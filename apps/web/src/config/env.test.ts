import { describe, expect, it } from "vitest";

import { loadWebEnv, resolveApiBaseUrl, WebEnvError } from "./env";

describe("loadWebEnv", () => {
  it("accepts a minimal valid configuration", () => {
    const env = loadWebEnv({ VITE_API_BASE_URL: "http://127.0.0.1:8001" });
    expect(env.viteApiBaseUrl).toBe("http://127.0.0.1:8001");
  });

  it("fails when VITE_API_BASE_URL is missing", () => {
    expect(() => loadWebEnv({})).toThrow(WebEnvError);
    expect(() => loadWebEnv({})).toThrow(/VITE_API_BASE_URL/);
  });

  it("fails when VITE_API_BASE_URL is malformed", () => {
    expect(() => loadWebEnv({ VITE_API_BASE_URL: "not-a-url" })).toThrow(/Malformed/);
  });
});

describe("resolveApiBaseUrl", () => {
  it("keeps loopback when the page is also local", () => {
    expect(
      resolveApiBaseUrl("http://127.0.0.1:8001", "http://localhost:5174/rosa"),
    ).toBe("http://127.0.0.1:8001");
  });

  it("uses the page origin when the UI is not on loopback", () => {
    expect(
      resolveApiBaseUrl("http://127.0.0.1:8001", "http://192.168.1.20:5174/rosa"),
    ).toBe("http://192.168.1.20:5174");
    expect(
      resolveApiBaseUrl("http://127.0.0.1:8001", "https://fantappero-web-dev.up.railway.app/rosa"),
    ).toBe("https://fantappero-web-dev.up.railway.app");
  });
});
