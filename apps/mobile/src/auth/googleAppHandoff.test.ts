import assert from "node:assert/strict";
import test from "node:test";

import {
  claimGoogleHandoffCode,
  readGoogleHandoffCode,
  releaseGoogleHandoffCode,
} from "./googleAppHandoff.ts";

test("readGoogleHandoffCode reads the handoff query", () => {
  assert.equal(
    readGoogleHandoffCode("exp://10.0.0.2:8081/--/google-auth?code=one-time-code"),
    "one-time-code",
  );
});

test("readGoogleHandoffCode ignores a return without a code", () => {
  assert.equal(readGoogleHandoffCode("fantappero://google-auth"), null);
  assert.equal(readGoogleHandoffCode("not a url"), null);
});

test("claimGoogleHandoffCode keeps a single in-flight code and allows a retry", () => {
  const claim = { code: null };
  const url = "exp://10.0.0.2:8081/--/google-auth?code=one-time-code";
  assert.equal(claimGoogleHandoffCode(url, claim), "one-time-code");
  assert.equal(claimGoogleHandoffCode(url, claim), null);
  assert.equal(claimGoogleHandoffCode(null, claim), null);
  releaseGoogleHandoffCode("one-time-code", claim);
  assert.equal(claimGoogleHandoffCode(url, claim), "one-time-code");
});
