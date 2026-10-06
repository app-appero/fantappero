import assert from "node:assert/strict";
import test from "node:test";

import { readGoogleIdToken } from "./googleAppHandoff.ts";

test("readGoogleIdToken reads the handoff query", () => {
  assert.equal(
    readGoogleIdToken("exp://10.0.0.2:8081/--/google-auth?id_token=header.payload.sig"),
    "header.payload.sig",
  );
});

test("readGoogleIdToken ignores a return without a token", () => {
  assert.equal(readGoogleIdToken("fantappero://google-auth"), null);
  assert.equal(readGoogleIdToken("not a url"), null);
});
