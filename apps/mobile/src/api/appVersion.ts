import type { AppVersionInfo } from "@fantappero/contracts";
import { apiRequest } from "./client";

/** Ultima versione pubblicata dell'app (impostata dall'operatore). */
export function fetchAppVersion(accessToken: string): Promise<AppVersionInfo> {
  return apiRequest<AppVersionInfo>("/app/version", { accessToken });
}
