import assert from "node:assert/strict";
import test from "node:test";
import { SERVICES, type HealthResponse } from "./health.ts";

test("SERVICES exposes stable ids", () => {
  assert.equal(SERVICES.api, "fantappero-api");
  assert.equal(SERVICES.web, "fantappero-web");
  assert.equal(SERVICES.mobile, "fantappero-mobile");
});

test("HealthResponse status is typed", () => {
  const body: HealthResponse = { status: "ok" };
  assert.equal(body.status, "ok");
});
