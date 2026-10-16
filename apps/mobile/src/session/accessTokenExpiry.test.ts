import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { accessTokenExpiresAtMs, accessTokenNeedsRefresh } from "./accessTokenExpiry.ts";

function tokenWithExp(expSeconds: number): string {
  const payload = Buffer.from(JSON.stringify({ exp: expSeconds })).toString("base64url");
  return `header.${payload}.sig`;
}

describe("accessTokenNeedsRefresh", () => {
  it("asks for a refresh when the token expires inside the skew window", () => {
    const now = Date.parse("2026-10-16T08:00:00Z");
    const exp = Math.floor((now + 30_000) / 1000);
    assert.equal(accessTokenNeedsRefresh(tokenWithExp(exp), now, 120_000), true);
  });

  it("keeps a token that is still valid beyond the skew window", () => {
    const now = Date.parse("2026-10-16T08:00:00Z");
    const exp = Math.floor((now + 10 * 60_000) / 1000);
    assert.equal(accessTokenNeedsRefresh(tokenWithExp(exp), now, 120_000), false);
    assert.equal(accessTokenExpiresAtMs(tokenWithExp(exp)), exp * 1000);
  });
});
