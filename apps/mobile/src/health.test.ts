import assert from "node:assert/strict";
import test from "node:test";
import { getMobileHealth } from "./health.ts";

test("mobile health is ok without network", () => {
  assert.deepEqual(getMobileHealth(), { status: "ok" });
});
