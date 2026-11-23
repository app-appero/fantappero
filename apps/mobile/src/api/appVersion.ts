import type { AndroidAppVersionUpdate, AppVersionInfo } from "@fantappero/contracts";
import { apiRequest } from "./client";

/** Ultima versione pubblicata dell'app (impostata dall'operatore). */
export function fetchAppVersion(accessToken: string): Promise<AppVersionInfo> {
  return apiRequest<AppVersionInfo>("/app/version", { accessToken });
}

/** Pannello operatore → «Versione app» (1.4): la versione annunciata, come sul sito. */
export function fetchAppVersionConfig(accessToken: string): Promise<AppVersionInfo> {
  return apiRequest<AppVersionInfo>("/admin/app-version", { accessToken });
}

/** Pannello operatore → «Versione app»: stessa chiamata del sito (`PUT /admin/app-version`). */
export function saveAppVersionConfig(
  accessToken: string,
  body: AndroidAppVersionUpdate,
): Promise<AppVersionInfo> {
  return apiRequest<AppVersionInfo>("/admin/app-version", { accessToken, method: "PUT", body });
}
