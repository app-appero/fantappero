import { describe, expect, it } from "vitest";
import { googleAppHandoffUrl, googleAppReturnUrl } from "./googleAppReturn";

describe("googleAppReturnUrl", () => {
  it("accepts the app scheme and Expo Go", () => {
    expect(googleAppReturnUrl("fantappero://google-auth")).toBe("fantappero://google-auth");
    expect(googleAppReturnUrl("exp://192.168.1.20:8081/--/google-auth")).toBe(
      "exp://192.168.1.20:8081/--/google-auth",
    );
  });

  it("rejects web, empty and credentialed urls", () => {
    expect(googleAppReturnUrl("https://example.com/steal")).toBeNull();
    expect(googleAppReturnUrl("javascript:alert(1)")).toBeNull();
    expect(googleAppReturnUrl("")).toBeNull();
    expect(googleAppReturnUrl("exp://user:pass@host/google-auth")).toBeNull();
  });

  it("appends the id token on the allowed return url", () => {
    expect(googleAppHandoffUrl("fantappero://google-auth", "header.payload.sig")).toBe(
      "fantappero://google-auth?id_token=header.payload.sig",
    );
  });
});
