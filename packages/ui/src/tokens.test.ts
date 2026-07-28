import assert from "node:assert/strict";
import test from "node:test";
import { colors, spacing } from "./index.ts";

test("tokens expose required keys", () => {
  assert.ok(colors.ok);
  assert.equal(spacing.md, 16);
});
