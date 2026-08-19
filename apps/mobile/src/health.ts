import type { HealthResponse } from "@fantappero/contracts";

/** Mobile scaffold health payload — no network required. */
export function getMobileHealth(): HealthResponse {
  return { status: "ok" };
}
