import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  PROFILE_LANGUAGE_OPTIONS,
  PROFILE_TIMEZONE_OPTIONS,
} from "../../../../packages/contracts/src/profile.ts";
import { DELETE_ACCOUNT_CONFIRMATION_PHRASE } from "../../../../packages/contracts/src/privacy.ts";

describe("EP02-02 profile contracts", () => {
  it("exposes Italian as default language option", () => {
    assert.equal(PROFILE_LANGUAGE_OPTIONS[0]?.value, "it");
  });

  it("includes Europe/Rome timezone", () => {
    const rome = PROFILE_TIMEZONE_OPTIONS.find((option) => option.value === "Europe/Rome");
    assert.ok(rome);
  });

  it("exposes delete confirmation phrase for privacy flow", () => {
    assert.equal(DELETE_ACCOUNT_CONFIRMATION_PHRASE, "ELIMINA");
  });
});
