/** Health check contract types. */

export type HealthStatus = "ok" | "degraded" | "error";

export interface HealthResponse {
  status: HealthStatus;
}

export interface ServiceInfo {
  service: string;
  status: HealthStatus;
}

/** Stable service identifiers used by clients. */
export const SERVICES = {
  api: "fantappero-api",
  web: "fantappero-web",
  mobile: "fantappero-mobile",
} as const;

export type ServiceId = (typeof SERVICES)[keyof typeof SERVICES];
