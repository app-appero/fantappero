import Constants from "expo-constants";
import { Platform } from "react-native";
import { appVersionHeaders } from "./versionHeaders";
import { appVersionLabel } from "./versionLabel";

/**
 * versionCode dell'app installata. Viene da `android.versionCode` di `app.json` (unica fonte:
 * il prebuild lo scrive nell'APK e expo-constants lo incorpora nella build); `null` se non si legge.
 */
export function installedAndroidVersionCode(): number | null {
  const code = Constants.expoConfig?.android?.versionCode;
  return typeof code === "number" && Number.isSafeInteger(code) && code > 0 ? code : null;
}

/**
 * Versione installata per le segnalazioni, es. «1.2.0 (3)»: `version` e `android.versionCode`
 * di `app.json`, letti come per l'avviso di nuova versione; `undefined` se non si leggono.
 */
export function installedAppVersionLabel(): string | undefined {
  return appVersionLabel(Constants.expoConfig?.version, installedAndroidVersionCode());
}

let cachedHeaders: Record<string, string> | null = null;

/**
 * Intestazioni con la versione installata per ogni richiesta al server (release 1.4): non
 * cambiano mentre l'app è aperta, si leggono una volta sola.
 */
export function installedAppVersionHeaders(): Record<string, string> {
  if (cachedHeaders === null) {
    cachedHeaders = appVersionHeaders(
      Platform.OS,
      Constants.expoConfig?.version,
      installedAndroidVersionCode(),
    );
  }
  return cachedHeaders;
}
