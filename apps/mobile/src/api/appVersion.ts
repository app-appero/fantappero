import type {
  AdminAppUsage,
  AndroidAppVersionUpdate,
  AppVersionInfo,
  AppVersionSaveResult,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

/** Ultima versione pubblicata dell'app (impostata dall'operatore). */
export function fetchAppVersion(accessToken: string): Promise<AppVersionInfo> {
  return apiRequest<AppVersionInfo>("/app/version", { accessToken });
}

/** Pannello operatore → «Versione app» (1.4): la versione annunciata, come sul sito. */
export function fetchAppVersionConfig(accessToken: string): Promise<AppVersionInfo> {
  return apiRequest<AppVersionInfo>("/admin/app-version", { accessToken });
}

/**
 * Pannello operatore → «Versione app»: stessa chiamata del sito (`PUT /admin/app-version`).
 * Dalla 1.4 il server manda anche la notifica a chi non ha la versione e dice a quanti.
 */
export function saveAppVersionConfig(
  accessToken: string,
  body: AndroidAppVersionUpdate,
): Promise<AppVersionSaveResult> {
  return apiRequest<AppVersionSaveResult>("/admin/app-version", {
    accessToken,
    method: "PUT",
    body,
  });
}

/** Pannello operatore → «Versione app» (1.4): chi ha quale versione, versione per versione. */
export function fetchAppVersionUsers(accessToken: string): Promise<AdminAppUsage> {
  return apiRequest<AdminAppUsage>("/admin/app-version/users", { accessToken });
}
